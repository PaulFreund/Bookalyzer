"""Independent numeric oracles, provenance and actual text-location regressions."""
import base64
import json
import math
from collections import Counter

import pandas as pd
import pytest

from bookanalyzer.desktop import DEFAULTS, DesktopService, validate_settings
from bookanalyzer.provenance import sha256_file, write_json
from bookanalyzer.quality import analyze, deltas, hdd, mattr, mtld, sentence_spans
from bookanalyzer.quality_catalog import CATALOG


def test_mattr_slides_one_token_and_uses_only_full_windows():
    words = ["a", "b", "a", "c", "c", "d", "e"]
    expected = sum(len(set(words[i:i+3])) / 3 for i in range(5)) / 5 * 100
    assert mattr(words, 3) == pytest.approx(expected)
    assert mattr(words, 8) is None
    assert mattr(words[:3], 3) == pytest.approx(200/3)


def test_hdd_matches_exact_hypergeometric_probabilities():
    counts = Counter({"oak": 25, "ash": 12, "elm": 10, "fir": 4})
    expected = sum(1-math.comb(51-f, 42)/math.comb(51, 42) if 51-f >= 42 else 1 for f in counts.values())/42*100
    assert hdd(counts) == pytest.approx(expected, abs=1e-10)
    assert hdd(Counter({str(i): 1 for i in range(42)})) == pytest.approx(100)
    assert hdd(Counter({"a": 42})) == pytest.approx(100/42)
    assert hdd(Counter({"a": 41})) is None


def test_mtld_two_directions_and_undefined_all_unique():
    assert mtld(["a"]*100) == pytest.approx(2)
    assert mtld([str(i) for i in range(100)]) is None
    words = "a b c d e a b a b a c d e f f f".split()
    assert mtld(words) == pytest.approx(mtld(list(reversed(words))))


def test_readability_formula_known_counts_and_unclipped_scales():
    # 100 words, 20 sentences, all 3 letters and one syllable.
    text = ("cat dog cat dog cat. " * 20).strip()
    result = analyze(text, {**DEFAULTS, "language": "en"})
    v = result["values"]
    assert result["words"] == 100
    assert result["sentences"] == 20
    assert v["lix"] == 5
    assert v["rix"] == 0
    assert v["fleschEn"] == pytest.approx(117.16)
    assert v["fkGrade"] == pytest.approx(-1.84)
    assert v["fleschDe"] is None
    assert v["wordLength"] == 3
    assert v["hapax"] == 0
    assert v["simpson"] == pytest.approx(100*(1-(60*59+40*39)/(100*99)), abs=.0001)


def test_unicode_evidence_and_abbreviations_preserve_original_offsets():
    text = "🪶 Dr. König war da. „Vielleicht“, sagte er, „ist das eigentlich klar?“\n\n"
    text += "Vielleicht wurde die Erinnerung geweckt. Eigentlich war der Wald kalt und dunkel. " * 12
    result = analyze(text, DEFAULTS)
    first = next(sentence_spans(text))
    assert text[slice(*first)] == "🪶 Dr. König war da."
    for e in result["evidence"]:
        assert text[e["start"]:e["end"]].startswith(e["text"])
        assert text[e["end"]:e["end"]+90] == e["after"]
    fillers = [e for e in result["evidence"] if e["metric"] == "fillers"]
    assert len(fillers) == 6
    assert result["evidenceCounts"]["fillers"] == 13
    assert result["values"]["passive"] > 0
    assert result["values"]["dialogue"] > 0
    json.dumps(result, allow_nan=False)


def test_empty_short_unknown_language_and_disabled_groups_are_not_zero_scores():
    for text in ("", " \n 123 .", "One sentence."):
        result = analyze(text, DEFAULTS)
        assert all(v is None for v in result["values"].values())
        json.dumps(result, allow_nan=False)
    unknown = analyze("The cat and the dog see the bird. " * 30, {**DEFAULTS, "language": "und"})
    assert unknown["values"]["mattr"] is not None
    assert unknown["values"]["fillers"] is None
    assert unknown["values"]["fleschEn"] is None
    disabled = analyze("I really hear a soft sound. " * 30, {**DEFAULTS, "qualityGroups": []})
    assert all(v is None for v in disabled["values"].values())
    assert disabled["evidence"] == disabled["cadence"] == disabled["keywords"] == []
    assert len(disabled["reasons"]) == len(CATALOG) == 51


def test_repetition_cohesion_and_rhythm_on_controlled_paragraphs():
    paragraph = "Der grüne Wald duftete nach Regen und der warme Wind bewegte leise das hohe Gras."
    result = analyze("\n\n".join([paragraph]*10), DEFAULTS)["values"]
    assert result["sentenceRepeat"] == 90
    assert result["paragraphRepeat"] == 90
    assert result["cohesion"] == 100
    assert result["shifts"] == 0
    assert result["sentenceCV"] == 0
    assert result["rhythmLag"] is None  # correlation of a constant series is undefined
    assert result["rhythmChange"] == 0


