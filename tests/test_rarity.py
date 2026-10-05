from __future__ import annotations

import json

import numpy as np

from bookanalyzer.rarity import ExactKNNIndex, build_reference, empirical_percentile


def test_exact_knn_removes_self_and_uses_25_neighbors() -> None:
    reference = np.arange(30, dtype=np.float32)[:, None]
    index = ExactKNNIndex(reference, backend="numpy", reference_block_size=7)
    excluded = np.arange(len(reference), dtype=np.int64)
    distances, neighbors = index.search(reference, 25, exclude_reference_indices=excluded)
    assert distances.shape == neighbors.shape == (30, 25)
    assert all(row not in neighbors[row] for row in range(30))
    brute = np.abs(reference[:, 0, None] - reference[:, 0][None, :])
    np.fill_diagonal(brute, np.inf)
    expected = np.sort(brute, axis=1)[:, :25]
    np.testing.assert_allclose(distances, expected)


def test_empirical_percentile_range_and_ties() -> None:
    reference = np.array([1.0, 2.0, 2.0, 4.0])
    values = np.array([0.0, 2.0, 5.0])
    percentiles = empirical_percentile(reference, values, tie_method="right")
    np.testing.assert_allclose(percentiles, [0.0, 0.75, 1.0])
    assert np.all((0 <= percentiles) & (percentiles <= 1))


def test_scaler_is_fitted_only_on_train_and_validation(tiny_reference) -> None:
    artifacts = build_reference(
        feature_set="full_304",
        reference_dir=tiny_reference["reference"],
        cache_dir=tiny_reference["cache"],
        source_order=["human"],
    )
    assert len(artifacts.matrix) == 2
    assert int(artifacts.scaler.n_samples_seen_) == 2
    with (tiny_reference["cache"] / "reference_manifest.json").open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    assert manifest["reference_splits"] == ["train", "val"]
    assert manifest["scaler_fit_rows"] == 2
