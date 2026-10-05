"""User-facing invariants from the quality review, with independent expected results."""
import base64
import json
from statistics import median

import pandas as pd
import pytest

from bookanalyzer.desktop import DEFAULTS, DesktopService, surface_metrics, validate_settings
from bookanalyzer.quality import analyze, WORD
from bookanalyzer.provenance import sha256_file


@pytest.fixture
def service(tmp_path):
    instance = DesktopService(tmp_path, seed=False)
    yield instance
    instance.executor.shutdown()


def upload(service, text, **settings):
    doc = service.prepare("Text.txt", base64.b64encode(text.encode()).decode(), {**DEFAULTS, **settings})
    service._complete(doc, pd.read_parquet(service._directory(doc["id"])/"segments.parquet"))
    return doc


def test_all_views_share_dialogue_sentence_and_vocabulary_counts():
    text = '„Das war ein langer Tag.“ Sie schloss die Tür. ' * 15
    surface = surface_metrics(text)
    quality = analyze(text, DEFAULTS)
    assert surface["sentences"] == quality["sentences"] == 30
    assert surface["sentenceMean"] == quality["values"]["sentenceMean"] == 4.5
    assert surface["vocabulary"] == quality["values"]["mattr"]
    assert surface["dialogue"] == quality["values"]["dialogue"]


def test_full_text_is_invariant_to_forced_segmentation_and_baseline_keeps_original(service):
    text = "Der Wind strich durch das alte Haus. " * 100
    docs = [upload(service, text, minWords=100, targetWords=limit, maxWords=limit) for limit in (100, 1000)]
    assert docs[0]["segmentCount"] == 7
    assert docs[1]["segmentCount"] == 1
    assert docs[0]["metrics"] == docs[1]["metrics"]
    rows = service.quality([d["id"] for d in docs])["rows"]
    assert rows[0]["quality"]["values"] == rows[1]["quality"]["values"]
    assert rows[0]["quality"]["paragraphs"] == 1
    assert rows[0]["quality"]["sentences"] == 100
    assert rows[0]["quality"]["values"]["cohesion"] is None
    assert "".join(service.segment(docs[0]["id"], i)["text"] for i in range(7)) == text.strip()
    baseline = service.baseline_create(docs[0]["id"], "Original")
    assert "text.json" in baseline["hashes"]
    frozen = {name: sha256_file(service.root/"baselines"/baseline["id"]/name) for name in baseline["hashes"]}
    service.remove(docs[0]["id"])
    report = service.quality([docs[1]["id"]], baselineId=baseline["id"])
    assert report["rows"][0]["delta"]["values"]["sentenceMean"] == 0
    assert report["baseline"]["quality"]["paragraphs"] == 1
    assert all(sha256_file(service.root/"baselines"/baseline["id"]/name) == value for name,value in frozen.items())


def test_numeric_segments_do_not_duplicate_or_steal_original_text(service):
    text = ("Wort "*100).strip() + "\n\n" + ("1234 "*100).strip()
    doc = upload(service, text, minWords=100, targetWords=100, maxWords=100)
    pieces = [service.segment(doc["id"], index)["text"] for index in range(2)]
    assert "".join(pieces) == text.strip()
    assert "1234" not in pieces[0]
    assert pieces[1].strip() == ("1234 "*100).strip()
    assert analyze(pieces[1], DEFAULTS)["words"] == 0


