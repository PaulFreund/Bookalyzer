"""Comparison invariants: pinned reference space, lossless chapters, and missing data."""
import base64
import json
import numpy as np
import pandas as pd
import pytest

from bookanalyzer.desktop import DEFAULTS, DesktopService, validate_settings
from bookanalyzer.desktop_compare import BaselineSpace
from bookanalyzer.segment import assert_no_text_loss
from conftest import valid_taxonomy_row


@pytest.fixture
def service(tmp_path):
    app = DesktopService(tmp_path / "library", seed=False)
    yield app
    app.executor.shutdown(wait=True)


def upload(service, title="Roman.txt", chapters=True, text=None):
    text = text or "Kapitel 1 – Regen\n" + "Regen fiel. Sie wartete am Fenster. " * 22 + "\nKapitel 2 – Licht\n" + "Am nächsten Morgen ging er langsam durch den noch dunklen Garten. " * 25 + "\nKapitel 3 – Heimkehr\nSie kam zurück."
    return service.prepare(title, base64.b64encode(text.encode()).decode(),
                           {**DEFAULTS, "detectChapters": chapters, "minWords": 100, "targetWords": 200, "maxWords": 300})


def finish(service, document, values=None):
    directory = service._directory(document["id"])
    segments = pd.read_parquet(directory / "segments.parquet")
    features = None
    if values is not None:
        _, specs = service._taxonomy()
        rows = []
        for i, segment in segments.iterrows():
            row = valid_taxonomy_row(specs, prompt_id=i + 1)
            row.update(segment.drop(labels=["human_story"]).to_dict())
            row.update(TMP_ORD_010=str(values[i % len(values)]), extraction_model="fixture")
            rows.append(row)
        features = pd.DataFrame(rows)
        features.to_parquet(directory / "features.parquet", index=False)
    service._complete(document, segments, features)
    service._persist()
    return segments


def test_optional_chapters_never_cross_boundaries_or_drop_short_chapters(service):
    doc = upload(service)
    segments = finish(service, doc)
    assert (segments.chapter_index == segments.chapter_end_index).all()
    assert segments.iloc[-1].word_count == 3
    assert_no_text_loss(pd.read_parquet(service._directory(doc["id"]) / "sections.parquet"), segments)
    result = service.chapters(doc["id"])
    assert len(result["chapters"]) == 3
    assert [r["words"] for r in result["chapters"]] == [132, 275, 3]
    assert result["chapters"][-1]["short"]
    assert service.chapter_text(doc["id"], 2)["text"] == "Sie kam zurück."
    assert all(r["profiles"] == [] for r in result["chapters"])
    with pytest.raises(ValueError):
        validate_settings({"detectChapters": "yes"})


def test_legacy_cross_chapter_segments_do_not_invent_chapter_features(service):
    doc = upload(service, chapters=False)
    segments = finish(service, doc, [1, 5])
    assert (segments.chapter_index != segments.chapter_end_index).any()
    result = service.chapters(doc["id"])
    for row in result["chapters"]:
        overlapping = segments[(segments.chapter_index <= row["index"]) & (segments.chapter_end_index >= row["index"])]
        if (overlapping.chapter_index != overlapping.chapter_end_index).any():
            assert not row["narrativeComplete"]
            assert row["profiles"] == []
            assert all(v is None for v in result["distance"][result["chapters"].index(row)])


def test_baseline_scaler_fits_reference_only_and_survives_removal_restart(service):
    reference = upload(service, title="Referenz.txt")
    finish(service, reference, [1, 2])
    baseline = service.baseline_create(reference["id"], "Fester Stand")
    query = upload(service, title="Neu.txt", text="Kapitel 1\n" + "Andere Worte in diesem Text. " * 80)
    finish(service, query, [5])
    other = upload(service, title="Weiterer.txt", text="Kapitel 1\n" + "Ein dritter unabhängiger Text im Vergleich. " * 75)
    finish(service, other, [3])
    alone = service.baseline_compare([query["id"]], baseline["id"])
    together = service.baseline_compare([query["id"], other["id"]], baseline["id"])
    assert alone["rows"][0] == together["rows"][0]
    assert alone["rows"][0]["distance"] > 0
    space = BaselineSpace(service, baseline["id"])
    assert space.scaler.n_samples_seen_ == reference["segmentCount"]
    # Independently compute the one varying feature's k-neighbor distances.
    ref_values = np.array([1, 2, 1], dtype=float)
    assert reference["segmentCount"] == len(ref_values)
    expected = np.abs((5 - ref_values) / ref_values.std()).mean()
    assert alone["rows"][0]["distance"] == pytest.approx(expected, rel=1e-6)
    service.remove(reference["id"])
    reopened = DesktopService(service.root, seed=False)
    assert reopened.baseline_compare([query["id"]], baseline["id"]) == alone
    reopened.executor.shutdown()


def test_chapter_baseline_values_and_pairwise_distances(service):
    reference = upload(service, title="Referenz.txt", text="Kapitel 1\n" + "Ein langer Satz im anderen Referenztext. " * 90)
    finish(service, reference, [1, 2])
    baseline = service.baseline_create(reference["id"])
    book = upload(service)
    finish(service, book, [1, 3, 5])
    result = service.chapters(book["id"], baseline["id"])
    assert all(r["narrativeComplete"] for r in result["chapters"])
    values = [r["comparison"]["distance"] for r in result["chapters"]]
    assert values[-1] > values[0]
    distance = np.array(result["distance"])
    assert np.allclose(distance, distance.T)
    assert np.allclose(distance.diagonal(), 0)
    assert distance[0, 2] > distance[0, 1]
    assert len(result["chapters"][1]["profiles"]) == 6


def test_baseline_rejects_incompatible_model_and_self_comparison(service):
    reference = upload(service)
    finish(service, reference, [1, 2])
    baseline = service.baseline_create(reference["id"])
    self_score = service.baseline_compare([reference["id"]], baseline["id"])["rows"][0]
    assert self_score["distance"] is None
    duplicate = upload(service, title="Kopie.txt")
    finish(service, duplicate, [1, 2])
    assert service.baseline_compare([duplicate["id"]], baseline["id"])["rows"][0]["distance"] is None
    query = upload(service, text="Kapitel 1\n" + "Ein fremder Text für die Kontrolle. " * 90)
    finish(service, query, [4])
    query["narrative"]["model"] = "other"
    result = service.baseline_compare([query["id"]], baseline["id"])["rows"][0]
    assert result["distance"] is None and "Extraktionsmodelle" in result["reason"]
    assert result["delta"]["sentenceMean"] is not None
    query["narrative"]["model"] = "fixture"
    query["narrative"]["reasoningEffort"] = "high"
    result = service.baseline_compare([query["id"]], baseline["id"])["rows"][0]
    assert result["distance"] is None and "Reasoning-Level" in result["reason"]
    assert result["delta"]["sentenceMean"] is not None


def test_baseline_tampering_is_detected(service):
    reference = upload(service)
    finish(service, reference)
    baseline = service.baseline_create(reference["id"])
    path = service.root / "baselines" / baseline["id"] / "snapshot.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["metrics"]["sentenceMean"] = 999
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="verändert"):
        service.baseline_compare([reference["id"]], baseline["id"])