def test_deltas_do_not_mix_languages_thresholds_or_versions():
    text = "The cat walks beside a small stream and sees a tiny bird nearby. " * 20
    a = analyze(text, DEFAULTS)
    b = analyze(text, {**DEFAULTS, "longSentenceWords": 40})
    result = deltas(a, b)
    assert result["values"]["mattr"] == 0
    assert result["values"]["longSentences"] is None
    other = analyze(text, {**DEFAULTS, "language": "en"})
    assert all(v is None for v in deltas(a, other)["values"].values())
    other = {**a, "version": "future"}
    assert all(v is None for v in deltas(a, other)["values"].values())


@pytest.mark.parametrize("change", [{"qualityGroups": "all"}, {"qualityGroups": ["wrong"]}, {"qualityGroups": ["style", "style"]}, {"qualityGroups": [True]}, {"longSentenceWords": True}, {"longSentenceWords": 0}, {"longSentenceWords": 90}])
def test_quality_settings_are_validated(change):
    with pytest.raises(ValueError):
        validate_settings(change)


def test_baseline_chapters_legacy_profiles_and_original_excerpts(tmp_path):
    service = DesktopService(tmp_path, seed=False)
    try:
        def upload(name, text):
            doc = service.prepare(name, base64.b64encode(text.encode()).decode(), {**DEFAULTS, "minWords": 100, "targetWords": 200, "maxWords": 300})
            segments = pd.read_parquet(service._directory(doc["id"]) / "segments.parquet")
            service._complete(doc, segments)
            return doc
        text = "Kapitel 1\n" + ("🪶 Eigentlich hörte sie den Wind. Der Wald war kalt. " * 20) + "\nKapitel 2\n" + ("Sie wartete vor der Tür und dachte an den langen Weg nach Hause. " * 20) + "\nKapitel 3\nSie ging."
        reference = upload("Basis.txt", "Kapitel 1\n" + "Die Sonne fiel warm durch das hohe Fenster und sie lächelte. " * 25)
        baseline = service.baseline_create(reference["id"], "Fixierter Text")
        # Emulate an older immutable snapshot with no quality options or summary.
        path = tmp_path / "baselines" / baseline["id"] / "snapshot.json"
        snapshot = json.loads(path.read_text(encoding="utf8"))
        snapshot.pop("qualitySummary")
        snapshot["settings"].pop("qualityGroups")
        snapshot["settings"].pop("longSentenceWords")
        write_json(path, snapshot)
        baseline["hashes"]["snapshot.json"] = sha256_file(path)
        hashes_before = dict(baseline["hashes"])
        doc = upload("Roman.txt", text)
        doc.pop("qualitySummary")  # old analyzed document; local derivation still works
        chapters = service.call("quality", {"ids": [], "bookId": doc["id"], "baselineId": baseline["id"]})
        assert len(chapters["rows"]) == 3
        assert chapters["rows"][0]["quality"]["words"] == 180
        assert all(v is None for v in chapters["rows"][2]["quality"]["values"].values())
        row = chapters["rows"][0]
        evidence = next(e for e in row["quality"]["evidence"] if e["metric"] == "fillers")
        excerpt = service.quality_excerpt(doc["id"], evidence["start"], evidence["end"], row["chapterIndex"])
        assert excerpt["text"] == "Eigentlich"
        report = service.quality([doc["id"]], baselineId=baseline["id"])
        assert len(service.quality_progression(doc["id"], baseline["id"])) == doc["segmentCount"]
        service.remove(reference["id"])
        extra = upload("Extra.txt", "Wind und Wald. " * 100)
        after = service.quality([extra["id"], doc["id"]], baselineId=baseline["id"])
        assert report["rows"][0]["delta"] == after["rows"][1]["delta"]
        assert report["baseline"]["quality"] == after["baseline"]["quality"]
        assert baseline["hashes"] == hashes_before
        for name, digest in hashes_before.items():
            assert sha256_file(tmp_path / "baselines" / baseline["id"] / name) == digest
        service._persist()
        reopened = DesktopService(tmp_path, seed=False)
        try:
            assert reopened.quality([doc["id"]], baselineId=baseline["id"])["rows"][0]["quality"] == report["rows"][0]["quality"]
        finally:
            reopened.executor.shutdown()
        with pytest.raises(ValueError):
            service.quality_excerpt(doc["id"], -1, 4)
        with pytest.raises(ValueError):
            service.quality_excerpt(doc["id"], 0, 3, 999)
        path.write_text("{}", encoding="utf8")
        with pytest.raises(ValueError, match="verändert"):
            service.quality([doc["id"]], baselineId=baseline["id"])
    finally:
        service.executor.shutdown()
