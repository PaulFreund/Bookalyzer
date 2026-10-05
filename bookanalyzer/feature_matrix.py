"""StoryScope taxonomy handling and strict feature-table validation."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from .config import load_yaml, project_path


MISSING_MARKERS = {"n/a", "na", "__na__"}
METADATA_COLUMNS = {"prompt_id", "story_title", "title", "source", "author"}


class FeatureValidationError(ValueError):
    """Raised when feature values do not conform to the public taxonomy."""


class FeatureSetBlockedError(RuntimeError):
    """Raised when a requested feature set depends on unpublished identifiers."""


@dataclass(frozen=True)
class FeatureSpec:
    id: str
    name: str
    feature_type: str
    values: tuple[str, ...]
    dimension_key: str
    dimension_name: str
    condition: str | None = None


def load_taxonomy(path: str | Path) -> tuple[dict[str, Any], dict[str, FeatureSpec]]:
    resolved = project_path(path)
    with resolved.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    taxonomy = payload.get("feature_taxonomy", payload)
    specs: dict[str, FeatureSpec] = {}
    for dimension_key, dimension in taxonomy.items():
        if not isinstance(dimension, Mapping) or "aspects" not in dimension:
            continue
        dimension_name = str(dimension.get("dimension_name", dimension_key))
        for aspect in dimension.get("aspects", {}).values():
            for feature in aspect.get("features", []):
                feature_id = str(feature["id"])
                if feature_id in specs:
                    raise FeatureValidationError(f"Duplicate taxonomy feature ID: {feature_id}")
                specs[feature_id] = FeatureSpec(
                    id=feature_id,
                    name=str(feature.get("name", feature_id)),
                    feature_type=str(feature.get("type", "categorical")).replace("-", "_"),
                    values=tuple(str(value) for value in feature.get("values", [])),
                    dimension_key=str(dimension_key),
                    dimension_name=dimension_name,
                    condition=feature.get("condition"),
                )
    expected = payload.get("taxonomy_metadata", {}).get("total_features")
    if expected is not None and int(expected) != len(specs):
        raise FeatureValidationError(
            f"Taxonomy declares {expected} features but contains {len(specs)}"
        )
    return payload, specs


def resolve_feature_set(
    name: str,
    specs: Mapping[str, FeatureSpec],
    config_path: str | Path = "config/feature_sets.yaml",
) -> list[str]:
    feature_sets = load_yaml(config_path).get("feature_sets", {})
    if name not in feature_sets:
        raise KeyError(f"Unknown feature set {name!r}; available: {', '.join(feature_sets)}")
    config = feature_sets[name]
    if config.get("status") == "blocked":
        raise FeatureSetBlockedError(str(config.get("blocked_reason", name)))

    excluded_dimensions = {str(value) for value in config.get("exclude_dimensions", [])}
    excluded_ids = {str(value) for value in config.get("excluded_feature_ids", [])}
    unknown = excluded_ids.difference(specs)
    if unknown:
        raise FeatureValidationError(
            f"Feature set {name} excludes unknown IDs: {', '.join(sorted(unknown))}"
        )
    selected = [
        feature_id
        for feature_id, spec in specs.items()
        if spec.dimension_key not in excluded_dimensions and feature_id not in excluded_ids
    ]
    expected = config.get("expected_features")
    if expected is not None and len(selected) != int(expected):
        raise FeatureValidationError(
            f"Feature set {name} resolves to {len(selected)} features, expected {expected}"
        )
    return selected


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return isinstance(value, str) and value.strip().lower() in MISSING_MARKERS


def parse_multi_select(value: Any) -> list[str]:
    if is_missing(value):
        return []
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value]
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed]
            except json.JSONDecodeError:
                pass
        return [item.strip() for item in stripped.split("|") if item.strip()]
    raise FeatureValidationError(f"Invalid multi-select value type: {type(value).__name__}")


def _normalization_key(value: str) -> str:
    normalized = str(value).strip().lower()
    normalized = re.sub(r"\s*\([^)]*\)", "", normalized)
    return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")


def _best_taxonomy_match(raw_value: str, allowed: Sequence[str]) -> tuple[str, str]:
    """Mirror StoryScope Stage 5's published canonicalization, with an audit label."""
    if not allowed:
        return raw_value, "no_vocabulary"
    raw_key = _normalization_key(raw_value)
    for canonical in allowed:
        if _normalization_key(canonical) == raw_key:
            return canonical, "normalized_exact"
    raw_number = re.match(r"^(\d+)", raw_key)
    if raw_number:
        for canonical in allowed:
            canonical_number = re.match(r"^(\d+)", _normalization_key(canonical))
            if canonical_number and canonical_number.group(1) == raw_number.group(1):
                return canonical, "numeric_prefix"
    for canonical in allowed:
        canonical_key = _normalization_key(canonical)
        if raw_key.startswith(canonical_key) or canonical_key.startswith(raw_key):
            return canonical, "prefix"
    raw_tokens = set(raw_key.split("_"))
    best_score = 0.0
    best_canonical: str | None = None
    for canonical in allowed:
        canonical_tokens = set(_normalization_key(canonical).split("_"))
        if not canonical_tokens:
            continue
        score = len(raw_tokens & canonical_tokens) / max(len(raw_tokens), len(canonical_tokens))
        if score > best_score:
            best_score = score
            best_canonical = canonical
    if best_score >= 0.5 and best_canonical is not None:
        return best_canonical, "token_overlap"
    return raw_value, "unmatched"


