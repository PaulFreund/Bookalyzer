from __future__ import annotations

from pathlib import Path

import pandas as pd

from bookanalyzer.plots import plot_book_rarity
from bookanalyzer.rarity import build_reference
from bookanalyzer.report import (
    analyze_books_internal,
    generate_internal_report,
    generate_report,
)


def _rarity_rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "book_id": ["a", "a", "b", "b"],
            "book_title": ["Alpha", "Alpha", "Beta", "Beta"],
            "segment_index": [0, 1, 0, 1],
            "segment_id": ["a1", "a2", "b1", "b2"],
            "word_count": [5000] * 4,
            "feature_set": ["full_304"] * 4,
            "raw_rarity": [1.0, 2.0, 3.0, 4.0],
            "rarity_percentile": [0.1, 0.3, 0.6, 0.8],
            "nearest_source_counts": ["{}"] * 4,
            "internal_raw_rarity": [1.0] * 4,
            "internal_rarity_percentile": [0.25, 0.5, 0.75, 1.0],
            "internal_k": [3] * 4,
            "internal_neighbor_book_counts": ["{}"] * 4,
            "extraction_model": ["fixture"] * 4,
            "run_id": ["fixture"] * 4,
            "chapter_index": [0, 1, 0, 1],
        }
    )


def test_plot_summary_matches_result_table(tmp_path: Path) -> None:
    frame = _rarity_rows()
    summary = plot_book_rarity(
        frame,
        png_path=tmp_path / "plot.png",
        svg_path=tmp_path / "plot.svg",
    ).set_index("book_title")
    assert summary.loc["Alpha", "mean"] == frame.loc[frame.book_title == "Alpha", "rarity_percentile"].mean()
    assert summary.loc["Beta", "median"] == frame.loc[frame.book_title == "Beta", "rarity_percentile"].median()
    assert (tmp_path / "plot.png").is_file()
    assert (tmp_path / "plot.svg").is_file()


def test_report_regenerates_entirely_from_cached_data(tmp_path: Path, tiny_reference) -> None:
    artifacts = build_reference(
        feature_set="full_304",
        reference_dir=tiny_reference["reference"],
        cache_dir=tiny_reference["cache"],
        source_order=["human"],
    )
    feature_rows = []
    for index, base in enumerate(tiny_reference["rows"][:2] * 2):
        row = dict(base)
        row.update(
            {
                "book_id": "a" if index < 2 else "b",
                "book_title": "Alpha" if index < 2 else "Beta",
                "language": "en",
                "segment_index": index % 2,
                "segment_id": f"segment-{index}",
                "word_count": 5000,
                "extraction_model": "fixture",
            }
        )
        feature_rows.append(row)
    features_path = tmp_path / "book_features.parquet"
    pd.DataFrame(feature_rows).to_parquet(features_path, index=False)
    rarity_path = tmp_path / "book_rarity.parquet"
    _rarity_rows().to_parquet(rarity_path, index=False)
    output = tmp_path / "outputs"
    manifest = generate_report(
        rarity_path=rarity_path,
        book_features_path=features_path,
        taxonomy_path=tiny_reference["reference"] / "taxonomy.json",
        cache_dir=tiny_reference["cache"],
        output_dir=output,
    )
    assert manifest["books"] == 2
    assert (output / "report" / "methods.md").is_file()
    assert (output / "figures" / "book_rarity_violin.png").is_file()
    assert (output / "figures" / "book_distance_matrix.svg").is_file()


def test_internal_report_does_not_require_external_reference_cache(tmp_path: Path, tiny_reference) -> None:
    feature_rows = []
    for index, base in enumerate(tiny_reference["rows"][:2] * 2):
        row = dict(base)
        row.update(
            {
                "book_id": "monster",
                "book_title": "Monster",
                "chapter_index": index,
                "segment_index": index,
                "segment_id": f"segment-{index}",
                "word_count": 5000,
                "extraction_provider": "codex-cli",
                "extraction_model": "fixture-codex",
            }
        )
        feature_rows.append(row)
    features_path = tmp_path / "book_features.parquet"
    pd.DataFrame(feature_rows).to_parquet(features_path, index=False)
    output = tmp_path / "outputs"

    scored = analyze_books_internal(
        book_features_path=features_path,
        taxonomy_path=tiny_reference["reference"] / "taxonomy.json",
        output_dir=output,
        feature_set="full_304",
        backend="numpy",
    )
    manifest = generate_internal_report(
        rarity_path=output / "data" / "codex_internal_segment_rarity.parquet",
        book_features_path=features_path,
        taxonomy_path=tiny_reference["reference"] / "taxonomy.json",
        output_dir=output,
    )

    assert len(scored) == 4
    assert manifest["external_storyscope_percentile"] is False
    assert (output / "figures" / "codex_internal_rarity_violin.png").is_file()
    assert (output / "figures" / "codex_internal_rarity_by_segment.svg").is_file()
    assert (output / "figures" / "codex_segment_distance_matrix.png").is_file()
