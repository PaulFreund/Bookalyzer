"""Reference-space construction and exact StoryScope rarity calculations."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import joblib
import numpy as np
import pandas as pd
from numpy.lib.format import open_memmap
from sklearn.preprocessing import StandardScaler

from .config import project_path
from .feature_matrix import (
    canonicalize_feature_frame,
    FeatureValidationError,
    invalid_feature_cells,
    load_feature_table,
    load_split_prompt_ids,
    load_taxonomy,
    resolve_feature_set,
    select_split_rows,
    validate_feature_frame,
)
from .paper_encoder import PaperEncoder
from .provenance import file_record, sha256_file, utc_now, write_json


DEFAULT_SOURCE_ORDER = ["human", "claude", "gpt", "deepseek", "kimi", "gemini"]


def _stable_feature_order(frame: pd.DataFrame, source_order: Sequence[str]) -> pd.DataFrame:
    unknown_sources = set(frame["source"].astype(str)).difference(source_order)
    if unknown_sources:
        raise FeatureValidationError(
            f"Feature table contains unexpected sources: {', '.join(sorted(unknown_sources))}"
        )
    ordered = frame.copy()
    ordered["source"] = pd.Categorical(ordered["source"], categories=source_order, ordered=True)
    ordered = ordered.sort_values(["prompt_id", "source"]).reset_index(drop=True)
    ordered["source"] = ordered["source"].astype("object").astype(str)
    return ordered


def _assert_source_coverage(
    frame: pd.DataFrame,
    prompt_ids: Iterable[int],
    sources: Sequence[str],
) -> dict[str, Any]:
    expected_ids = set(int(value) for value in prompt_ids)
    grouped = frame.groupby("prompt_id")["source"].agg(lambda values: set(map(str, values)))
    incomplete = {
        int(prompt_id): sorted(set(sources).difference(values))
        for prompt_id, values in grouped.items()
        if values != set(sources)
    }
    missing_ids = expected_ids.difference(set(map(int, grouped.index)))
    source_counts = frame["source"].astype(str).value_counts().to_dict()
    wholly_missing_sources = set(sources).difference(source_counts)
    if missing_ids or wholly_missing_sources:
        raise FeatureValidationError(
            "Reference source coverage is incomplete: "
            f"{len(missing_ids)} prompts and {len(wholly_missing_sources)} complete sources are absent"
        )
    return {
        "expected_complete_rows": len(expected_ids) * len(sources),
        "published_rows": int(len(frame)),
        "missing_story_rows": len(expected_ids) * len(sources) - len(frame),
        "incomplete_prompt_count": len(incomplete),
        "missing_sources_by_prompt": {str(key): value for key, value in incomplete.items()},
        "source_counts": {source: int(source_counts.get(source, 0)) for source in sources},
    }


@dataclass
class ReferenceArtifacts:
    cache_dir: Path
    feature_set: str
    feature_ids: list[str]
    encoder: PaperEncoder
    scaler: StandardScaler
    matrix: np.ndarray
    metadata: pd.DataFrame
    manifest: dict[str, Any]


def build_reference(
    *,
    feature_set: str = "public_nonstyle_265",
    reference_dir: str | Path = "data/reference/storyscope",
    cache_dir: str | Path = "data/cache",
    source_order: Sequence[str] = DEFAULT_SOURCE_ORDER,
) -> ReferenceArtifacts:
    reference = project_path(reference_dir)
    cache = project_path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    taxonomy_path = reference / "taxonomy.json"
    features_path = reference / "storyscope_features.parquet"
    _, specs = load_taxonomy(taxonomy_path)
    feature_ids = resolve_feature_set(feature_set, specs)
    features = load_feature_table(features_path)

    train_ids = load_split_prompt_ids(reference / "stories_train.parquet", "train")
    val_ids = load_split_prompt_ids(reference / "stories_val.parquet", "val")
    pooled_ids = train_ids | val_ids
    pooled = select_split_rows(features, pooled_ids)
    pooled = _stable_feature_order(pooled, source_order)
    coverage = _assert_source_coverage(pooled, pooled_ids, source_order)
    pooled, normalization_decisions = canonicalize_feature_frame(pooled, specs, feature_ids)
    normalization_path = cache / "reference_normalization_decisions.parquet"
    normalization_decisions.to_parquet(normalization_path, index=False)
    incompatible = invalid_feature_cells(pooled, specs, feature_ids)
    if incompatible:
        incompatible_frame = pd.DataFrame(incompatible)
        incompatible_path = cache / "reference_incompatible_values.parquet"
        incompatible_frame.to_parquet(incompatible_path, index=False)
        summary = {
            "schema_version": 1,
            "status": "blocked_incompatible_public_artifacts",
            "feature_set": feature_set,
            "invalid_cell_count": len(incompatible_frame),
            "affected_row_count": int(incompatible_frame["row_index"].nunique()),
            "affected_feature_count": int(incompatible_frame["feature_id"].nunique()),
            "top_features": {
                str(key): int(value)
                for key, value in incompatible_frame["feature_id"].value_counts().head(25).items()
            },
            "normalization_decision_count": int(len(normalization_decisions)),
            "normalization_affected_cell_count": int(normalization_decisions["count"].sum()),
            "published_source_coverage": coverage,
            "encoded_dimension_if_compatible": PaperEncoder(specs, feature_ids).encoded_dimension,
            "policy": (
                "StoryScope Stage 5 canonicalization was applied and logged. Values still outside "
                "the taxonomy were not guessed, added as categories, or silently imputed."
            ),
            "incompatible_values_path": str(incompatible_path),
            "normalization_decisions_path": str(normalization_path),
        }
        write_json(cache / "reference_compatibility.json", summary)
        raise FeatureValidationError(
            "Published StoryScope features remain incompatible with the published taxonomy after "
            f"the official Stage 5 normalization rules: {len(incompatible_frame)} cells across "
            f"{summary['affected_row_count']} rows and {summary['affected_feature_count']} features. "
            f"Details: {incompatible_path}"
        )
    validation = validate_feature_frame(pooled, specs, feature_ids)

    encoder = PaperEncoder(specs, feature_ids)
    encoded = encoder.fit_transform(pooled)
    scaler = StandardScaler(copy=True, with_mean=True, with_std=True)
    scaled = scaler.fit_transform(encoded).astype(np.float32, copy=False)
    constant_indices = np.flatnonzero(scaler.var_ == 0).astype(int).tolist()

    encoder_path = cache / "encoder.json"
    columns_path = cache / "feature_columns.json"
    scaler_path = cache / "scaler.joblib"
    matrix_path = cache / "reference_matrix.npy"
    metadata_path = cache / "reference_metadata.parquet"
    manifest_path = cache / "reference_manifest.json"
    encoder.save(encoder_path)
    write_json(
        columns_path,
        {
            "schema_version": 1,
            "feature_set": feature_set,
            "feature_ids": feature_ids,
            "encoded_columns": encoder.columns,
        },
    )
    joblib.dump(scaler, scaler_path)
    np.save(matrix_path, scaled, allow_pickle=False)
    metadata_columns = [
        column for column in ("prompt_id", "story_title", "title", "source") if column in pooled.columns
    ]
    metadata = pooled[metadata_columns].copy()
    metadata.insert(0, "reference_index", np.arange(len(metadata), dtype=np.int64))
    metadata.to_parquet(metadata_path, index=False)

    dimension_targets = {
        "full_304": 1108,
        "paper_narrative_257": 958,
        "style_only": 129,
    }
    manifest = {
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "feature_set": feature_set,
        "feature_count": len(feature_ids),
        "encoded_dimension": encoder.encoded_dimension,
        "paper_dimension_target": dimension_targets.get(feature_set),
        "reference_splits": ["train", "val"],
        "source_order": list(source_order),
        "train_prompt_count": len(train_ids),
        "validation_prompt_count": len(val_ids),
        "reference_rows": int(len(pooled)),
        "published_source_coverage": coverage,
        "scaler_fit_rows": int(scaler.n_samples_seen_),
        "zero_variance_column_count": len(constant_indices),
        "zero_variance_columns": [encoder.columns[index] for index in constant_indices],
        "na_policy": encoder.to_dict()["na_policy"],
        "validation": validation,
        "normalization": {
            "decision_rows": int(len(normalization_decisions)),
            "affected_cells": int(normalization_decisions["count"].sum()),
            "decisions_path": str(normalization_path),
        },
        "inputs": {
            "taxonomy": file_record(taxonomy_path),
            "features": file_record(features_path),
            "train_split": file_record(reference / "stories_train.parquet"),
            "validation_split": file_record(reference / "stories_val.parquet"),
        },
    }
    write_json(manifest_path, manifest)
    return ReferenceArtifacts(
        cache_dir=cache,
        feature_set=feature_set,
        feature_ids=feature_ids,
        encoder=encoder,
        scaler=scaler,
        matrix=scaled,
        metadata=metadata,
        manifest=manifest,
    )


def load_reference(
    *,
    cache_dir: str | Path = "data/cache",
    taxonomy_path: str | Path = "data/reference/storyscope/taxonomy.json",
    feature_set: str | None = None,
    mmap_mode: str | None = "r",
) -> ReferenceArtifacts:
    cache = project_path(cache_dir)
    with (cache / "reference_manifest.json").open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if feature_set is not None and manifest.get("feature_set") != feature_set:
        raise RuntimeError(
            f"Cached reference uses {manifest.get('feature_set')!r}, requested {feature_set!r}; "
            "rebuild the reference cache."
        )
    _, specs = load_taxonomy(taxonomy_path)
    encoder = PaperEncoder.load(cache / "encoder.json", specs)
    scaler = joblib.load(cache / "scaler.joblib")
    matrix = np.load(cache / "reference_matrix.npy", mmap_mode=mmap_mode, allow_pickle=False)
    metadata = pd.read_parquet(cache / "reference_metadata.parquet")
    if matrix.shape != (len(metadata), encoder.encoded_dimension):
        raise RuntimeError("Reference matrix shape does not match metadata/encoder")
    if int(scaler.n_samples_seen_) != len(metadata):
        raise RuntimeError("Scaler was not fitted on exactly the cached reference rows")
    return ReferenceArtifacts(
        cache_dir=cache,
        feature_set=str(manifest["feature_set"]),
        feature_ids=list(encoder.feature_ids),
        encoder=encoder,
        scaler=scaler,
        matrix=matrix,
        metadata=metadata,
        manifest=manifest,
    )


class ExactKNNIndex:
    """Exact Euclidean kNN using FAISS IndexFlatL2 or blockwise NumPy."""

    def __init__(
        self,
        reference: np.ndarray,
        *,
        backend: str = "auto",
        reference_block_size: int = 4096,
    ):
        if reference.ndim != 2 or len(reference) == 0:
            raise ValueError("Reference matrix must be a non-empty 2D array")
        self.reference = np.ascontiguousarray(reference, dtype=np.float32)
        self.reference_block_size = int(reference_block_size)
        self.backend = backend
        self._faiss = None
        if backend in {"auto", "faiss"}:
            try:
                import faiss  # type: ignore

                self._faiss = faiss.IndexFlatL2(self.reference.shape[1])
                self._faiss.add(self.reference)
                self.backend = "faiss_index_flat_l2"
            except ImportError:
                if backend == "faiss":
                    raise
                self.backend = "numpy_blockwise"
        elif backend == "numpy":
            self.backend = "numpy_blockwise"
        else:
            raise ValueError("backend must be auto, faiss, or numpy")
        self._reference_norms = np.einsum("ij,ij->i", self.reference, self.reference)

    def search(
        self,
        queries: np.ndarray,
        k: int,
        *,
        exclude_reference_indices: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        query = np.ascontiguousarray(queries, dtype=np.float32)
        if query.ndim != 2 or query.shape[1] != self.reference.shape[1]:
            raise ValueError("Query matrix dimensions do not match the reference")
        if k < 1:
            raise ValueError("k must be positive")
        excluded = (
            np.full(len(query), -1, dtype=np.int64)
            if exclude_reference_indices is None
            else np.asarray(exclude_reference_indices, dtype=np.int64)
        )
        if excluded.shape != (len(query),):
            raise ValueError("exclude_reference_indices must have one entry per query")
        needed = k + (1 if np.any(excluded >= 0) else 0)
        if needed > len(self.reference):
            raise ValueError(f"Reference has too few rows for k={k} with self-exclusion")
        if self._faiss is not None:
            return self._search_faiss(query, k, excluded)
        return self._search_numpy(query, k, excluded)

    def _search_faiss(
        self, queries: np.ndarray, k: int, excluded: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        request_k = min(len(self.reference), k + 1)
        squared, indices = self._faiss.search(queries, request_k)
        output_squared = np.empty((len(queries), k), dtype=np.float32)
        output_indices = np.empty((len(queries), k), dtype=np.int64)
        for row in range(len(queries)):
            keep = indices[row] != excluded[row]
            row_indices = indices[row][keep][:k]
            row_squared = squared[row][keep][:k]
            if len(row_indices) != k:
                raise RuntimeError("FAISS did not return enough neighbors after self-exclusion")
            output_indices[row] = row_indices
            output_squared[row] = row_squared
        return np.sqrt(np.maximum(output_squared, 0), dtype=np.float32), output_indices

    def _search_numpy(
        self, queries: np.ndarray, k: int, excluded: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        query_norms = np.einsum("ij,ij->i", queries, queries)
        best_squared = np.full((len(queries), k), np.inf, dtype=np.float32)
        best_indices = np.full((len(queries), k), -1, dtype=np.int64)
        for block_start in range(0, len(self.reference), self.reference_block_size):
            block_end = min(block_start + self.reference_block_size, len(self.reference))
            block = self.reference[block_start:block_end]
            squared = (
                query_norms[:, None]
                + self._reference_norms[None, block_start:block_end]
                - 2.0 * (queries @ block.T)
            )
            np.maximum(squared, 0, out=squared)
            local_rows = np.flatnonzero(
                (excluded >= block_start) & (excluded < block_end)
            )
            if len(local_rows):
                squared[local_rows, excluded[local_rows] - block_start] = np.inf
            block_indices = np.broadcast_to(
                np.arange(block_start, block_end, dtype=np.int64), squared.shape
            )
            combined_squared = np.concatenate((best_squared, squared), axis=1)
            combined_indices = np.concatenate((best_indices, block_indices), axis=1)
            positions = np.argpartition(combined_squared, kth=k - 1, axis=1)[:, :k]
            best_squared = np.take_along_axis(combined_squared, positions, axis=1)
            best_indices = np.take_along_axis(combined_indices, positions, axis=1)
        order = np.argsort(best_squared, axis=1, kind="stable")
        best_squared = np.take_along_axis(best_squared, order, axis=1)
        best_indices = np.take_along_axis(best_indices, order, axis=1)
        if (best_indices < 0).any() or not np.isfinite(best_squared).all():
            raise RuntimeError("Exact kNN search produced incomplete neighbors")
        return np.sqrt(best_squared, dtype=np.float32), best_indices


def compute_reference_rarity(
    artifacts: ReferenceArtifacts,
    *,
    k: int = 25,
    backend: str = "auto",
    query_batch_size: int = 256,
    reference_block_size: int = 4096,
    resume: bool = True,
) -> tuple[np.ndarray, dict[str, Any]]:
    cache = artifacts.cache_dir
    raw_path = cache / "reference_raw_rarity.npy"
    progress_path = cache / "reference_rarity_progress.json"
    matrix_hash = sha256_file(cache / "reference_matrix.npy")
    expected_progress = {
        "matrix_sha256": matrix_hash,
        "rows": len(artifacts.matrix),
        "k": k,
    }
    start = 0
    if resume and raw_path.is_file() and progress_path.is_file():
        with progress_path.open("r", encoding="utf-8") as handle:
            progress = json.load(handle)
        if all(progress.get(key) == value for key, value in expected_progress.items()):
            start = int(progress.get("completed_rows", 0))
            raw = np.load(raw_path, mmap_mode="r+", allow_pickle=False)
            if raw.shape != (len(artifacts.matrix),):
                start = 0
    if start == 0:
        raw = open_memmap(
            raw_path,
            mode="w+",
            dtype=np.float32,
            shape=(len(artifacts.matrix),),
        )

    index = ExactKNNIndex(
        artifacts.matrix,
        backend=backend,
        reference_block_size=reference_block_size,
    )
    for batch_start in range(start, len(artifacts.matrix), query_batch_size):
        batch_end = min(batch_start + query_batch_size, len(artifacts.matrix))
        queries = artifacts.matrix[batch_start:batch_end]
        excluded = np.arange(batch_start, batch_end, dtype=np.int64)
        distances, _ = index.search(queries, k, exclude_reference_indices=excluded)
        raw[batch_start:batch_end] = distances.mean(axis=1)
        raw.flush()
        write_json(
            progress_path,
            {
                **expected_progress,
                "backend": index.backend,
                "completed_rows": batch_end,
                "updated_at_utc": utc_now(),
            },
        )
    values = np.asarray(raw, dtype=np.float32).copy()
    metrics = {
        "reference_rows": len(values),
        "k": k,
        "metric": "euclidean",
        "backend": index.backend,
        "exact": True,
        "mean": float(values.mean()),
        "median": float(np.median(values)),
        "minimum": float(values.min()),
        "maximum": float(values.max()),
        "raw_rarity_sha256": sha256_file(raw_path),
    }
    write_json(cache / "reference_rarity_metrics.json", metrics)
    return values, metrics


def empirical_percentile(
    reference_values: np.ndarray,
    values: np.ndarray,
    *,
    tie_method: str = "right",
) -> np.ndarray:
    if tie_method not in {"right", "left", "midpoint"}:
        raise ValueError("tie_method must be right, left, or midpoint")
    reference = np.sort(np.asarray(reference_values, dtype=np.float64))
    query = np.asarray(values, dtype=np.float64)
    left = np.searchsorted(reference, query, side="left")
    right = np.searchsorted(reference, query, side="right")
    ranks = right if tie_method == "right" else left if tie_method == "left" else (left + right) / 2
    return np.asarray(ranks / len(reference), dtype=np.float64)


def transform_with_reference(
    frame: pd.DataFrame,
    artifacts: ReferenceArtifacts,
) -> np.ndarray:
    validate_feature_frame(frame, artifacts.encoder.specs, artifacts.feature_ids)
    encoded = artifacts.encoder.transform(frame, validate=False)
    return artifacts.scaler.transform(encoded).astype(np.float32, copy=False)


def score_against_reference(
    frame: pd.DataFrame,
    artifacts: ReferenceArtifacts,
    *,
    reference_rarity: np.ndarray,
    k: int = 25,
    backend: str = "auto",
    query_batch_size: int = 256,
    reference_block_size: int = 4096,
    tie_method: str = "right",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    matrix = transform_with_reference(frame, artifacts)
    index = ExactKNNIndex(
        artifacts.matrix,
        backend=backend,
        reference_block_size=reference_block_size,
    )
    raw_values = np.empty(len(frame), dtype=np.float32)
    source_counts: list[str] = [""] * len(frame)
    for start in range(0, len(frame), query_batch_size):
        end = min(start + query_batch_size, len(frame))
        distances, neighbors = index.search(matrix[start:end], k)
        raw_values[start:end] = distances.mean(axis=1)
        for offset, neighbor_indices in enumerate(neighbors):
            sources = artifacts.metadata.iloc[neighbor_indices]["source"].astype(str)
            source_counts[start + offset] = json.dumps(
                dict(sorted(Counter(sources).items())), sort_keys=True
            )
    percentiles = empirical_percentile(reference_rarity, raw_values, tie_method=tie_method)
    result = frame.copy().reset_index(drop=True)
    result["feature_set"] = artifacts.feature_set
    result["raw_rarity"] = raw_values
    result["rarity_percentile"] = percentiles
    result["nearest_source_counts"] = source_counts
    metrics = {
        "rows": len(result),
        "feature_set": artifacts.feature_set,
        "encoded_dimension": artifacts.encoder.encoded_dimension,
        "k": k,
        "metric": "euclidean",
        "backend": index.backend,
        "exact": True,
        "percentile_reference": "StoryScope train+validation",
        "percentile_tie_method": tie_method,
    }
    return result, metrics


def score_internal_leave_one_out(
    frame: pd.DataFrame,
    matrix: np.ndarray,
    *,
    k: int = 25,
    backend: str = "auto",
) -> pd.DataFrame:
    if len(frame) < 2:
        raise ValueError("Internal rarity requires at least two book segments")
    effective_k = min(k, len(frame) - 1)
    index = ExactKNNIndex(matrix, backend=backend)
    excluded = np.arange(len(frame), dtype=np.int64)
    distances, neighbors = index.search(matrix, effective_k, exclude_reference_indices=excluded)
    raw = distances.mean(axis=1)
    output = frame.copy().reset_index(drop=True)
    output["internal_raw_rarity"] = raw
    output["internal_rarity_percentile"] = empirical_percentile(raw, raw, tie_method="right")
    output["internal_k"] = effective_k
    output["internal_neighbor_book_counts"] = [
        json.dumps(
            dict(sorted(Counter(output.iloc[row]["book_id"].astype(str)).items())),
            sort_keys=True,
        )
        for row in neighbors
    ]
    return output
