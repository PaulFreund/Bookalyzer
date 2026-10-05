"""Deterministic, non-overlapping segmentation near natural book boundaries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import pandas as pd

from .config import project_path
from .ingest import SCENE_PATTERN, WORD_PATTERN, count_words, normalize_text
from .provenance import sha256_file, sha256_text, utc_now, write_json


@dataclass(frozen=True)
class TextBlock:
    text: str
    chapter_index: int
    chapter_title: str
    start_position: int
    end_position: int
    boundary_before: str

    @property
    def word_count(self) -> int:
        return count_words(self.text)


def _slice_by_word_count(text: str, maximum: int) -> list[tuple[str, int, int]]:
    """Split a pathological long block without inventing or dropping text."""
    matches = list(WORD_PATTERN.finditer(text))
    if len(matches) <= maximum:
        return [(text, 0, len(text))]
    slices: list[tuple[str, int, int]] = []
    start = 0
    for first in range(0, len(matches), maximum):
        last_index = min(first + maximum, len(matches)) - 1
        next_index = last_index + 1
        end = matches[next_index].start() if next_index < len(matches) else len(text)
        piece = text[start:end].strip()
        leading = len(text[start:end]) - len(text[start:end].lstrip())
        if piece:
            slices.append((piece, start + leading, end))
        start = end
    return slices


def _paragraph_spans(text: str) -> list[tuple[str, int, int]]:
    spans: list[tuple[str, int, int]] = []
    for match in re.finditer(r"(?:^|\n\s*\n)(.*?)(?=\n\s*\n|$)", text, flags=re.DOTALL):
        raw = match.group(1)
        value = raw.strip()
        if not value:
            continue
        offset = raw.find(value)
        start = match.start(1) + offset
        spans.append((value, start, start + len(value)))
    if not spans and text.strip():
        value = text.strip()
        start = text.find(value)
        spans.append((value, start, start + len(value)))
    return spans


def blocks_from_sections(sections: pd.DataFrame, max_words: int) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    for _, section in sections.sort_values("chapter_index").iterrows():
        content = str(section["content"])
        chapter_index = int(section["chapter_index"])
        chapter_title = str(section["chapter_title"])
        first_in_chapter = True
        after_scene = False
        for paragraph, start, end in _paragraph_spans(content):
            if SCENE_PATTERN.match(paragraph):
                after_scene = True
                continue
            boundary = "chapter" if first_in_chapter else "scene" if after_scene else "paragraph"
            slices = _slice_by_word_count(paragraph, max_words)
            for slice_index, (piece, local_start, local_end) in enumerate(slices):
                blocks.append(
                    TextBlock(
                        text=piece,
                        chapter_index=chapter_index,
                        chapter_title=chapter_title,
                        start_position=start + local_start,
                        end_position=start + local_end,
                        boundary_before=boundary if slice_index == 0 else "forced",
                    )
                )
                boundary = "forced"
            first_in_chapter = False
            after_scene = False
    return blocks


def _boundary_bonus(kind: str, target_words: int) -> float:
    """Prefer natural boundaries while still respecting the configured size range."""
    weight = {"chapter": 0.30, "scene": 0.10, "paragraph": 0.0, "forced": -0.10}.get(kind, 0.0)
    return weight * target_words


def _choose_cut(
    blocks: Sequence[TextBlock],
    start: int,
    min_words: int,
    target_words: int,
    max_words: int,
) -> int:
    total = 0
    candidates: list[tuple[float, int, int]] = []
    for index in range(start, len(blocks)):
        total += blocks[index].word_count
        if total > max_words:
            break
        if total >= min_words:
            next_boundary = blocks[index + 1].boundary_before if index + 1 < len(blocks) else "chapter"
            score = abs(total - target_words) - _boundary_bonus(next_boundary, target_words)
            candidates.append((score, abs(total - target_words), index + 1))
    if candidates:
        return min(candidates)[2]
    # Keep a short complete remainder together so the final two ranges can be
    # merged or rebalanced. Emitting one paragraph per segment would preserve
    # text but violate the intended unit of analysis.
    return len(blocks)


def _word_total(blocks: Sequence[TextBlock], start: int, end: int) -> int:
    return sum(block.word_count for block in blocks[start:end])


def partition_blocks(
    blocks: Sequence[TextBlock],
    *,
    min_words: int,
    target_words: int,
    max_words: int,
) -> list[tuple[int, int]]:
    if not 0 < min_words <= target_words <= max_words:
        raise ValueError("Segmentation parameters must satisfy 0 < min <= target <= max")
    if not blocks:
        return []
    cuts = [0]
    while cuts[-1] < len(blocks):
        cuts.append(
            _choose_cut(blocks, cuts[-1], min_words, target_words, max_words)
        )
    ranges = list(zip(cuts[:-1], cuts[1:]))

    if len(ranges) >= 2 and _word_total(blocks, *ranges[-1]) < min_words:
        previous_start = ranges[-2][0]
        final_end = ranges[-1][1]
        combined = _word_total(blocks, previous_start, final_end)
        if combined <= max_words:
            ranges[-2:] = [(previous_start, final_end)]
        else:
            feasible: list[tuple[float, int, int]] = []
            for cut in range(previous_start + 1, final_end):
                left = _word_total(blocks, previous_start, cut)
                right = _word_total(blocks, cut, final_end)
                if min_words <= left <= max_words and min_words <= right <= max_words:
                    score = abs(left - target_words) + abs(right - target_words)
                    score -= _boundary_bonus(blocks[cut].boundary_before, target_words)
                    feasible.append((score, abs(left - right), cut))
            if feasible:
                cut = min(feasible)[2]
                ranges[-2:] = [(previous_start, cut), (cut, final_end)]
    return ranges


def _join_segment_blocks(blocks: Sequence[TextBlock]) -> str:
    return normalize_text("\n\n".join(block.text for block in blocks))


def segment_book(
    sections: pd.DataFrame,
    *,
    target_words: int = 5000,
    min_words: int = 3000,
    max_words: int = 7000,
) -> list[dict[str, Any]]:
    included = sections[sections["included"].astype(bool)].sort_values("chapter_index")
    if included.empty:
        return []
    blocks = blocks_from_sections(included, max_words=max_words)
    ranges = partition_blocks(
        blocks,
        min_words=min_words,
        target_words=target_words,
        max_words=max_words,
    )
    book_id = str(included.iloc[0]["book_id"])
    book_title = str(included.iloc[0]["book_title"])
    language = str(included.iloc[0]["language"])
    source_file = str(included.iloc[0]["source_file"])
    results: list[dict[str, Any]] = []
    for segment_index, (start, end) in enumerate(ranges):
        selected = blocks[start:end]
        text = _join_segment_blocks(selected)
        text_hash = sha256_text(text)
        chapter_indices = [block.chapter_index for block in selected]
        chapter_titles = list(dict.fromkeys(block.chapter_title for block in selected))
        segment_id = f"{book_id}-s{segment_index + 1:04d}-{text_hash[:12]}"
        results.append(
            {
                "title": f"{book_title} — Segment {segment_index + 1:03d}",
                "human_story": text,
                "book_id": book_id,
                "book_title": book_title,
                "source_file": source_file,
                "language": language,
                "chapter_index": min(chapter_indices),
                "chapter_end_index": max(chapter_indices),
                "chapter_title": " | ".join(chapter_titles),
                "segment_index": segment_index,
                "segment_id": segment_id,
                "word_count": count_words(text),
                "text_sha256": text_hash,
                "start_position": selected[0].start_position,
                "end_position": selected[-1].end_position,
                "boundary_start": selected[0].boundary_before,
                "boundary_end": blocks[end].boundary_before if end < len(blocks) else "book_end",
            }
        )
    return results


def _word_sequence(values: Iterable[str]) -> list[str]:
    sequence: list[str] = []
    for value in values:
        sequence.extend(match.group(0) for match in WORD_PATTERN.finditer(value))
    return sequence


def assert_no_text_loss(sections: pd.DataFrame, segments: pd.DataFrame) -> None:
    for book_id, book_sections in sections[sections["included"].astype(bool)].groupby("book_id"):
        expected = _word_sequence(book_sections.sort_values("chapter_index")["content"])
        book_segments = segments[segments["book_id"] == book_id].sort_values("segment_index")
        actual = _word_sequence(book_segments["human_story"])
        if expected != actual:
            mismatch = next(
                (index for index, pair in enumerate(zip(expected, actual)) if pair[0] != pair[1]),
                min(len(expected), len(actual)),
            )
            raise RuntimeError(
                f"Text loss or reordering detected for {book_id} at word {mismatch}; "
                f"expected {len(expected)} words, got {len(actual)}"
            )


def write_preview(
    segments: pd.DataFrame,
    processed_dir: str | Path,
    parameters: dict[str, int],
) -> tuple[Path, Path]:
    output = project_path(processed_dir)
    preview_columns = [
        "book_id",
        "book_title",
        "segment_index",
        "segment_id",
        "chapter_index",
        "chapter_end_index",
        "chapter_title",
        "start_position",
        "end_position",
        "word_count",
        "boundary_start",
        "boundary_end",
        "text_sha256",
    ]
    csv_path = output / "segment_preview.csv"
    markdown_path = output / "segment_preview.md"
    segments[preview_columns].to_csv(csv_path, index=False)
    lines = [
        "# Segmentierungsvorschau",
        "",
        "Vor der externen Merkmalsextraktion manuell prüfen. Die Vorschau enthält keinen Buchtext.",
        "",
        f"Parameter: `{parameters}`",
        "",
        "| Buch | Segment | Kapitel | Wörter | Startgrenze | Endgrenze |",
        "|---|---:|---|---:|---|---|",
    ]
    for row in segments[preview_columns].itertuples(index=False):
        lines.append(
            f"| {row.book_title} | {row.segment_index + 1} | "
            f"{row.chapter_index}–{row.chapter_end_index} ({row.chapter_title}) | "
            f"{row.word_count} | {row.boundary_start} | {row.boundary_end} |"
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path, markdown_path


def segment_books(
    sections_path: str | Path = "data/processed/book_sections.parquet",
    output_path: str | Path = "data/processed/book_segments.parquet",
    *,
    target_words: int = 5000,
    min_words: int = 3000,
    max_words: int = 7000,
    respect_chapters: bool = False,
) -> pd.DataFrame:
    source = project_path(sections_path)
    sections = pd.read_parquet(source)
    rows: list[dict[str, Any]] = []
    for _, book_sections in sections.groupby("book_id", sort=True):
        groups = [part for _, part in book_sections.groupby("chapter_index", sort=True)] if respect_chapters else [book_sections]
        book_rows = []
        for part in groups:
            book_rows.extend(segment_book(
                part,
                target_words=target_words,
                min_words=min_words,
                max_words=max_words,
            ))
        for index, row in enumerate(book_rows):
            row["segment_index"] = index
            row["segment_id"] = f"{row['book_id']}-s{index + 1:04d}-{row['text_sha256'][:12]}"
            row["title"] = f"{row['book_title']} — Segment {index + 1:03d}"
        rows.extend(book_rows)
    if not rows:
        raise RuntimeError("No segments were produced")
    segments = pd.DataFrame(rows).sort_values(["book_id", "segment_index"]).reset_index(drop=True)
    segments.insert(0, "prompt_id", range(1, len(segments) + 1))
    if segments["title"].duplicated().any() or segments["segment_id"].duplicated().any():
        raise RuntimeError("Segment titles and IDs must be unique")
    assert_no_text_loss(sections, segments)
    output = project_path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    segments.to_parquet(output, index=False)
    write_preview(
        segments,
        output.parent,
        {"min_words": min_words, "target_words": target_words, "max_words": max_words},
    )
    return segments


def approve_segments(
    segments_path: str | Path = "data/processed/book_segments.parquet",
    approval_path: str | Path = "data/processed/segment_approval.json",
    *,
    approver: str,
    note: str = "",
) -> Path:
    if not approver.strip():
        raise ValueError("An approver name is required")
    segments = project_path(segments_path)
    frame = pd.read_parquet(segments, columns=["book_id", "segment_id", "word_count"])
    payload = {
        "schema_version": 1,
        "approved_at_utc": utc_now(),
        "approver": approver.strip(),
        "note": note,
        "segments_path": str(segments),
        "segments_sha256": sha256_file(segments),
        "segment_count": int(len(frame)),
        "book_count": int(frame["book_id"].nunique()),
    }
    return write_json(project_path(approval_path), payload)


def assert_segments_approved(
    segments_path: str | Path = "data/processed/book_segments.parquet",
    approval_path: str | Path = "data/processed/segment_approval.json",
) -> dict[str, Any]:
    import json

    segments = project_path(segments_path)
    approval = project_path(approval_path)
    if not approval.is_file():
        raise RuntimeError(
            "Segment preview has not been approved. Review data/processed/segment_preview.md "
            "and run approve-segments before external extraction."
        )
    with approval.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    current_hash = sha256_file(segments)
    if payload.get("segments_sha256") != current_hash:
        raise RuntimeError(
            "Segment data changed after approval. Review and approve the current preview again."
        )
    return payload
