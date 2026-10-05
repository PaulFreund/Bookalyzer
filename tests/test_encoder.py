from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from bookanalyzer.feature_matrix import (
    FeatureSetBlockedError,
    FeatureValidationError,
    load_taxonomy,
    resolve_feature_set,
)
from bookanalyzer.paper_encoder import PaperEncoder
from bookanalyzer.feature_matrix import parse_multi_select


def test_multi_select_accepts_parquet_numpy_arrays() -> None:
    assert parse_multi_select(np.array(["x", "y"], dtype=object)) == ["x", "y"]


def test_taxonomy_ids_once_and_paper_dimensions() -> None:
    _, specs = load_taxonomy("data/reference/storyscope/taxonomy.json")
    assert len(specs) == len(set(specs)) == 304
    full = resolve_feature_set("full_304", specs)
    nonstyle = resolve_feature_set("public_nonstyle_265", specs)
    style = [feature_id for feature_id, spec in specs.items() if spec.dimension_key == "style"]
    assert len(nonstyle) == 265
    assert PaperEncoder(specs, full).encoded_dimension == 1108
    assert PaperEncoder(specs, style).encoded_dimension == 129
    assert PaperEncoder(specs, nonstyle).encoded_dimension == 979
    with pytest.raises(FeatureSetBlockedError):
        resolve_feature_set("paper_narrative_257", specs)


def test_encoder_types_and_ordinal_order(small_specs) -> None:
    frame = pd.DataFrame(
        [
            {"CAT": "a", "BIN": "yes", "MUL": "x|y", "ORD": "low", "SCL": "1"},
            {"CAT": "b", "BIN": "no", "MUL": "y", "ORD": "high", "SCL": "3"},
            {"CAT": "n/a", "BIN": "n/a", "MUL": "n/a", "ORD": "n/a", "SCL": "n/a"},
        ]
    )
    encoder = PaperEncoder(small_specs, list(small_specs)).fit(frame)
    matrix = encoder.transform(frame)
    assert matrix.shape == (3, 11)
    ordinal_index = encoder.columns.index("ORD")
    scale_index = encoder.columns.index("SCL")
    assert matrix[:, ordinal_index].tolist() == [0.0, 2.0, -1.0]
    assert matrix[:, scale_index].tolist() == [1.0, 3.0, -1.0]
    assert matrix[0, encoder.columns.index("MUL__x")] == 1
    assert matrix[0, encoder.columns.index("MUL__y")] == 1


def test_unknown_category_is_an_error(small_specs) -> None:
    frame = pd.DataFrame(
        [{"CAT": "new", "BIN": "yes", "MUL": "x", "ORD": "low", "SCL": "1"}]
    )
    with pytest.raises(FeatureValidationError, match="CAT"):
        PaperEncoder(small_specs, list(small_specs)).fit(frame)


def test_encoder_round_trip(tmp_path, small_specs) -> None:
    frame = pd.DataFrame(
        [{"CAT": "a", "BIN": "yes", "MUL": "x", "ORD": "medium", "SCL": "2"}]
    )
    encoder = PaperEncoder(small_specs, list(small_specs)).fit(frame)
    path = tmp_path / "encoder.json"
    encoder.save(path)
    loaded = PaperEncoder.load(path, small_specs)
    np.testing.assert_array_equal(encoder.transform(frame), loaded.transform(frame))
