"""Adding StoryScope must preserve local results and require new scoped consent."""
import base64
import json
import threading

import pandas as pd
import pytest

from bookanalyzer.desktop import DEFAULTS, DesktopService
from bookanalyzer.provenance import sha256_file
from conftest import valid_taxonomy_row


@pytest.fixture
def local(service):
    doc = service.prepare(
        "Existing.txt",
        base64.b64encode(("Rain falls. The road shines in the morning light.\n\n" * 60).encode()).decode(),
        {**DEFAULTS, "language": "en", "minWords": 100, "targetWords": 200, "maxWords": 300},
    )
    service.start([doc["id"]])
    service.executor.submit(lambda: None).result(timeout=10)
    return doc


@pytest.fixture
def service(tmp_path):
    app = DesktopService(tmp_path / "library", seed=False)
    yield app
    app.executor.shutdown(wait=True)


APPROVAL = {"consent": True, "previewConfirmed": True, "approver": "Reader"}


@pytest.mark.parametrize("approval", [
    {}, {"consent": True}, {"consent": True, "previewConfirmed": True},
    {**APPROVAL, "approver": " "}, {**APPROVAL, "consent": 1},
])
def test_local_approval_does_not_authorize_storyscope(service, local, approval):
    before = json.dumps(local, sort_keys=True)
    with pytest.raises(ValueError, match="ausdrücklich"):
        service.call("storyscope_start", {"id": local["id"], **approval})
    assert json.dumps(local, sort_keys=True) == before
    assert not (service._directory(local["id"]) / "rights.yaml").exists()


def test_storyscope_keeps_text_profile_readable_and_preserves_saved_baseline(service, local, monkeypatch):
    from bookanalyzer import codex_adapter, feature_matrix
    directory = service._directory(local["id"])
    original_segments = sha256_file(directory / "segments.parquet")
    original_metrics = dict(local["metrics"])
    baseline = service.baseline_create(local["id"], "Before StoryScope")
    baseline_hashes = dict(baseline["hashes"])
    entered, release = threading.Event(), threading.Event()
    calls = []

    def extract(**params):
        calls.append(params)
        entered.set()
        assert release.wait(timeout=10)

    def compile_features(raw, taxonomy, segments_path, output):
        segments = pd.read_parquet(segments_path)
        _, specs = service._taxonomy()
        rows = []
        for index, segment in segments.iterrows():
            row = valid_taxonomy_row(specs, prompt_id=index)
            row.update(segment.drop(labels=["human_story"]).to_dict())
            row["extraction_model"] = "selected-model"
            rows.append(row)
        frame = pd.DataFrame(rows)
        frame.to_parquet(output, index=False)
        return frame

    monkeypatch.setattr(codex_adapter, "extract_features_with_codex", extract)
    monkeypatch.setattr(feature_matrix, "compile_feature_jsons", compile_features)
    try:
        service.storyscope_start(local["id"], model="selected-model", reasoningEffort="high", parallel=2, **APPROVAL)
        assert entered.wait(timeout=5)
        assert local["status"] == "ready"
        assert local["storyscope"]["status"] == "analyzing"
        assert service.quality([local["id"]])["rows"]
        service.local_update(local["id"], {"textProfile": "technical", "longSentenceWords": 35})
        assert local["storyscope"]["status"] == "analyzing"
        assert local["settings"]["model"] == "selected-model"
        assert service.bootstrap()["documents"][0]["progress"]["total"] == local["segmentCount"] * 10
        with pytest.raises(ValueError, match="bereits gestartet"):
            service.storyscope_start(local["id"], **APPROVAL)
        with pytest.raises(ValueError, match="Laufende Analyse"):
            service.remove(local["id"])
        with pytest.raises(ValueError, match="StoryScope abschließen"):
            service.baseline_create(local["id"])
    finally:
        release.set()
    service.executor.submit(lambda: None).result(timeout=10)
    assert local["storyscope"]["status"] == "ready"
    assert local["narrative"]["featureCount"] == 304
    assert local["narrative"]["model"] == "selected-model"
    assert local["metrics"] == original_metrics
    assert sha256_file(directory / "segments.parquet") == original_segments
    assert calls[0]["parallel"] == 2
    assert calls[0]["reasoning_effort"] == "high"
    assert local["narrative"]["reasoningEffort"] == "high"
    assert calls[0]["rights_approval_path"].is_file()
    assert len(service.state["documents"]) == 1
    for name, expected in baseline_hashes.items():
        assert sha256_file(service.root / "baselines" / baseline["id"] / name) == expected
    with pytest.raises(ValueError, match="bereits fertig"):
        service.storyscope_start(local["id"], **APPROVAL)


