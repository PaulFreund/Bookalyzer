"""Regressions for complete review queues and explainable style comparisons."""
import base64
from copy import deepcopy

import pandas as pd
import pytest

from bookanalyzer.desktop import DEFAULTS, DesktopService
from bookanalyzer.quality import analyze
from bookanalyzer.quality_summary import summarize


@pytest.fixture
def service(tmp_path):
    instance = DesktopService(tmp_path, seed=False)
    yield instance
    instance.executor.shutdown()


def upload(service, text):
    doc = service.prepare("Review.txt", base64.b64encode(text.encode()).decode(), {**DEFAULTS, "detectChapters": True})
    service._complete(doc, pd.read_parquet(service._directory(doc["id"]) / "segments.parquet"))
    return doc


PARAGRAPH = "Am Morgen geht die kleine Gruppe langsam durch den stillen Wald. Neben dem Fluss bleiben alle Wanderer stehen und sehen sich aufmerksam um."


@pytest.mark.parametrize("chapter", [False, True])
def test_all_repeat_findings_advance_past_six_and_remain_reversible(service, chapter):
    doc = upload(service, ("Kapitel 1\n" if chapter else "") + "\n\n".join([PARAGRAPH] * 20))
    def report():
        return service.quality([] if chapter else [doc["id"]], bookId=doc["id"] if chapter else None)["rows"][0]
    first = report()
    assert first["quality"]["evidenceCounts"]["paragraphRepeat"] == 19
    assert first["quality"]["evidenceCounts"]["sentenceRepeat"] == 38
    assert "evidenceIndex" not in first["quality"], "Only visible excerpts belong in the report payload"
    saved = []
    for index in range(57):
        row = report()
        priority = next(p for p in row["summary"]["priorities"] if p["group"] == "Wiederholung")
        finding = priority["evidence"][0]
        assert finding["key"] not in {e["key"] for e in saved}
        assert row["quality"]["values"] == first["quality"]["values"]
        assert row["summary"]["intentional"] == index
        assert priority["openCount"] == (19 - index if index < 19 else 57 - index)
        service.quality_decision(doc["id"], row["quality"]["textSha256"], finding["metric"], finding["start"], finding["end"], True, row["chapterIndex"])
        saved.append(finding)
    after = report()
    assert after["summary"]["intentional"] == 57
    assert not any(p["group"] == "Wiederholung" for p in after["summary"]["priorities"])
    assert next(c for c in after["summary"]["cards"] if c["id"] == "repetition")["title"] == "Textduplikate als beabsichtigt markiert"
    if chapter:
        assert service.quality([doc["id"]])["rows"][0]["summary"]["intentional"] == 0
    params = dict(id=doc["id"], textSha256=after["quality"]["textSha256"], chapterIndex=after["chapterIndex"], metric="sentenceRepeat", status="intentional", offset=30)
    page = service.call("quality_findings", params)
    assert page["total"] == 38 and page["offset"] == 30 and len(page["items"]) == 6
    late = page["items"][-1]
    reopened = DesktopService(service.root, seed=False)
    try:
        assert reopened.call("quality_findings", params) == page
        reopened.quality_decision(doc["id"], page["textSha256"], late["metric"], late["start"], late["end"], False, after["chapterIndex"])
        restored = reopened.quality([] if chapter else [doc["id"]], bookId=doc["id"] if chapter else None)["rows"][0]
        priority = next(p for p in restored["summary"]["priorities"] if p["metric"] == "sentenceRepeat")
        assert priority["openCount"] == 1 and priority["evidence"][0]["key"] == late["key"]
        open_page = reopened.call("quality_findings", {**params, "status": "open", "offset": 999})
        assert open_page["offset"] == 0 and open_page["total"] == 1
    finally:
        reopened.executor.shutdown()


def test_complete_index_has_exact_counts_and_unicode_locations():
    text = (("🪶 Eigentlich ging König durch den Wald. Vielleicht war die kleine Reise eigentlich eine große Idee. " + PARAGRAPH + "\n\n") * 40)
    q = analyze(text, DEFAULTS)
    for metric, positions in q["evidenceIndex"].items():
        assert len(positions) == q["evidenceCounts"][metric]
        assert all(0 <= a < b <= len(text) for a, b, _ in positions)
    assert len(q["evidenceIndex"]["fillers"]) > 6
    assert len(q["evidenceIndex"]["trigramRepeat"]) > 16


