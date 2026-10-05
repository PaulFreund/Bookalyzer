"""Desktop boundaries: private uploads, settings, consent and comparable spaces."""
import base64
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bookanalyzer.desktop import DEFAULTS, DesktopService, axis_value, surface_metrics, validate_settings
from bookanalyzer.feature_matrix import FeatureSpec
from conftest import valid_taxonomy_row


@pytest.fixture
def service(tmp_path):
    app = DesktopService(tmp_path / "library", seed=False)
    yield app
    app.executor.shutdown(wait=True)


def prepare(service, *, mode="local", title="Test.txt"):
    return service.prepare(
        name=title,
        base64data=base64.b64encode(("First comes rain. Then the sun returns, bright and warm.\n\n" * 60).encode()).decode(),
        settings={**DEFAULTS, "mode": mode, "minWords": 100, "targetWords": 200, "maxWords": 300},
    )


@pytest.mark.parametrize("change", [
    {"targetWords": 50}, {"minWords": 6000}, {"maxWords": 25000},
    {"parallel": 0}, {"parallel": True}, {"mode": "unknown"}, {"featureSet": "paper_narrative_257"},
    {"excludeFrontmatter": "false"}, {"model": "x;not-a-model"},
    {"reasoningEffort": "fast"}, {"reasoningEffort": True},
])
def test_invalid_settings_rejected(change):
    with pytest.raises(ValueError):
        validate_settings({**DEFAULTS, **change})


def test_surface_metrics_do_not_invent_short_text_vocabulary():
    result = surface_metrics("One short sentence. A much longer sentence with a few additional words.")
    assert result["sentences"] == 2
    assert result["words"] == 12
    assert result["vocabulary"] is None
    assert sum(result["histogram"]) == 2
    assert not any(key in result for key in ("humanProbability", "aiScore", "qualityScore"))


def test_reference_axis_never_maps_unknown_values(small_specs):
    assert axis_value("2", small_specs["SCL"]) == 50
    assert axis_value("2.0", small_specs["SCL"]) == 50
    assert axis_value("medium", small_specs["ORD"]) == 50
    assert axis_value("4", small_specs["SCL"]) is None
    assert axis_value("n/a", small_specs["SCL"]) is None
    assert axis_value("2_unpublished_label", small_specs["SCL"]) is None
    assert axis_value("made_up", small_specs["ORD"]) is None


def test_local_upload_is_isolated_and_persists(service):
    doc = prepare(service)
    assert doc["segmentCount"] >= 2
    before = dict(doc["settings"])
    service.settings({**DEFAULTS, "language": "en"})
    assert doc["settings"] == before
    directory = service._directory(doc["id"])
    assert directory.is_relative_to(service.root)
    assert (directory / "segment_preview.csv").is_file()
    assert service.segment(doc["id"], 0)["text"]
    service.start([doc["id"]])
    service.executor.shutdown(wait=True)
    assert doc["status"] == "ready"
    assert doc["narrative"] is None
    assert len(doc["segmentMetrics"]) == doc["segmentCount"]
    reopened = DesktopService(service.root, seed=False)
    assert reopened._document(doc["id"])["report"] == doc["report"]
    assert reopened.state["settings"]["language"] == "en"
    reopened.executor.shutdown()


@pytest.mark.parametrize("params", [
    {}, {"consent": True}, {"consent": True, "previewConfirmed": True},
    {"consent": True, "previewConfirmed": True, "approver": "  "},
])
def test_external_upload_requires_scoped_consent_and_preview(service, params):
    doc = prepare(service, mode="codex")
    with pytest.raises(ValueError, match="ausdrücklich"):
        service.start([doc["id"]], **params)
    assert doc["status"] == "draft"
    assert not (service._directory(doc["id"]) / "rights.yaml").exists()


def test_external_approval_records_stay_per_upload(service, monkeypatch):
    from bookanalyzer import codex_adapter
    calls = []
    def stopped_extractor(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("Simulated offline extraction")
    monkeypatch.setattr(codex_adapter, "configured_codex_model", lambda: "test-model")
    monkeypatch.setattr(codex_adapter, "extract_features_with_codex", stopped_extractor)
    docs = [prepare(service, mode="codex", title=title) for title in ("One.txt", "Two.txt")]
    service.start([doc["id"] for doc in docs], consent=True, previewConfirmed=True, approver="Test User")
    service.executor.shutdown(wait=True)
    assert len(calls) == 2
    assert calls[0]["rights_approval_path"] != calls[1]["rights_approval_path"]
    for doc, kwargs in zip(docs, calls):
        assert doc["status"] == "error"
        assert doc["settings"]["model"] == "test-model"
        assert kwargs["segment_approval_path"].parent == service._directory(doc["id"])
        assert kwargs["rights_approval_path"].exists()
        assert kwargs["model"] == "test-model"
        assert "Simulated offline" in doc["error"]


def test_comparison_uses_one_shared_space_and_self_exclusion(service):
    _, specs = service._taxonomy()
    docs = [prepare(service, title=name) for name in ("One.txt", "Two.txt")]
    for di, doc in enumerate(docs):
        directory = service._directory(doc["id"])
        segments = pd.read_parquet(directory / "segments.parquet")
        rows = []
        for i, segment in segments.iterrows():
            values = valid_taxonomy_row(specs, prompt_id=i)
            values.update(segment.drop(labels=["human_story"]).to_dict())
            values["TMP_ORD_010"] = str(1 + (di + i) % 5)
            values["extraction_model"] = "fixture"
            rows.append(values)
        frame = pd.DataFrame(rows)
        frame.to_parquet(directory / "features.parquet", index=False)
        service._complete(doc, segments, frame)
    result = service.compare([doc["id"] for doc in docs])
    assert result["available"]
    assert result["k"] == sum(doc["segmentCount"] for doc in docs) - 1
    assert len(result["series"]) == 2
    distance = np.array(result["distance"])
    assert np.allclose(distance, distance.T)
    assert np.allclose(distance.diagonal(), 0)
    assert all(np.isfinite(series["values"]).all() for series in result["series"])
    assert "percentile" not in result
    assert service.compare([doc["id"] for doc in docs]) == result
    docs[1]["narrative"]["reasoningEffort"] = "high"
    service.comparisons.clear()
    assert "Reasoning-Level" in service.compare([doc["id"] for doc in docs])["reason"]
    docs[1]["narrative"]["reasoningEffort"] = "low"
    docs[1]["settings"]["featureSet"] = "full_304"
    service.comparisons.clear()
    assert not service.compare([doc["id"] for doc in docs])["available"]


def test_invalid_ids_files_and_duplicate_jobs_are_rejected(service):
    with pytest.raises(ValueError):
        service.segment("../escape", 0)
    with pytest.raises(ValueError):
        service.prepare("bad.exe", "YWJj", DEFAULTS)
    with pytest.raises(ValueError):
        service.prepare("empty.txt", "", DEFAULTS)
    doc = prepare(service)
    with pytest.raises(ValueError):
        service.start([doc["id"], doc["id"]])
    service.start([doc["id"]])
    with pytest.raises(ValueError):
        service.start([doc["id"]])


def test_interrupted_job_can_be_recovered(service):
    doc = prepare(service, mode="codex")
    doc["status"] = "analyzing"
    service._persist()
    reopened = DesktopService(service.root, seed=False)
    assert reopened._document(doc["id"])["status"] == "error"
    assert "unterbrochen" in reopened._document(doc["id"])["error"]
    reopened.executor.shutdown()
