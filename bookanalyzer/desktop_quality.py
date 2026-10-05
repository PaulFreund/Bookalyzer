"""Versioned derived diagnostics. Saved baseline files are never rewritten."""
from __future__ import annotations

import json
from hashlib import sha256

import pandas as pd

from .provenance import sha256_file, write_json
from .quality import analyze, catalog, deltas
from .quality_catalog import GROUPS, VERSION
from .desktop_text import document_text, text_basis, segment_texts
from .quality_comparison import compare_to_reference
from .quality_summary import summarize, peer_bands, decision_key
from .quality_evidence import review_overview, findings_page, indexed


def profile(service, text, settings):
    options = {"language": settings.get("language", "de"),
               "qualityGroups": settings.get("qualityGroups", [g["id"] for g in GROUPS]),
               "longSentenceWords": settings.get("longSentenceWords", 30),
               "textProfile": settings.get("textProfile", "narrative"),
               "longSentenceShare": settings.get("longSentenceShare", 10)}
    key = sha256((VERSION + json.dumps(options, sort_keys=True) + text).encode("utf-8")).hexdigest()
    path = service.root / "quality-cache" / f"{key}.json"
    if path.is_file():
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
            if result.get("cacheKey") == key and result.get("analysis", {}).get("textSha256"):
                return result["analysis"]
        except (ValueError, KeyError):
            pass
    result = analyze(text, options)
    with service.lock:
        write_json(path, {"cacheKey": key, "analysis": result})
    return result


def ready_document(service, identifier):
    doc = service._document(identifier)
    if doc["status"] != "ready":
        raise ValueError("Bitte die Textanalyse zuerst abschließen.")
    return doc


def baseline_profile(service, identifier):
    service._directory(identifier)
    info = next((b for b in service.state["baselines"] if b["id"] == identifier), None)
    if info is None:
        raise ValueError("Baseline nicht gefunden.")
    directory = service.root / "baselines" / identifier
    for filename, expected in info["hashes"].items():
        if sha256_file(directory / filename) != expected:
            raise ValueError("Baseline-Dateien wurden verändert. Bitte eine neue Baseline anlegen.")
    snapshot = json.loads((directory / "snapshot.json").read_text(encoding="utf-8"))
    basis = text_basis(directory)
    result = profile(service, basis["text"], snapshot["settings"])
    result.pop("evidenceIndex", None)
    result["basis"] = {k: basis[k] for k in ("origin", "note")}
    return {**info, "quality": result, "_text": basis["text"], "_settings": snapshot["settings"],
            "derivation": f"Qualitätsmethoden {VERSION}, lokal auf dem unveränderten Baseline-Text berechnet. Der gespeicherte StoryScope-Raum bleibt unverändert."}


def report(service, ids, book_id=None, baseline_id=None):
    if not isinstance(ids, list) or len(ids) > 6 or len(set(ids)) != len(ids):
        raise ValueError("Bitte höchstens sechs verschiedene Texte auswählen.")
    from .desktop_compare import chapter_sections
    baseline = baseline_profile(service, baseline_id) if baseline_id else None
    rows = []
    if book_id:
        doc = ready_document(service, book_id)
        sections = chapter_sections(service, book_id)
        if len(sections) > 400:
            raise ValueError("Das Qualitätslabor unterstützt bis zu 400 Kapitel pro Buch.")
        for section in sections.itertuples():
            index = int(section.chapter_index)
            rows.append(dict(id=f"{doc['id']}:{index}", documentId=doc["id"], chapterIndex=index,
                             title=str(section.chapter_title), color=doc["color"],
                             quality=profile(service, str(section.content), doc["settings"]),
                             _text=str(section.content), series=[]))
    else:
        for identifier in ids:
            doc = ready_document(service, identifier)
            basis = document_text(service, identifier)
            q = profile(service, basis["text"], doc["settings"])
            q["basis"] = {k: basis[k] for k in ("origin", "note")}
            rows.append(dict(id=identifier, documentId=identifier, chapterIndex=None,
                             title=doc["title"], color=doc["color"], quality=q, _text=basis["text"], series=[]))
    peers = peer_bands(rows) if book_id else {}
    for row in rows:
        row["delta"], row["comparison"] = compare_to_reference(service, row["quality"], baseline) if baseline else (None, None)
        doc = service._document(row["documentId"])
        review_overview(row["quality"], row.pop("_text"), doc.get("qualityDecisions", []), row["chapterIndex"])
        row["summary"] = summarize(row, doc.get("qualityDecisions", []), peers.get(row["id"]))
        row["quality"].pop("evidenceIndex", None)
    public_baseline = {k: v for k, v in baseline.items() if not k.startswith("_")} if baseline else None
    return dict(catalog=catalog(), rows=rows, baseline=public_baseline, scope="chapters" if book_id else "documents")


