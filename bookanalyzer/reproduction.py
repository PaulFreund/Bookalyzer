"""Figure 5 quality gate using only published StoryScope artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from .config import project_path
from .feature_matrix import (
    FeatureValidationError,
    canonicalize_feature_frame,
    invalid_feature_cells,
    load_feature_table,
    load_split_prompt_ids,
    load_taxonomy,
    select_split_rows,
)
from .plots import plot_figure5_reconstruction
from .provenance import file_record, utc_now, write_json
from .rarity import (
    DEFAULT_SOURCE_ORDER,
    _assert_source_coverage,
    _stable_feature_order,
    build_reference,
    compute_reference_rarity,
    score_against_reference,
)


def _write_reproduction_readme(
    output_dir: Path,
    metrics: dict[str, Any],
) -> None:
    status = str(metrics.get("status", "unknown"))
    lines = [
        "# Figure 5 reproduction status",
        "",
        f"Status: **{status.replace('_', ' ')}**.",
        "",
    ]
    if status.startswith("blocked") or status == "failed":
        lines.extend(
            [
                str(metrics.get("reason", "The quality gate could not be completed.")),
                "",
                "No exact-reproduction claim or book-level quality-gate claim is made.",
            ]
        )
    else:
        lines.extend(
            [
                f"Feature set: `{metrics['feature_set']}`  ",
                f"Encoded dimensions: `{metrics['encoded_dimension']}`  ",
                f"Reference rows: `{metrics['reference_rows']}`  ",
                f"Test rows: `{metrics['test_rows']}`  ",
                f"Human mean percentile: `{metrics['orientation']['human_mean']:.4f}`  ",
                f"Combined AI mean percentile: `{metrics['orientation']['ai_mean']:.4f}`",
                "",
                "The solid violin mark is the mean and the dashed mark is the median.",
            ]
        )
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def record_reproduction_blocker(
    *,
    feature_set: str,
    error: Exception,
    output_dir: str | Path = "reproduction",
    cache_dir: str | Path = "data/cache",
) -> dict[str, Any]:
    output = project_path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    compatibility_path = project_path(cache_dir) / "reference_compatibility.json"
    compatibility = None
    if compatibility_path.is_file():
        with compatibility_path.open("r", encoding="utf-8") as handle:
            compatibility = json.load(handle)
    metrics = {
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "status": "blocked_incompatible_public_artifacts",
        "feature_set": feature_set,
        "reason": str(error),
        "compatibility_audit": compatibility,
        "official_artifact_audit": {
            "paper": "https://arxiv.org/abs/2604.03136v4",
            "paper_source_checked": True,
            "repository": "https://github.com/jenna-russell/storyscope",
            "repository_commit": "642e746804e1ee4138ffdcf13b7412eb3dc2a70b",
            "result": (
                "No published mapping for out-of-taxonomy values and no list of the eight "
                "additional style-related feature IDs was found."
            ),
        },
        "known_artifact_gaps": [
            "The paper's strict narrative set omits eight non-style-dimension feature IDs that are not published.",
            "The paper reports 61,608 feature rows while the released parquet contains 61,575.",
        ],
        "exact_reproduction_claimed": False,
        "book_quality_gate_passed": False,
    }
    write_json(output / "metrics.json", metrics)
    _write_reproduction_readme(output, metrics)
    return metrics


def reproduce_figure5(
    *,
    feature_set: str = "public_nonstyle_265",
    reference_dir: str | Path = "data/reference/storyscope",
    cache_dir: str | Path = "data/cache",
    output_dir: str | Path = "reproduction",
    source_order: Sequence[str] = DEFAULT_SOURCE_ORDER,
    k: int = 25,
    backend: str = "auto",
    query_batch_size: int = 256,
    reference_block_size: int = 4096,
    tie_method: str = "right",
) -> dict[str, Any]:
    output = project_path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    try:
        artifacts = build_reference(
            feature_set=feature_set,
            reference_dir=reference_dir,
            cache_dir=cache_dir,
            source_order=source_order,
        )
    except FeatureValidationError as error:
        record_reproduction_blocker(
            feature_set=feature_set,
            error=error,
            output_dir=output,
            cache_dir=cache_dir,
        )
        raise

    reference_rarity, reference_metrics = compute_reference_rarity(
        artifacts,
        k=k,
        backend=backend,
        query_batch_size=query_batch_size,
        reference_block_size=reference_block_size,
    )
    reference = project_path(reference_dir)
    features = load_feature_table(reference / "storyscope_features.parquet")
    test_ids = load_split_prompt_ids(reference / "stories_test.parquet", "test")
    published_test = _stable_feature_order(select_split_rows(features, test_ids), source_order)
    coverage = _assert_source_coverage(published_test, test_ids, source_order)
    source_counts_by_prompt = published_test.groupby("prompt_id")["source"].nunique()
    complete_prompt_ids = set(
        source_counts_by_prompt[source_counts_by_prompt == len(source_order)].index.astype(int)
    )
    test = published_test[
        published_test["prompt_id"].astype(int).isin(complete_prompt_ids)
    ].reset_index(drop=True)
    _, specs = load_taxonomy(reference / "taxonomy.json")
    test, normalization = canonicalize_feature_frame(test, specs, artifacts.feature_ids)
    normalization.to_parquet(output / "test_normalization_decisions.parquet", index=False)
    incompatible = invalid_feature_cells(test, specs, artifacts.feature_ids)
    if incompatible:
        incompatible_path = output / "test_incompatible_values.parquet"
        pd.DataFrame(incompatible).to_parquet(incompatible_path, index=False)
        error = FeatureValidationError(
            f"Published test features contain {len(incompatible)} values outside the taxonomy; "
            f"details: {incompatible_path}"
        )
        record_reproduction_blocker(
            feature_set=feature_set,
            error=error,
            output_dir=output,
            cache_dir=cache_dir,
        )
        raise error

    scored, scoring_metrics = score_against_reference(
        test,
        artifacts,
        reference_rarity=reference_rarity,
        k=k,
        backend=backend,
        query_batch_size=query_batch_size,
        reference_block_size=reference_block_size,
        tie_method=tie_method,
    )
    result_columns = [
        column
        for column in (
            "prompt_id",
            "story_title",
            "source",
            "feature_set",
            "raw_rarity",
            "rarity_percentile",
            "nearest_source_counts",
        )
        if column in scored.columns
    ]
    results = scored[result_columns]
    results_path = output / "test_rarity.parquet"
    results.to_parquet(results_path, index=False)
    summary = plot_figure5_reconstruction(
        results,
        feature_set=feature_set,
        source_order=source_order,
        png_path=output / "figure5.png",
        svg_path=output / "figure5.svg",
    )
    summary.to_csv(output / "figure5_summary.csv", index=False)
    human_mean = float(results.loc[results["source"] == "human", "rarity_percentile"].mean())
    ai_mean = float(results.loc[results["source"] != "human", "rarity_percentile"].mean())
    orientation = {
        "paper_human_mean_approx": 0.71,
        "paper_ai_mean_approx": 0.49,
        "human_mean": human_mean,
        "ai_mean": ai_mean,
        "human_absolute_delta": abs(human_mean - 0.71),
        "ai_absolute_delta": abs(ai_mean - 0.49),
        "orientation_tolerance": 0.10,
    }
    orientation["within_tolerance"] = bool(
        orientation["human_absolute_delta"] <= 0.10
        and orientation["ai_absolute_delta"] <= 0.10
    )
    exact = bool(
        feature_set == "paper_narrative_257"
        and artifacts.encoder.encoded_dimension == 958
        and coverage["missing_story_rows"] == 0
        and orientation["within_tolerance"]
    )
    status = "exact_reproduction" if exact else "public_artifacts_reconstruction"
    metrics = {
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "status": status,
        "exact_reproduction_claimed": exact,
        "book_quality_gate_passed": bool(orientation["within_tolerance"]),
        "feature_set": feature_set,
        "feature_count": len(artifacts.feature_ids),
        "encoded_dimension": artifacts.encoder.encoded_dimension,
        "reference_rows": len(artifacts.matrix),
        "test_rows": len(results),
        "published_test_rows_before_complete_prompt_filter": len(published_test),
        "complete_test_prompt_count": len(complete_prompt_ids),
        "test_filter": (
            "Figure 5 uses prompts with all six sources; the paper reports 1,377 per source "
            "and 8,262 evaluated test stories."
        ),
        "reference_source_coverage": artifacts.manifest["published_source_coverage"],
        "test_source_coverage": coverage,
        "source_summary": summary.to_dict(orient="records"),
        "orientation": orientation,
        "reference_rarity": reference_metrics,
        "scoring": scoring_metrics,
        "tie_method": tie_method,
        "outputs": {
            "test_rarity": file_record(results_path),
            "figure5_png": file_record(output / "figure5.png"),
            "figure5_svg": file_record(output / "figure5.svg"),
        },
    }
    write_json(output / "metrics.json", metrics)
    _write_reproduction_readme(output, metrics)
    return metrics