def canonicalize_value(value: Any, spec: FeatureSpec) -> tuple[Any, str]:
    if is_missing(value):
        return "n/a", "missing_marker"
    if spec.feature_type == "multi_select":
        raw_values = parse_multi_select(value)
        normalized: list[str] = []
        methods: list[str] = []
        for raw in raw_values:
            canonical, method = _best_taxonomy_match(raw, spec.values)
            if canonical not in normalized:
                normalized.append(canonical)
            methods.append(method)
        return "|".join(normalized), "+".join(sorted(set(methods)))
    if spec.feature_type == "scale":
        try:
            return _scale_value(value), "numeric_scale"
        except FeatureValidationError:
            return value, "unmatched"
    canonical, method = _best_taxonomy_match(str(value).strip(), spec.values)
    return canonical, method


def canonicalize_feature_frame(
    frame: pd.DataFrame,
    specs: Mapping[str, FeatureSpec],
    feature_ids: Sequence[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Canonicalize with StoryScope's public rules and return every changed value."""
    selected = list(feature_ids or specs.keys())
    output = frame.copy()
    decisions: dict[tuple[str, str, str, str], int] = {}
    for feature_id in selected:
        spec = specs[feature_id]
        cache: dict[str, tuple[Any, str]] = {}
        normalized_values: list[Any] = []
        for value in output[feature_id].tolist():
            key = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
            if key not in cache:
                cache[key] = canonicalize_value(value, spec)
            normalized, method = cache[key]
            normalized_values.append(normalized)
            raw_display = str(value)
            normalized_display = str(normalized)
            if raw_display != normalized_display:
                decision_key = (feature_id, raw_display, normalized_display, method)
                decisions[decision_key] = decisions.get(decision_key, 0) + 1
        output[feature_id] = normalized_values
    decision_rows = [
        {
            "feature_id": feature_id,
            "raw_value": raw,
            "canonical_value": canonical,
            "method": method,
            "count": count,
        }
        for (feature_id, raw, canonical, method), count in sorted(decisions.items())
    ]
    return output, pd.DataFrame(
        decision_rows,
        columns=["feature_id", "raw_value", "canonical_value", "method", "count"],
    )


def _scale_value(value: Any) -> str:
    if isinstance(value, bool):
        raise FeatureValidationError("Boolean is not a valid scale value")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as error:
        raise FeatureValidationError(f"Invalid numeric scale value: {value!r}") from error
    return str(int(numeric)) if numeric.is_integer() else str(numeric)


def _allowed_scale_numbers(values: Sequence[str]) -> set[str]:
    numbers: set[str] = set()
    for value in values:
        match = re.match(r"^\s*(-?\d+(?:\.\d+)?)", str(value))
        if match:
            numeric = float(match.group(1))
            numbers.add(str(int(numeric)) if numeric.is_integer() else str(numeric))
    return numbers


def validate_value(value: Any, spec: FeatureSpec) -> None:
    if is_missing(value):
        return
    allowed = set(spec.values)
    if spec.feature_type == "multi_select":
        values = parse_multi_select(value)
        invalid = [item for item in values if item not in allowed]
        if invalid:
            raise FeatureValidationError(
                f"{spec.id} contains unknown multi-select values: {invalid!r}"
            )
        if len(values) != len(set(values)):
            raise FeatureValidationError(f"{spec.id} contains duplicate multi-select values")
        return
    if spec.feature_type == "scale":
        normalized = _scale_value(value)
        allowed_numbers = _allowed_scale_numbers(spec.values)
        if allowed and normalized not in allowed and normalized not in allowed_numbers:
            raise FeatureValidationError(
                f"{spec.id}={value!r} is outside allowed values {spec.values!r}"
            )
        return
    normalized = str(value).strip()
    if normalized not in allowed:
        raise FeatureValidationError(
            f"{spec.id}={value!r} is not one of {spec.values!r}"
        )


def invalid_feature_cells(
    frame: pd.DataFrame,
    specs: Mapping[str, FeatureSpec],
    feature_ids: Sequence[str] | None = None,
    *,
    max_errors: int | None = None,
) -> list[dict[str, Any]]:
    """Return explicit invalid cells without creating any new category."""
    selected = list(feature_ids or specs.keys())
    errors: list[dict[str, Any]] = []
    for feature_id in selected:
        if feature_id not in frame.columns:
            errors.append(
                {
                    "row_index": None,
                    "feature_id": feature_id,
                    "value": "__MISSING_COLUMN__",
                    "error": "missing feature column",
                }
            )
            continue
        spec = specs[feature_id]
        validation_cache: dict[str, str | None] = {}
        for index, value in frame[feature_id].items():
            if is_missing(value):
                continue
            try:
                key = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
            except TypeError:
                key = repr(value)
            if key not in validation_cache:
                try:
                    validate_value(value, spec)
                    validation_cache[key] = None
                except FeatureValidationError as error:
                    validation_cache[key] = str(error)
            error_text = validation_cache[key]
            if error_text is not None:
                errors.append(
                    {
                        "row_index": int(index) if isinstance(index, int) else str(index),
                        "feature_id": feature_id,
                        "value": value,
                        "error": error_text,
                    }
                )
                if max_errors is not None and len(errors) >= max_errors:
                    return errors
    return errors


def validate_feature_frame(
    frame: pd.DataFrame,
    specs: Mapping[str, FeatureSpec],
    feature_ids: Sequence[str] | None = None,
    *,
    max_errors: int = 25,
) -> dict[str, Any]:
    selected = list(feature_ids or specs.keys())
    missing_columns = [feature_id for feature_id in selected if feature_id not in frame.columns]
    if missing_columns:
        raise FeatureValidationError(
            f"Feature table is missing {len(missing_columns)} columns: "
            + ", ".join(missing_columns[:10])
        )

    errors: list[str] = []
    na_counts: dict[str, int] = {}
    for feature_id in selected:
        spec = specs[feature_id]
        na_count = 0
        for index, value in frame[feature_id].items():
            if is_missing(value):
                na_count += 1
                continue
            try:
                validate_value(value, spec)
            except FeatureValidationError as error:
                errors.append(f"row={index}, {error}")
                if len(errors) >= max_errors:
                    break
        na_counts[feature_id] = na_count
        if len(errors) >= max_errors:
            break
    if errors:
        raise FeatureValidationError(
            f"Feature validation failed ({len(errors)} shown):\n" + "\n".join(errors)
        )
    return {
        "rows": int(len(frame)),
        "features": len(selected),
        "missing_values": int(sum(na_counts.values())),
        "missing_by_feature": na_counts,
    }


def load_feature_table(path: str | Path) -> pd.DataFrame:
    frame = pd.read_parquet(project_path(path))
    if "author" in frame.columns and "source" not in frame.columns:
        frame = frame.rename(columns={"author": "source"})
    required = {"prompt_id", "source"}
    missing = required.difference(frame.columns)
    if missing:
        raise FeatureValidationError(f"Feature table lacks columns: {', '.join(sorted(missing))}")
    duplicates = frame.duplicated(["prompt_id", "source"])
    if duplicates.any():
        raise FeatureValidationError(
            f"Feature table has {int(duplicates.sum())} duplicate prompt/source rows"
        )
    return frame


def load_split_prompt_ids(stories_path: str | Path, expected_split: str) -> set[int]:
    frame = pd.read_parquet(project_path(stories_path), columns=["prompt_id", "split"])
    actual = set(frame["split"].dropna().astype(str).unique())
    if actual != {expected_split}:
        raise FeatureValidationError(
            f"Expected only split {expected_split!r} in {stories_path}, found {sorted(actual)!r}"
        )
    return set(frame["prompt_id"].astype(int))


def select_split_rows(frame: pd.DataFrame, prompt_ids: Iterable[int]) -> pd.DataFrame:
    ids = set(int(value) for value in prompt_ids)
    selected = frame[frame["prompt_id"].astype(int).isin(ids)].copy()
    found = set(selected["prompt_id"].astype(int))
    missing = ids.difference(found)
    if missing:
        raise FeatureValidationError(
            f"Published features are missing {len(missing)} prompt IDs from the split"
        )
    return selected.reset_index(drop=True)


def compile_feature_jsons(
    raw_dir: str | Path,
    taxonomy_path: str | Path,
    segments_path: str | Path,
    output_path: str | Path,
) -> pd.DataFrame:
    _, specs = load_taxonomy(taxonomy_path)
    segments = pd.read_parquet(project_path(segments_path))
    segment_by_prompt = segments.set_index("prompt_id", drop=False)
    rows: list[dict[str, Any]] = []
    for path in sorted(project_path(raw_dir).glob("*/*.features.json")):
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        prompt_id = int(payload["prompt_id"])
        if prompt_id not in segment_by_prompt.index:
            raise FeatureValidationError(f"Unknown prompt_id {prompt_id} in {path}")
        features = payload.get("features", {})
        unknown = set(features).difference(specs)
        missing = set(specs).difference(features)
        if unknown or missing:
            raise FeatureValidationError(
                f"{path} has {len(missing)} missing and {len(unknown)} unknown feature IDs"
            )
        segment = segment_by_prompt.loc[prompt_id]
        row = {
            "prompt_id": prompt_id,
            "story_title": payload.get("story_title", segment["title"]),
            "source": "human",
            "book_id": segment["book_id"],
            "book_title": segment["book_title"],
            "segment_id": segment["segment_id"],
            "chapter_index": int(segment["chapter_index"]),
            "chapter_title": segment.get("chapter_title", ""),
            "segment_index": int(segment["segment_index"]),
            "word_count": int(segment["word_count"]),
            "language": segment.get("language", "und"),
            "extraction_provider": payload.get("metadata", {}).get("provider"),
            "extraction_model": payload.get("metadata", {}).get("model"),
            "extraction_reasoning_effort": payload.get("metadata", {}).get("reasoning_effort"),
            **features,
        }
        rows.append(row)
    if not rows:
        raise FileNotFoundError(f"No .features.json files found below {project_path(raw_dir)}")
    result = pd.DataFrame(rows).sort_values(["book_id", "segment_index"]).reset_index(drop=True)
    validate_feature_frame(result, specs)
    output = project_path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output, index=False)
    return result