def progression(service, identifier, baseline_id=None):
    doc = ready_document(service, identifier)
    segments = pd.read_parquet(service._directory(identifier) / "segments.parquet")
    if len(segments) > 3000:
        raise ValueError("Bitte höchstens 3.000 Segmente verwenden.")
    reference = baseline_profile(service, baseline_id) if baseline_id else None
    texts = segment_texts(document_text(service, identifier))
    rows = []
    for row, text in zip(segments.itertuples(), texts):
        result = profile(service, text, doc["settings"])
        delta, comparison = compare_to_reference(service, result, reference) if reference else (None, None)
        rows.append(dict(index=int(row.segment_index), title=str(row.chapter_title), words=result["words"],
                          values=result["values"], reasons=result["reasons"], delta=delta, comparison=comparison))
    return rows


def excerpt(service, identifier, start, end, chapter_index=None):
    from .desktop_compare import chapter_sections
    doc = ready_document(service, identifier)
    if chapter_index is None:
        text = document_text(service, identifier)["text"]
    else:
        if type(chapter_index) is not int:
            raise ValueError("Ungültiges Kapitel.")
        sections = chapter_sections(service, identifier)
        rows = sections[sections.chapter_index == chapter_index]
        if rows.empty:
            raise ValueError("Kapitel nicht gefunden.")
        text = str(rows.iloc[0].content)
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
        raise ValueError("Ungültige Fundstelle.")
    return dict(before=text[max(0, start-700):start], text=text[start:min(end, start+4000)],
                 after=text[end:end+700], truncated=end-start > 4000)


def finding_source(service, identifier, chapter_index):
    doc = ready_document(service, identifier)
    if chapter_index is None:
        text = document_text(service, identifier)["text"]
    else:
        from .desktop_compare import chapter_sections
        if type(chapter_index) is not int:
            raise ValueError("Ungültiges Kapitel.")
        rows = chapter_sections(service, identifier)
        rows = rows[rows.chapter_index == chapter_index]
        if rows.empty:
            raise ValueError("Kapitel fehlt.")
        text = str(rows.iloc[0].content)
    return doc, text


def findings(service, identifier, digest, metric, status, offset, limit, chapter_index):
    if (metric is not None and (not isinstance(metric, str) or metric not in {m["id"] for m in catalog()["metrics"]})
            or not isinstance(status, str) or status not in ("all", "open", "intentional")
            or type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50):
        raise ValueError("Ungültige Fundstellenauswahl.")
    doc, text = finding_source(service, identifier, chapter_index)
    q = profile(service, text, doc["settings"])
    if q["textSha256"] != digest:
        raise ValueError("Der Text hat sich verändert. Bitte die Analyse neu laden.")
    return findings_page(q, text, doc.get("qualityDecisions", []), chapter_index, metric, status, offset, limit)


def decision(service, identifier, digest, metric, start, end, intentional, chapter_index):
    if type(intentional) is not bool:
        raise ValueError("Ungültige Entscheidung.")
    if type(start) is not int or type(end) is not int:
        raise ValueError("Ungültige Fundstelle.")
    doc, text = finding_source(service, identifier, chapter_index)
    q = profile(service, text, doc["settings"])
    if q["textSha256"] != digest:
        raise ValueError("Der Text hat sich verändert. Bitte die Analyse neu laden.")
    evidence = next((e for e in indexed(q) if e["metric"] == metric and e["start"] == start and e["end"] == end), None)
    if evidence is None:
        raise ValueError("Fundstelle nicht gefunden.")
    key = decision_key(q, evidence, chapter_index)
    with service.lock:
        decisions = set(doc.get("qualityDecisions", []))
        decisions.add(key) if intentional else decisions.discard(key)
        doc["qualityDecisions"] = sorted(decisions)
        service._persist()
    return dict(key=key, intentional=intentional)
