"""One immutable text basis for local metrics; legacy snapshots remain untouched."""
from __future__ import annotations

import json
from hashlib import sha256

import pandas as pd

from .provenance import write_json
from .ingest import WORD_PATTERN


def segment_mappings(text, segments):
    # Use the import tokenizer for positions: numbers also occupy segment space.
    matches = list(WORD_PATTERN.finditer(text))
    offset, start, mappings = 0, 0, []
    for row in segments.itertuples():
        offset += len(WORD_PATTERN.findall(str(row.human_story)))
        end = matches[offset].start() if offset < len(matches) else len(text)
        mappings.append(dict(index=int(row.segment_index), id=str(row.segment_id), start=start, end=end))
        start = end
    return mappings


def text_basis(directory, *, recover_sections=None, persist=False):
    path = directory / "text.json"
    if path.is_file():
        result = json.loads(path.read_text(encoding="utf-8"))
        if sha256(result["text"].encode("utf-8")).hexdigest() != result["sha256"]:
            raise ValueError("Die gespeicherte Textgrundlage wurde verändert.")
        if result.get("version") != 2:
            segments = pd.read_parquet(directory / "segments.parquet").sort_values("segment_index")
            result = {**result, "version": 2, "segments": segment_mappings(result["text"], segments)}
            if persist:
                write_json(path, result)
        return result
    segments = pd.read_parquet(directory / "segments.parquet").sort_values("segment_index")
    section_path = directory / "sections.parquet"
    sections = pd.read_parquet(section_path) if section_path.is_file() else None
    if sections is None and recover_sections:
        try:
            sections = recover_sections()
        except ValueError:
            pass
    origin = "import"
    if sections is not None:
        sections = sections[sections.included.astype(bool)].sort_values("chapter_index")
        text = "\n\n".join(str(t) for t in sections.content)
        expected = [w for t in segments.human_story for w in WORD_PATTERN.findall(str(t))]
        if WORD_PATTERN.findall(text) != expected:
            raise ValueError("Kapitel und Analysesegmente gehören nicht zum selben Text. Bitte neu importieren.")
    else:
        text = "\n\n".join(segments.human_story)
        origin = "legacy_segments"
    result = dict(version=2, text=text, sha256=sha256(text.encode("utf-8")).hexdigest(),
                  origin=origin, segments=segment_mappings(text, segments),
                  note="Absatzgrenzen des Imports bleiben erhalten." if origin == "import" else
                  "Alter Import ohne Originalstruktur. Absatzwerte können Segmentgrenzen enthalten; für verlässliche Absatzvergleiche neu importieren.")
    if persist:
        write_json(path, result)
    return result


def document_text(service, identifier):
    from .desktop_compare import chapter_sections
    return text_basis(service._directory(identifier),
                      recover_sections=lambda: chapter_sections(service, identifier), persist=True)


def segment_texts(basis):
    return [basis["text"][row["start"]:row["end"]] for row in basis["segments"]]
