"""Explicit StoryScope encoding matching the method described in the paper."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from .feature_matrix import (
    FeatureSpec,
    FeatureValidationError,
    is_missing,
    parse_multi_select,
    validate_feature_frame,
)
from .provenance import sha256_text, utc_now, write_json


ENCODER_SCHEMA_VERSION = 1
NA_CATEGORY = "__NA__"
NA_NUMERIC = -1.0


class PaperEncoder:
    """Taxonomy-fixed encoder fitted only on StoryScope train + validation rows.

    Categorical and binary values are one-hot encoded, multi-select values are
    multi-hot encoded, ordinal values use their taxonomy order, and scales remain
    numeric. Conditional ``n/a`` is a dedicated indicator for one/multi-hot
    features and the documented sentinel ``-1`` for ordinal/scale features.
    """

    def __init__(self, specs: Mapping[str, FeatureSpec], feature_ids: Sequence[str]):
        self.specs = {feature_id: specs[feature_id] for feature_id in feature_ids}
        self.feature_ids = list(feature_ids)
        self.columns = self._build_columns()
        self.fitted = False
        self.fit_metadata: dict[str, Any] = {}

    def _build_columns(self) -> list[str]:
        columns: list[str] = []
        for feature_id, spec in self.specs.items():
            if spec.feature_type in {"categorical", "binary", "multi_select"}:
                columns.extend(f"{feature_id}__{value}" for value in spec.values)
                columns.append(f"{feature_id}__{NA_CATEGORY}")
            elif spec.feature_type in {"ordinal", "scale"}:
                columns.append(feature_id)
            else:
                raise FeatureValidationError(
                    f"Unsupported taxonomy type {spec.feature_type!r} for {feature_id}"
                )
        if len(columns) != len(set(columns)):
            raise FeatureValidationError("Encoded column names are not unique")
        return columns

    @property
    def encoded_dimension(self) -> int:
        return len(self.columns)

    def fit(self, frame: pd.DataFrame) -> "PaperEncoder":
        validation = validate_feature_frame(frame, self.specs, self.feature_ids)
        source_counts = (
            frame["source"].astype(str).value_counts().sort_index().to_dict()
            if "source" in frame.columns
            else {}
        )
        prompt_ids = sorted(frame["prompt_id"].astype(int).unique()) if "prompt_id" in frame else []
        self.fit_metadata = {
            "fitted_at_utc": utc_now(),
            "rows": int(len(frame)),
            "unique_prompt_ids": len(prompt_ids),
            "prompt_ids_sha256": sha256_text("\n".join(map(str, prompt_ids))),
            "source_counts": {str(key): int(value) for key, value in source_counts.items()},
            "validation": validation,
        }
        self.fitted = True
        return self

    def transform(self, frame: pd.DataFrame, *, validate: bool = True) -> np.ndarray:
        if not self.fitted:
            raise RuntimeError("PaperEncoder must be fitted before transform")
        if validate:
            validate_feature_frame(frame, self.specs, self.feature_ids)
        matrix = np.zeros((len(frame), self.encoded_dimension), dtype=np.float32)
        column_index = 0
        for feature_id, spec in self.specs.items():
            series = frame[feature_id]
            missing = series.map(is_missing).to_numpy(dtype=bool)
            if spec.feature_type in {"categorical", "binary"}:
                normalized = series.map(lambda value: "" if is_missing(value) else str(value).strip())
                for value in spec.values:
                    matrix[:, column_index] = (normalized == value).to_numpy(dtype=np.float32)
                    column_index += 1
                matrix[:, column_index] = missing.astype(np.float32)
                column_index += 1
            elif spec.feature_type == "multi_select":
                parsed = series.map(lambda value: set(parse_multi_select(value)))
                for value in spec.values:
                    matrix[:, column_index] = parsed.map(lambda items, v=value: v in items).to_numpy(
                        dtype=np.float32
                    )
                    column_index += 1
                matrix[:, column_index] = missing.astype(np.float32)
                column_index += 1
            elif spec.feature_type == "ordinal":
                ordinal = {value: index for index, value in enumerate(spec.values)}
                matrix[:, column_index] = series.map(
                    lambda value: NA_NUMERIC if is_missing(value) else float(ordinal[str(value).strip()])
                ).to_numpy(dtype=np.float32)
                column_index += 1
            elif spec.feature_type == "scale":
                matrix[:, column_index] = series.map(
                    lambda value: NA_NUMERIC if is_missing(value) else float(value)
                ).to_numpy(dtype=np.float32)
                column_index += 1
        if column_index != self.encoded_dimension:
            raise AssertionError("Internal encoded-column count mismatch")
        return matrix

    def fit_transform(self, frame: pd.DataFrame) -> np.ndarray:
        return self.fit(frame).transform(frame, validate=False)

    def to_dict(self) -> dict[str, Any]:
        if not self.fitted:
            raise RuntimeError("Cannot persist an unfitted PaperEncoder")
        return {
            "schema_version": ENCODER_SCHEMA_VERSION,
            "encoder": "Bookalyzer PaperEncoder",
            "feature_ids": self.feature_ids,
            "feature_specs": {key: asdict(value) for key, value in self.specs.items()},
            "columns": self.columns,
            "encoded_dimension": self.encoded_dimension,
            "na_policy": {
                "categorical_binary_multi_select": "dedicated __NA__ indicator",
                "ordinal_scale": NA_NUMERIC,
            },
            "fit_metadata": self.fit_metadata,
        }

    def save(self, path: str | Path) -> Path:
        return write_json(path, self.to_dict())

    @classmethod
    def load(
        cls,
        path: str | Path,
        specs: Mapping[str, FeatureSpec],
    ) -> "PaperEncoder":
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("schema_version") != ENCODER_SCHEMA_VERSION:
            raise ValueError(f"Unsupported encoder schema in {path}")
        encoder = cls(specs, payload["feature_ids"])
        if encoder.columns != payload.get("columns"):
            raise ValueError("Persisted encoder columns do not match the supplied taxonomy")
        persisted_specs = payload.get("feature_specs", {})
        current_specs = json.loads(
            json.dumps({key: asdict(value) for key, value in encoder.specs.items()})
        )
        if persisted_specs != current_specs:
            raise ValueError("Persisted encoder taxonomy does not match the current taxonomy")
        encoder.fit_metadata = payload.get("fit_metadata", {})
        encoder.fitted = True
        return encoder
