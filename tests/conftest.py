from __future__ import annotations

import re
import shutil
from pathlib import Path

import pandas as pd
import pytest

from bookanalyzer.feature_matrix import FeatureSpec, load_taxonomy


@pytest.fixture(autouse=True)
def isolated_codex_catalog(monkeypatch):
    # Unit tests never inspect the developer's real account or installed model catalog.
    monkeypatch.setattr("bookanalyzer.codex_catalog.read_models", lambda: [])


@pytest.fixture
def small_specs() -> dict[str, FeatureSpec]:
    return {
        "CAT": FeatureSpec("CAT", "Category", "categorical", ("a", "b"), "narrative", "Narrative"),
        "BIN": FeatureSpec("BIN", "Binary", "binary", ("yes", "no"), "narrative", "Narrative"),
        "MUL": FeatureSpec("MUL", "Multi", "multi_select", ("x", "y"), "narrative", "Narrative"),
        "ORD": FeatureSpec("ORD", "Ordinal", "ordinal", ("low", "medium", "high"), "narrative", "Narrative"),
        "SCL": FeatureSpec("SCL", "Scale", "scale", ("1", "2", "3"), "narrative", "Narrative"),
    }


def valid_taxonomy_row(specs: dict[str, FeatureSpec], *, prompt_id: int, source: str = "human") -> dict:
    row: dict[str, object] = {
        "prompt_id": prompt_id,
        "story_title": f"Story {prompt_id}",
        "source": source,
    }
    for feature_id, spec in specs.items():
        if spec.feature_type == "multi_select":
            row[feature_id] = spec.values[0] if spec.values else "n/a"
        elif spec.feature_type == "scale":
            match = re.match(r"^\s*(-?\d+(?:\.\d+)?)", spec.values[0]) if spec.values else None
            row[feature_id] = match.group(1) if match else "1"
        else:
            row[feature_id] = spec.values[0] if spec.values else "n/a"
    return row


@pytest.fixture
def tiny_reference(tmp_path: Path) -> dict:
    reference = tmp_path / "reference"
    cache = tmp_path / "cache"
    reference.mkdir()
    taxonomy_source = Path(__file__).parents[1] / "data" / "reference" / "storyscope" / "taxonomy.json"
    shutil.copyfile(taxonomy_source, reference / "taxonomy.json")
    _, specs = load_taxonomy(reference / "taxonomy.json")
    rows = [valid_taxonomy_row(specs, prompt_id=index) for index in (1, 2, 3)]
    # Ensure the train+validation scaler sees variance that the test row cannot influence.
    categorical_id = next(
        feature_id
        for feature_id, spec in specs.items()
        if spec.feature_type == "categorical" and len(spec.values) >= 2
    )
    rows[1][categorical_id] = specs[categorical_id].values[1]
    rows[2][categorical_id] = specs[categorical_id].values[-1]
    pd.DataFrame(rows).to_parquet(reference / "storyscope_features.parquet", index=False)
    pd.DataFrame({"prompt_id": [1], "split": ["train"]}).to_parquet(
        reference / "stories_train.parquet", index=False
    )
    pd.DataFrame({"prompt_id": [2], "split": ["val"]}).to_parquet(
        reference / "stories_val.parquet", index=False
    )
    pd.DataFrame({"prompt_id": [3], "split": ["test"]}).to_parquet(
        reference / "stories_test.parquet", index=False
    )
    return {
        "reference": reference,
        "cache": cache,
        "specs": specs,
        "rows": rows,
        "categorical_id": categorical_id,
    }