def test_failed_storyscope_can_resume_with_pinned_model_and_local_quality(service, local, monkeypatch):
    from bookanalyzer import codex_adapter
    calls = []

    def extract(**params):
        calls.append(params)
        raise RuntimeError("Offline fixture")

    monkeypatch.setattr(codex_adapter, "extract_features_with_codex", extract)
    monkeypatch.setattr(codex_adapter, "configured_codex_model", lambda: "first-model")
    service.storyscope_start(local["id"], **APPROVAL)
    service.executor.submit(lambda: None).result(timeout=10)
    assert local["status"] == "ready"
    assert local["error"] is None
    assert local["storyscope"]["status"] == "error"
    assert "Offline fixture" in local["storyscope"]["error"]
    assert service.quality([local["id"]])["rows"]
    monkeypatch.setattr(codex_adapter, "configured_codex_model", lambda: "changed-default")
    with pytest.raises(ValueError, match="bisherige Modell"):
        service.storyscope_start(local["id"], model="changed-default", **APPROVAL)
    with pytest.raises(ValueError, match="bisherigen Reasoning-Level"):
        service.storyscope_start(local["id"], model="first-model", reasoningEffort="high", **APPROVAL)
    service.retry(local["id"])
    service.executor.submit(lambda: None).result(timeout=10)
    assert [call["model"] for call in calls] == ["first-model", "first-model"]
    assert [call["reasoning_effort"] for call in calls] == ["low", "low"]
    assert calls[0]["response_dir"] == calls[1]["response_dir"]
    assert local["approval"]["approver"] == "Reader"


def test_known_model_rejects_unsupported_effort_before_queueing(service, local, monkeypatch):
    monkeypatch.setattr("bookanalyzer.codex_catalog.read_models", lambda: [{
        "id": "model-a", "reasoningEfforts": ["low", "medium"], "defaultReasoningEffort": "medium",
    }])
    before = json.dumps(local, sort_keys=True)
    with pytest.raises(ValueError, match="unterstützt"):
        service.storyscope_start(local["id"], model="model-a", reasoningEffort="ultra", **APPROVAL)
    assert json.dumps(local, sort_keys=True) == before
    assert service._pin_codex_options({**local["settings"], "model": "model-a", "reasoningEffort": ""})["reasoningEffort"] == "medium"


def test_invalid_model_batch_does_not_start_first_document(service, monkeypatch):
    monkeypatch.setattr("bookanalyzer.codex_catalog.read_models", lambda: [{
        "id": "model-a", "reasoningEfforts": ["low"], "defaultReasoningEffort": "low",
    }])
    documents = []
    for effort in ("low", "ultra"):
        documents.append(service.prepare("Batch.txt", base64.b64encode(b"A small story. " * 50).decode(),
                         {**DEFAULTS, "mode": "codex", "model": "model-a", "reasoningEffort": effort}))
    with pytest.raises(ValueError, match="unterstützt"):
        service.start([doc["id"] for doc in documents], **APPROVAL)
    assert all(doc["status"] == "draft" for doc in documents)


def test_unavailable_catalog_does_not_change_saved_defaults(service, monkeypatch):
    def unavailable():
        raise RuntimeError("Offline fixture")
    monkeypatch.setattr("bookanalyzer.codex_catalog.read_models", unavailable)
    before = dict(service.state["settings"])
    catalog = service.codex_models()
    assert not catalog["available"]
    assert "Offline fixture" in catalog["reason"]
    assert service.state["settings"] == before