def test_reference_uses_median_of_equal_length_nonoverlapping_windows(service):
    paragraphs = ["Sonne Wind Wald Wolke Regen. "*20, "Ein alter Baum steht neben dem Haus. "*20,
                  "Weit hinter dem hohen Berg erscheint langsam die helle Sonne. "*20,
                  "Hier bleiben wir. "*60]
    reference = upload(service, "\n\n".join(paragraphs))
    target = upload(service, "Die leise Katze schleicht durchs Haus. "*20)
    baseline = service.baseline_create(reference["id"], "Gleich lange Ausschnitte")
    report = service.quality([target["id"]], baselineId=baseline["id"])
    row = report["rows"][0]
    text = json.loads((service._directory(reference["id"])/"text.json").read_text(encoding="utf8"))["text"]
    tokens=list(WORD.finditer(text))
    n=row["quality"]["words"]
    count=min(9,len(tokens)//n)
    starts=[round(i*(len(tokens)-n)/(count-1)) for i in range(count)]
    expected=median(analyze(text[tokens[i].start():tokens[i+n-1].end()],DEFAULTS)["values"]["entropy"] for i in starts)
    assert row["comparison"]["windows"] == count
    assert row["comparison"]["words"] == n
    assert row["comparison"]["values"]["entropy"] == pytest.approx(expected, abs=.0001)
    assert row["delta"]["values"]["entropy"] == pytest.approx(row["quality"]["values"]["entropy"]-expected,abs=.0001)
    assert row["comparison"]["bands"]["entropy"]["n"] >= 3
    assert "_text" not in report["baseline"]


def test_short_reference_and_language_mismatch_do_not_create_misleading_deltas(service):
    reference = upload(service, "Wind und Regen ziehen durch das Land. "*20)
    target = upload(service, "Das Licht fällt warm auf den alten Tisch. "*90)
    baseline=service.baseline_create(reference["id"], "Kurz")
    row=service.quality([target["id"]],baselineId=baseline["id"])["rows"][0]
    assert row["delta"]["values"]["entropy"] is None
    assert row["delta"]["values"]["hapax"] is None
    assert "kürzer" in row["delta"]["reasons"]["entropy"]
    assert row["comparison"]["bands"] == {}
    english=upload(service,"The cat returns home in the rain. "*15, language="en")
    row=service.quality([english["id"]],baselineId=baseline["id"])["rows"][0]
    assert all(v is None for v in row["delta"]["values"].values())
    assert row["comparison"]["bands"] == {}


def test_intentional_findings_are_scoped_persisted_and_do_not_change_measurements(service):
    doc=upload(service,"Der Wind strich durch das alte Haus. "*100)
    first=service.quality([doc["id"]])["rows"][0]
    e=first["summary"]["priorities"][0]["evidence"][0]
    params=dict(id=doc["id"],textSha256=first["quality"]["textSha256"],metric=e["metric"],start=e["start"],end=e["end"],intentional=True)
    service.call("quality_decision",params)
    after=service.quality([doc["id"]])["rows"][0]
    assert after["quality"]["values"] == first["quality"]["values"]
    assert after["summary"]["intentional"] == 1
    assert all(e["key"] != example["key"] for p in after["summary"]["priorities"] for example in p["evidence"])
    reopened=DesktopService(service.root,seed=False)
    try:
        assert reopened.quality([doc["id"]])["rows"][0]["summary"]["intentional"] == 1
    finally:
        reopened.executor.shutdown()
    with pytest.raises(ValueError):
        service.call("quality_decision",{**params,"textSha256":"stale"})
    service.call("quality_decision",{**params,"intentional":False})
    assert service.quality([doc["id"]])["rows"][0]["summary"]["intentional"] == 0


def test_old_document_metrics_migrate_but_frozen_baseline_is_not_rewritten(service):
    doc=upload(service,'„Das war ein langer Tag.“ Sie schloss die Tür. '*50)
    baseline=service.baseline_create(doc["id"],"Alt")
    doc.pop("localMetricsVersion")
    doc["metrics"]["sentenceMean"]=900
    service._persist()
    before=sha256_file(service.root/"baselines"/baseline["id"]/"snapshot.json")
    reopened=DesktopService(service.root,seed=False)
    try:
        assert reopened._document(doc["id"])["metrics"]["sentenceMean"] == 4.5
        assert sha256_file(service.root/"baselines"/baseline["id"]/"snapshot.json") == before
    finally:
        reopened.executor.shutdown()


def test_legacy_baseline_without_original_paragraphs_suppresses_structural_deltas(service):
    doc = upload(service, "Der Wind strich durch das alte Haus. "*100, minWords=100, targetWords=100, maxWords=100)
    baseline = service.baseline_create(doc["id"], "Altes Format")
    directory = service.root/"baselines"/baseline["id"]
    # Reproduce an older saved baseline, which stored only segments.
    for name in ("text.json", "sections.parquet"):
        (directory/name).unlink()
        del baseline["hashes"][name]
    report = service.quality([doc["id"]], baselineId=baseline["id"])
    row = report["rows"][0]
    assert report["baseline"]["quality"]["basis"]["origin"] == "legacy_segments"
    for metric in ("paragraphMean", "paragraphCV", "paragraphRepeat", "cohesion", "shifts"):
        assert row["delta"]["values"][metric] is None
        assert metric not in row["comparison"]["bands"]
    assert row["delta"]["values"]["sentenceMean"] is not None
    assert not (directory/"text.json").exists(), "Deriving legacy values must not rewrite a frozen reference"


@pytest.mark.parametrize("text, settings", [
    ("Der Wind strich durch das alte Haus. "*25, {}),
    ("Der Wind strich durch das alte Haus. "*80, {"qualityGroups": []}),
])
def test_short_or_disabled_analyses_do_not_give_reassuring_quality_cards(service, text, settings):
    doc = upload(service, text, **settings)
    row = service.quality([doc["id"]])["rows"][0]
    assert all(card["status"] == "unknown" for card in row["summary"]["cards"])
    assert all("eingehalten" not in card["title"] for card in row["summary"]["cards"])


def test_consistency_requires_comparable_measurements_and_priorities_cover_different_issues(service):
    text = ("Eigentlich wurde der alte Baum gefällt, weil der Wind stark war, obwohl der Garten geschützt lag, und niemand hatte damit gerechnet, selbst die Nachbarn nicht. "*70)
    reference = upload(service, text)
    baseline = service.baseline_create(reference["id"], "Referenz")
    target = upload(service, text[:len(text)//4], qualityGroups=["style"])
    row = service.quality([target["id"]], baselineId=baseline["id"])["rows"][0]
    assert row["comparison"]["bands"], "Other style bands exist but cannot justify consistency"
    assert next(c for c in row["summary"]["cards"] if c["id"] == "consistency")["status"] == "unknown"
    row = service.quality([reference["id"]])["rows"][0]
    groups = [p["group"] for p in row["summary"]["priorities"]]
    assert len(groups) == len(set(groups)) == 3


@pytest.mark.parametrize("options", [{"textProfile":"invalid"},{"longSentenceShare":True},{"longSentenceShare":-1},{"longSentenceShare":101}])
def test_writing_goals_are_validated(options):
    with pytest.raises(ValueError):
        validate_settings(options)
