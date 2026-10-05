"""Book scoring and report generation from cached feature artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from .config import project_path
from .feature_matrix import (
    canonicalize_feature_frame,
    invalid_feature_cells,
    load_taxonomy,
    resolve_feature_set,
)
from .paper_encoder import PaperEncoder
from .plots import (
    plot_book_distance_matrix,
    plot_book_rarity,
    plot_internal_book_rarity,
    plot_internal_rarity_sequence,
    plot_rarity_sequence,
    plot_segment_distance_matrix,
)
from .provenance import (
    build_run_manifest,
    new_run_id,
    utc_now,
    write_json,
)
from .rarity import (
    load_reference,
    score_against_reference,
    score_internal_leave_one_out,
    transform_with_reference,
)


def _book_internal_space(
    features: pd.DataFrame,
    *,
    taxonomy_path: str | Path,
    feature_set: str,
) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame, PaperEncoder, StandardScaler]:
    _, specs = load_taxonomy(taxonomy_path)
    feature_ids = resolve_feature_set(feature_set, specs)
    normalized, decisions = canonicalize_feature_frame(features, specs, feature_ids)
    incompatible = invalid_feature_cells(normalized, specs, feature_ids)
    if incompatible:
        raise ValueError(
            f"Book features contain {len(incompatible)} values outside the taxonomy; "
            "the internal analysis was not generated."
        )
    encoder = PaperEncoder(specs, feature_ids)
    encoded = encoder.fit_transform(normalized)
    scaler = StandardScaler()
    standardized = scaler.fit_transform(encoded).astype(np.float32, copy=False)
    return normalized, standardized, decisions, encoder, scaler


def analyze_books(
    *,
    book_features_path: str | Path = "data/features/book_features.parquet",
    taxonomy_path: str | Path = "data/reference/storyscope/taxonomy.json",
    cache_dir: str | Path = "data/cache",
    output_dir: str | Path = "outputs",
    feature_set: str = "public_nonstyle_265",
    k: int = 25,
    backend: str = "auto",
    tie_method: str = "right",
) -> pd.DataFrame:
    feature_path = project_path(book_features_path)
    features = pd.read_parquet(feature_path)
    artifacts = load_reference(
        cache_dir=cache_dir,
        taxonomy_path=taxonomy_path,
        feature_set=feature_set,
    )
    _, specs = load_taxonomy(taxonomy_path)
    normalized, decisions = canonicalize_feature_frame(features, specs, artifacts.feature_ids)
    incompatible = invalid_feature_cells(normalized, specs, artifacts.feature_ids)
    if incompatible:
        raise ValueError(
            f"Book features contain {len(incompatible)} values outside the taxonomy; "
            "external results are not scored."
        )
    output = project_path(output_dir)
    data_dir = output / "data"
    report_dir = output / "report"
    data_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    decisions.to_parquet(data_dir / "book_feature_normalization.parquet", index=False)
    reference_rarity_path = project_path(cache_dir) / "reference_raw_rarity.npy"
    if not reference_rarity_path.is_file():
        raise FileNotFoundError(
            "Reference rarity distribution is missing; complete reproduce-figure5 first."
        )
    reference_rarity = np.load(reference_rarity_path, allow_pickle=False)
    scored, scoring_metrics = score_against_reference(
        normalized,
        artifacts,
        reference_rarity=reference_rarity,
        k=k,
        backend=backend,
        tie_method=tie_method,
    )
    standardized = transform_with_reference(normalized, artifacts)
    if len(scored) >= 2:
        scored = score_internal_leave_one_out(scored, standardized, k=k, backend=backend)
    else:
        scored["internal_raw_rarity"] = np.nan
        scored["internal_rarity_percentile"] = np.nan
        scored["internal_k"] = 0
        scored["internal_neighbor_book_counts"] = "{}"
    run_id = new_run_id("book-rarity")
    scored["run_id"] = run_id
    central_columns = [
        "book_id",
        "book_title",
        "chapter_index",
        "chapter_title",
        "segment_index",
        "segment_id",
        "word_count",
        "feature_set",
        "raw_rarity",
        "rarity_percentile",
        "nearest_source_counts",
        "internal_raw_rarity",
        "internal_rarity_percentile",
        "internal_k",
        "internal_neighbor_book_counts",
        "extraction_model",
        "run_id",
    ]
    available_columns = [column for column in central_columns if column in scored.columns]
    result = scored[available_columns].copy()
    parquet_path = data_dir / "book_segment_rarity.parquet"
    csv_path = data_dir / "book_segment_rarity.csv"
    result.to_parquet(parquet_path, index=False)
    result.to_csv(csv_path, index=False)
    manifest = build_run_manifest(
        run_id=run_id,
        command="rarity",
        parameters={
            **scoring_metrics,
            "internal_reference": "all other supplied book segments",
        },
        inputs=[feature_path, reference_rarity_path, project_path(cache_dir) / "reference_matrix.npy"],
        outputs=[parquet_path, csv_path],
    )
    write_json(report_dir / f"{run_id}.manifest.json", manifest)
    return result


def generate_report(
    *,
    rarity_path: str | Path = "outputs/data/book_segment_rarity.parquet",
    book_features_path: str | Path = "data/features/book_features.parquet",
    taxonomy_path: str | Path = "data/reference/storyscope/taxonomy.json",
    cache_dir: str | Path = "data/cache",
    output_dir: str | Path = "outputs",
) -> dict[str, Any]:
    output = project_path(output_dir)
    data_dir = output / "data"
    figures_dir = output / "figures"
    report_dir = output / "report"
    for directory in (data_dir, figures_dir, report_dir):
        directory.mkdir(parents=True, exist_ok=True)
    results = pd.read_parquet(project_path(rarity_path))
    summary = plot_book_rarity(
        results,
        png_path=figures_dir / "book_rarity_violin.png",
        svg_path=figures_dir / "book_rarity_violin.svg",
    )
    summary.to_csv(data_dir / "book_rarity_summary.csv", index=False)
    plot_rarity_sequence(
        results,
        png_path=figures_dir / "rarity_by_segment.png",
        svg_path=figures_dir / "rarity_by_segment.svg",
    )
    rarest = results.sort_values("rarity_percentile", ascending=False).groupby("book_id").head(5)
    rarest.to_csv(data_dir / "rarest_segments.csv", index=False)

    features = pd.read_parquet(project_path(book_features_path))
    artifacts = load_reference(cache_dir=cache_dir, taxonomy_path=taxonomy_path)
    standardized = transform_with_reference(features, artifacts)
    distance_frame = plot_book_distance_matrix(
        features.reset_index(drop=True),
        standardized,
        png_path=figures_dir / "book_distance_matrix.png",
        svg_path=figures_dir / "book_distance_matrix.svg",
    )
    distance_frame.to_csv(data_dir / "book_distance_matrix.csv")

    reproduction_metrics_path = project_path("reproduction/metrics.json")
    reproduction = None
    if reproduction_metrics_path.is_file():
        with reproduction_metrics_path.open("r", encoding="utf-8") as handle:
            reproduction = json.load(handle)
    feature_set = str(results["feature_set"].iloc[0])
    languages = sorted(features["language"].dropna().astype(str).unique()) if "language" in features else []
    lines = [
        "# Bookalyzer methods and results",
        "",
        "## Interpretation",
        "",
        "These values measure statistical rarity in a StoryScope-derived feature space. They are not "
        "quality scores, plagiarism evidence, or judgments of originality.",
        "",
        "## Method",
        "",
        f"- Unit of analysis: {len(results)} non-overlapping novel segments.",
        f"- Feature set: `{feature_set}`.",
        "- External reference: pooled StoryScope train + validation features.",
        "- Encoding: taxonomy-fixed one-hot, multi-hot, ordinal order, and numeric scale values.",
        "- Standardization: fitted only on StoryScope train + validation.",
        "- Rarity: mean exact Euclidean distance to 25 nearest reference stories.",
        "- Percentile: right-continuous empirical CDF of reference rarity.",
        "- Solid violin mark: mean; dashed mark: median.",
        "",
        "## Methodological limits",
        "",
        "StoryScope analyzed complete short stories; applying it to novel segments is a documented "
        "methodological adaptation.",
    ]
    if languages and any(language.lower() not in {"en", "eng", "english"} for language in languages):
        lines.extend(
            [
                "",
                "The external corpus is English. Non-English external rarity is exploratory; the "
                "output therefore also includes a language-consistent internal leave-one-out rarity.",
            ]
        )
    lines.extend(
        [
            "",
            "## Reproduction gate",
            "",
            f"Reproduction status: `{(reproduction or {}).get('status', 'not recorded')}`.",
            "",
            "## Outputs",
            "",
            "- `figures/book_rarity_violin.png` and `.svg`",
            "- `figures/rarity_by_segment.png` and `.svg`",
            "- `figures/book_distance_matrix.png` and `.svg`",
            "- `data/book_segment_rarity.csv` and `.parquet`",
            "- `data/book_rarity_summary.csv`",
            "- `data/rarest_segments.csv`",
        ]
    )
    methods_path = report_dir / "methods.md"
    methods_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report_manifest = {
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "rows": len(results),
        "books": int(results["book_id"].nunique()),
        "feature_set": feature_set,
        "reproduction_status": (reproduction or {}).get("status"),
    }
    write_json(report_dir / "report.json", report_manifest)
    return report_manifest


def analyze_books_internal(
    *,
    book_features_path: str | Path = "data/features/book_features.parquet",
    taxonomy_path: str | Path = "data/reference/storyscope/taxonomy.json",
    output_dir: str | Path = "outputs",
    feature_set: str = "public_nonstyle_265",
    k: int = 25,
    backend: str = "auto",
) -> pd.DataFrame:
    """Score segments only against the other supplied book segments."""
    feature_path = project_path(book_features_path)
    features = pd.read_parquet(feature_path).sort_values(
        ["book_id", "segment_index"]
    ).reset_index(drop=True)
    if len(features) < 2:
        raise ValueError("Internal analysis requires at least two book segments")
    normalized, standardized, decisions, encoder, scaler = _book_internal_space(
        features,
        taxonomy_path=taxonomy_path,
        feature_set=feature_set,
    )
    scored = score_internal_leave_one_out(
        normalized,
        standardized,
        k=k,
        backend=backend,
    )
    run_id = new_run_id("book-internal-rarity")
    scored["feature_set"] = feature_set
    scored["run_id"] = run_id
    scored["analysis_scope"] = "book_internal_exploratory"
    central_columns = [
        "book_id",
        "book_title",
        "chapter_index",
        "chapter_title",
        "segment_index",
        "segment_id",
        "word_count",
        "feature_set",
        "internal_raw_rarity",
        "internal_rarity_percentile",
        "internal_k",
        "internal_neighbor_book_counts",
        "extraction_provider",
        "extraction_model",
        "analysis_scope",
        "run_id",
    ]
    result = scored[[column for column in central_columns if column in scored.columns]].copy()
    output = project_path(output_dir)
    data_dir = output / "data"
    report_dir = output / "report"
    cache_dir = output / "cache"
    for directory in (data_dir, report_dir, cache_dir):
        directory.mkdir(parents=True, exist_ok=True)
    parquet_path = data_dir / "codex_internal_segment_rarity.parquet"
    csv_path = data_dir / "codex_internal_segment_rarity.csv"
    result.to_parquet(parquet_path, index=False)
    result.to_csv(csv_path, index=False)
    decisions.to_parquet(data_dir / "codex_book_feature_normalization.parquet", index=False)
    np.save(cache_dir / "codex_book_internal_standardized.npy", standardized, allow_pickle=False)
    encoder.save(cache_dir / "codex_book_internal_encoder.json")
    import joblib

    joblib.dump(scaler, cache_dir / "codex_book_internal_scaler.joblib")
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at_utc": utc_now(),
        "analysis_scope": "book_internal_exploratory",
        "feature_set": feature_set,
        "rows": len(result),
        "encoded_dimension": encoder.encoded_dimension,
        "k": int(result["internal_k"].iloc[0]),
        "metric": "euclidean",
        "standardization_fit": "supplied book segments only",
        "external_storyscope_percentile": False,
        "inputs": [str(feature_path)],
        "outputs": [str(parquet_path), str(csv_path)],
    }
    write_json(report_dir / f"{run_id}.manifest.json", manifest)
    return result


def generate_internal_report(
    *,
    rarity_path: str | Path = "outputs/data/codex_internal_segment_rarity.parquet",
    book_features_path: str | Path = "data/features/book_features.parquet",
    taxonomy_path: str | Path = "data/reference/storyscope/taxonomy.json",
    output_dir: str | Path = "outputs",
) -> dict[str, Any]:
    """Generate honest diagrams when the external StoryScope gate is unavailable."""
    output = project_path(output_dir)
    data_dir = output / "data"
    figures_dir = output / "figures"
    report_dir = output / "report"
    for directory in (data_dir, figures_dir, report_dir):
        directory.mkdir(parents=True, exist_ok=True)
    results = pd.read_parquet(project_path(rarity_path)).sort_values(
        ["book_id", "segment_index"]
    ).reset_index(drop=True)
    features = pd.read_parquet(project_path(book_features_path)).sort_values(
        ["book_id", "segment_index"]
    ).reset_index(drop=True)
    if results["segment_id"].astype(str).tolist() != features["segment_id"].astype(str).tolist():
        raise ValueError("Rarity results and feature rows are not aligned by segment")
    feature_set = str(results["feature_set"].iloc[0])
    normalized, standardized, _, encoder, _ = _book_internal_space(
        features,
        taxonomy_path=taxonomy_path,
        feature_set=feature_set,
    )
    summary = plot_internal_book_rarity(
        results,
        png_path=figures_dir / "codex_internal_rarity_violin.png",
        svg_path=figures_dir / "codex_internal_rarity_violin.svg",
    )
    summary.to_csv(data_dir / "codex_internal_rarity_summary.csv", index=False)
    plot_internal_rarity_sequence(
        results,
        png_path=figures_dir / "codex_internal_rarity_by_segment.png",
        svg_path=figures_dir / "codex_internal_rarity_by_segment.svg",
    )
    distance_frame = plot_segment_distance_matrix(
        normalized,
        standardized,
        png_path=figures_dir / "codex_segment_distance_matrix.png",
        svg_path=figures_dir / "codex_segment_distance_matrix.svg",
    )
    distance_frame.to_csv(data_dir / "codex_segment_distance_matrix.csv")
    rarest = results.sort_values("internal_rarity_percentile", ascending=False).head(5)
    rarest.to_csv(data_dir / "codex_rarest_segments.csv", index=False)

    models = sorted(results.get("extraction_model", pd.Series(dtype=str)).dropna().astype(str).unique())
    effective_k = int(results["internal_k"].iloc[0])
    methods = [
        "# Book-internal narrative rarity — Codex exploratory diagrams",
        "",
        "## Interpretation",
        "",
        "These diagrams compare each segment only with the other analyzed segments of the book. "
        "They are not external StoryScope percentiles, quality scores, plagiarism evidence, or "
        "judgments of originality.",
        "",
        "## Method",
        "",
        f"- Unit of analysis: {len(results)} non-overlapping novel segments.",
        "- Feature extraction: ten dimension-specific Codex CLI calls per segment.",
        f"- Extraction model recorded in the feature cache: `{', '.join(models)}`.",
        f"- Feature set: `{feature_set}` ({encoder.encoded_dimension} encoded columns).",
        "- Encoding: taxonomy-fixed one-hot, multi-hot, ordinal order, and numeric scale values.",
        "- Standardization: fitted only on the supplied book segments.",
        f"- Internal rarity: mean exact Euclidean distance to the other {effective_k} segments.",
        "- Percentile: empirical rank within this book's segment-level internal rarity values.",
        "- Violin and reading-order figures show raw mean distance; percentiles remain in the data table.",
        "",
        "## Limitation",
        "",
        "The published StoryScope reference artifacts remain mutually incompatible, so this report "
        "does not present a StoryScope train+validation comparison. The Codex extraction path also "
        "uses a different model from the paper and is explicitly exploratory.",
    ]
    methods_path = report_dir / "codex_internal_methods.md"
    methods_path.write_text("\n".join(methods) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "analysis_scope": "book_internal_exploratory",
        "rows": len(results),
        "books": int(results["book_id"].nunique()),
        "feature_set": feature_set,
        "encoded_dimension": encoder.encoded_dimension,
        "external_storyscope_percentile": False,
        "figures": [
            "codex_internal_rarity_violin.png",
            "codex_internal_rarity_by_segment.png",
            "codex_segment_distance_matrix.png",
        ],
    }
    write_json(report_dir / "codex_internal_report.json", manifest)
    return manifest