@pytest.mark.parametrize("change", [
    {"offset": -1}, {"offset": True}, {"limit": 51}, {"limit": 0},
    {"metric": "unknown"}, {"status": "ignored"}, {"textSha256": "stale"},
    {"chapterIndex": True}, {"chapterIndex": 999},
])
def test_findings_api_validates_selection(service, change):
    doc = upload(service, PARAGRAPH * 20)
    row = service.quality([doc["id"]])["rows"][0]
    with pytest.raises(ValueError):
        service.call("quality_findings", {"id": doc["id"], "textSha256": row["quality"]["textSha256"], **change})


@pytest.mark.parametrize("metric,value,unit,title", [
    ("sentenceMean", 24, "Wörter je Satz", "längere Sätze"),
    ("sentenceMean", 5, "Wörter je Satz", "kürzere Sätze"),
    ("mattr", 75, "Wortformen je 100 Wörter", "mehr Wortvielfalt"),
    ("mattr", 15, "Wortformen je 100 Wörter", "weniger Wortvielfalt"),
    ("nearRepeat", 20, "%", "mehr nahe Wortwiederholungen"),
    ("nearRepeat", 0, "%", "weniger nahe Wortwiederholungen"),
])
@pytest.mark.parametrize("baseline", [False, True])
def test_style_explanations_identify_the_actual_measurement_and_reference(metric, value, unit, title, baseline):
    q = analyze(PARAGRAPH * 20, DEFAULTS)
    q["values"].update(sentenceMean=11, mattr=45, nearRepeat=7)
    q["values"][metric] = value
    bands = {"sentenceMean": dict(low=10, median=11, high=12, n=4),
             "mattr": dict(low=40, median=45, high=50, n=4),
             "nearRepeat": dict(low=6, median=7, high=8, n=4)}
    row = dict(id="chapter", chapterIndex=2, quality=q,
               comparison=dict(name="Meine Referenz", bands=bands) if baseline else None)
    summary = summarize(row, peers=bands)
    assert len(summary["deviations"]) == 1
    finding = summary["deviations"][0]
    assert finding["metric"] == metric and finding["value"] == value
    assert finding["band"] == bands[metric] and finding["unit"] == unit
    assert title in finding["explanation"] and "Dieses Kapitel" in finding["explanation"]
    assert ("in deiner Referenz" if baseline else "in den übrigen Kapiteln") in finding["explanation"]
    card = next(c for c in summary["cards"] if c["id"] == "consistency")
    assert card["metric"] == metric and card["status"] == "review" and title in card["title"]
    assert "kein Qualitätsurteil" in card["detail"]
    # A short text, or too few samples, must not receive an assertive explanation.
    short = deepcopy(row)
    short["quality"]["words"] = 200
    assert summarize(short, peers=bands)["deviations"] == []
    for b in bands.values():
        b["n"] = 2 if baseline else 3
    assert summarize(row, peers=bands)["deviations"] == []


def test_chapter_comparison_explains_long_sentences_without_vocabulary_analysis(service):
    short = "Der Morgen ist ruhig und die Sonne scheint. " * 40
    long = "Als die Sonne am Morgen hinter den Bergen aufging, warteten alle Wanderer noch immer auf die verspätete Ankunft ihres Freundes. " * 20
    doc = upload(service, "\n".join(f"Kapitel {i+1}\n{text}" for i, text in enumerate([short] * 4 + [long])))
    doc["settings"]["qualityGroups"] = ["rhythm"]
    chapters = service.quality([], bookId=doc["id"])["rows"]
    row = chapters[-1]
    finding = next(d for d in row["summary"]["deviations"] if d["metric"] == "sentenceMean")
    assert finding["band"]["n"] == 4 and finding["referenceKind"] == "chapters"
    assert finding["value"] > finding["band"]["high"]
    assert row["quality"]["values"]["mattr"] is None
    assert next(c for c in row["summary"]["cards"] if c["id"] == "consistency")["status"] == "review"