def test_reopening_interrupted_supplement_preserves_local_report(service, local):
    report = list(local["report"])
    local["storyscope"] = {"status": "analyzing", "error": None, "startedAt": "fixture"}
    service._persist()
    reopened = DesktopService(service.root, seed=False)
    try:
        document = reopened._document(local["id"])
        assert document["status"] == "ready"
        assert document["report"] == report
        assert document["storyscope"]["status"] == "error"
        assert "Fortsetzen" in document["storyscope"]["error"]
        assert reopened.quality([local["id"]])["rows"]
    finally:
        reopened.executor.shutdown()


def test_local_expansion_preserves_storyscope_features_and_authorization(service, local, monkeypatch):
    from bookanalyzer import codex_adapter
    directory = service._directory(local["id"])
    segments = pd.read_parquet(directory / "segments.parquet")
    _, specs = service._taxonomy()
    rows = []
    for index, segment in segments.iterrows():
        row = valid_taxonomy_row(specs, prompt_id=index)
        row.update(segment.drop(labels=["human_story"]).to_dict())
        row["extraction_model"] = "existing-model"
        rows.append(row)
    features = pd.DataFrame(rows)
    features.to_parquet(directory / "features.parquet", index=False)
    local["settings"].update(mode="codex", model="existing-model", qualityGroups=[])
    local["approval"] = dict(APPROVAL)
    service._complete(local, segments, features)
    narrative = json.dumps(local["narrative"], sort_keys=True)
    hashes = {name: sha256_file(directory / name) for name in ("segments.parquet", "features.parquet")}
    approval = dict(local["approval"])
    monkeypatch.setattr(codex_adapter, "extract_features_with_codex", lambda **kwargs: pytest.fail("Local analysis invoked Codex"))
    result = service.call("local_update", {"id": local["id"], "settings": {
        "qualityGroups": ["readability", "rhythm"], "textProfile": "informative",
        "longSentenceWords": 25, "longSentenceShare": 5,
    }})
    assert result["status"] == "ready"
    assert result["settings"]["mode"] == "codex"
    assert result["settings"]["model"] == "existing-model"
    assert result["approval"] == approval
    assert json.dumps(result["narrative"], sort_keys=True) == narrative
    quality = service.quality([local["id"]])["rows"][0]["quality"]
    assert set(quality["groups"]) == {"readability", "rhythm"}
    assert quality["longSentenceWords"] == 25
    for name, expected in hashes.items():
        assert sha256_file(directory / name) == expected
    assert len(service.state["documents"]) == 1
    before = json.dumps(local, sort_keys=True)
    with pytest.raises(ValueError, match="nur die lokalen"):
        service.local_update(local["id"], {"mode": "local"})
    assert json.dumps(local, sort_keys=True) == before


def test_local_analysis_can_be_created_after_initial_codex_failure(service, monkeypatch):
    from bookanalyzer import codex_adapter

    def offline(**params):
        raise RuntimeError("Codex unavailable")

    monkeypatch.setattr(codex_adapter, "extract_features_with_codex", offline)
    doc = service.prepare("External.txt", base64.b64encode(("Light fills the room.\n\n" * 60).encode()).decode(),
                          {**DEFAULTS, "mode": "codex", "minWords": 100, "targetWords": 200, "maxWords": 300})
    service.start([doc["id"]], **APPROVAL)
    service.executor.submit(lambda: None).result(timeout=10)
    assert doc["status"] == "error"
    assert not doc.get("metrics")
    service.local_update(doc["id"], {})
    assert doc["status"] == "ready"
    assert doc["storyscope"]["status"] == "error"
    assert doc["storyscope"]["error"] == "Codex unavailable"
    assert service.quality([doc["id"]])["rows"]
    service.retry(doc["id"])
    service.executor.submit(lambda: None).result(timeout=10)
    assert doc["status"] == "ready"
    assert doc["storyscope"]["status"] == "error"
