from __future__ import annotations

from pathlib import Path

import pandas as pd

from bookanalyzer.ingest import count_words
from bookanalyzer.segment import assert_no_text_loss, segment_book, segment_books


def _sections() -> pd.DataFrame:
    rows = []
    for chapter in range(3):
        paragraphs = []
        for paragraph in range(6):
            paragraphs.append(
                " ".join(f"c{chapter}p{paragraph}w{word}" for word in range(4))
            )
        rows.append(
            {
                "book_id": "book-1",
                "book_title": "Book One",
                "source_file": "fixture.txt",
                "language": "en",
                "chapter_index": chapter,
                "chapter_title": f"Chapter {chapter + 1}",
                "included": True,
                "content": "\n\n".join(paragraphs),
            }
        )
    return pd.DataFrame(rows)


def test_segmentation_is_non_overlapping_lossless_and_bounded() -> None:
    sections = _sections()
    rows = segment_book(sections, min_words=16, target_words=24, max_words=32)
    segments = pd.DataFrame(rows)
    assert len(segments) >= 2
    assert all(value <= 32 for value in segments["word_count"])
    assert_no_text_loss(sections, segments)
    assert sum(segments["word_count"]) == sum(count_words(text) for text in sections["content"])


def test_segment_ids_and_prompt_ids_are_stable(tmp_path: Path) -> None:
    sections_path = tmp_path / "book_sections.parquet"
    output_path = tmp_path / "book_segments.parquet"
    _sections().to_parquet(sections_path, index=False)
    first = segment_books(
        sections_path,
        output_path,
        min_words=16,
        target_words=24,
        max_words=32,
    )
    second = segment_books(
        sections_path,
        output_path,
        min_words=16,
        target_words=24,
        max_words=32,
    )
    assert first["segment_id"].tolist() == second["segment_id"].tolist()
    assert first["prompt_id"].tolist() == second["prompt_id"].tolist()
    assert first["title"].is_unique


def test_short_final_chapter_is_rebalanced_not_split_into_paragraphs() -> None:
    rows = []
    for chapter, paragraph_count in ((0, 6), (1, 3)):
        paragraphs = [
            " ".join(f"c{chapter}p{paragraph}w{word}" for word in range(4))
            for paragraph in range(paragraph_count)
        ]
        rows.append(
            {
                "book_id": "short-tail",
                "book_title": "Short Tail",
                "source_file": "fixture.txt",
                "language": "en",
                "chapter_index": chapter,
                "chapter_title": f"Chapter {chapter + 1}",
                "included": True,
                "content": "\n\n".join(paragraphs),
            }
        )
    sections = pd.DataFrame(rows)
    segments = pd.DataFrame(
        segment_book(sections, min_words=12, target_words=20, max_words=24)
    )
    assert len(segments) == 2
    assert segments["word_count"].min() >= 12
    assert segments["word_count"].max() <= 24
    assert_no_text_loss(sections, segments)
