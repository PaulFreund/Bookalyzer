"""Plots whose summary marks are computed directly from result tables."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def group_summary(frame: pd.DataFrame, group: str, value: str) -> pd.DataFrame:
    return (
        frame.groupby(group, observed=True)[value]
        .agg(n="count", mean="mean", median="median", minimum="min", maximum="max")
        .reset_index()
    )


def violin_plot(
    frame: pd.DataFrame,
    *,
    group: str,
    value: str,
    order: Sequence[str] | None,
    title: str,
    subtitle: str,
    ylabel: str,
    png_path: str | Path,
    svg_path: str | Path,
) -> pd.DataFrame:
    if frame.empty:
        raise ValueError("Cannot plot an empty result table")
    labels = list(order) if order is not None else list(dict.fromkeys(frame[group].astype(str)))
    values = [
        frame.loc[frame[group].astype(str) == label, value].dropna().astype(float).to_numpy()
        for label in labels
    ]
    missing = [label for label, data in zip(labels, values) if len(data) == 0]
    if missing:
        raise ValueError(f"Plot groups have no observations: {', '.join(missing)}")

    width = max(8.0, 1.15 * len(labels))
    figure, axis = plt.subplots(figsize=(width, 6.5), constrained_layout=True)
    multi_positions = [index + 1 for index, data in enumerate(values) if len(data) > 1]
    multi_values = [data for data in values if len(data) > 1]
    if multi_values:
        violin_width = 0.55 if len(labels) == 1 else 0.82
        violin = axis.violinplot(
            multi_values,
            positions=multi_positions,
            showmeans=False,
            showmedians=False,
            showextrema=False,
            widths=violin_width,
        )
        for body in violin["bodies"]:
            body.set_facecolor("#5B8FF9")
            body.set_edgecolor("#244A7C")
            body.set_alpha(0.72)

    rng = np.random.default_rng(20260413)
    for position, data in enumerate(values, 1):
        if len(data) == 1:
            axis.scatter([position], data, color="#244A7C", s=35, zorder=3)
        elif len(data) <= 40:
            jitter = rng.uniform(-0.08, 0.08, len(data))
            axis.scatter(position + jitter, data, color="#244A7C", s=8, alpha=0.35, zorder=3)
        mean = float(np.mean(data))
        median = float(np.median(data))
        axis.hlines(mean, position - 0.32, position + 0.32, colors="#111111", linewidth=2.0)
        axis.hlines(
            median,
            position - 0.32,
            position + 0.32,
            colors="#111111",
            linewidth=1.8,
            linestyles="dashed",
        )
        axis.text(position, -0.055, f"n={len(data)}", ha="center", va="top", transform=axis.get_xaxis_transform())

    axis.plot([], [], color="#111111", linewidth=2.0, label="Mean")
    axis.plot([], [], color="#111111", linewidth=1.8, linestyle="dashed", label="Median")
    axis.set_xticks(range(1, len(labels) + 1), labels, rotation=20, ha="right")
    axis.set_ylabel(ylabel)
    axis.set_title(f"{title}\n{subtitle}", loc="left", fontsize=13, pad=14)
    axis.grid(axis="y", alpha=0.2)
    axis.legend(frameon=False, loc="upper right")
    if value.endswith("percentile"):
        axis.set_ylim(0, 1)
    for target in (Path(png_path), Path(svg_path)):
        target.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(png_path, dpi=220)
    figure.savefig(svg_path)
    plt.close(figure)
    return group_summary(frame.assign(**{group: frame[group].astype(str)}), group, value)


def plot_book_rarity(
    frame: pd.DataFrame,
    *,
    png_path: str | Path,
    svg_path: str | Path,
) -> pd.DataFrame:
    feature_sets = sorted(frame["feature_set"].dropna().astype(str).unique())
    if len(feature_sets) != 1:
        raise ValueError("Book plot requires exactly one feature set")
    order = list(dict.fromkeys(frame.sort_values(["book_title", "segment_index"])["book_title"].astype(str)))
    return violin_plot(
        frame,
        group="book_title",
        value="rarity_percentile",
        order=order,
        title="Per-segment narrative rarity by book",
        subtitle=f"Feature set: {feature_sets[0]} · Reference: StoryScope train + validation",
        ylabel="Rarity percentile vs. StoryScope train + validation",
        png_path=png_path,
        svg_path=svg_path,
    )


def plot_figure5_reconstruction(
    frame: pd.DataFrame,
    *,
    feature_set: str,
    source_order: Sequence[str],
    png_path: str | Path,
    svg_path: str | Path,
) -> pd.DataFrame:
    present = set(frame["source"].astype(str))
    order = [source for source in source_order if source in present]
    return violin_plot(
        frame,
        group="source",
        value="rarity_percentile",
        order=order,
        title="StoryScope Figure 5 — public-artifacts reconstruction",
        subtitle=f"Feature set: {feature_set} · Reference: pooled train + validation · k=25 exact Euclidean",
        ylabel="Narrative rarity percentile",
        png_path=png_path,
        svg_path=svg_path,
    )


def plot_rarity_sequence(
    frame: pd.DataFrame,
    *,
    png_path: str | Path,
    svg_path: str | Path,
) -> None:
    figure, axis = plt.subplots(figsize=(10, 5.5), constrained_layout=True)
    for book_title, group in frame.groupby("book_title", sort=True):
        ordered = group.sort_values("segment_index")
        axis.plot(
            ordered["segment_index"].astype(int) + 1,
            ordered["rarity_percentile"],
            marker="o",
            linewidth=1.5,
            label=str(book_title),
        )
    axis.set_xlabel("Segment in reading order")
    axis.set_ylabel("Rarity percentile vs. StoryScope train + validation")
    axis.set_ylim(0, 1)
    axis.set_title("Narrative rarity along each book", loc="left")
    axis.grid(alpha=0.2)
    axis.legend(frameon=False)
    for target in (Path(png_path), Path(svg_path)):
        target.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(png_path, dpi=220)
    figure.savefig(svg_path)
    plt.close(figure)


def plot_internal_book_rarity(
    frame: pd.DataFrame,
    *,
    png_path: str | Path,
    svg_path: str | Path,
) -> pd.DataFrame:
    """Plot book-local rarity without implying an external StoryScope percentile."""
    feature_sets = sorted(frame["feature_set"].dropna().astype(str).unique())
    if len(feature_sets) != 1:
        raise ValueError("Internal book plot requires exactly one feature set")
    order = list(dict.fromkeys(frame.sort_values(["book_title", "segment_index"])["book_title"].astype(str)))
    reference_count = int(frame["internal_k"].max()) if "internal_k" in frame else max(len(frame) - 1, 0)
    return violin_plot(
        frame,
        group="book_title",
        value="internal_raw_rarity",
        order=order,
        title="Book-internal narrative feature distance",
        subtitle=(
            f"{feature_sets[0]} · reference: {reference_count} other segments\n"
            "Codex exploratory extraction"
        ),
        ylabel="Mean Euclidean distance to other segments",
        png_path=png_path,
        svg_path=svg_path,
    )


def plot_internal_rarity_sequence(
    frame: pd.DataFrame,
    *,
    png_path: str | Path,
    svg_path: str | Path,
) -> None:
    figure, axis = plt.subplots(figsize=(11, 5.8), constrained_layout=True)
    for book_title, group in frame.groupby("book_title", sort=True):
        ordered = group.sort_values("segment_index")
        axis.plot(
            ordered["segment_index"].astype(int) + 1,
            ordered["internal_raw_rarity"],
            marker="o",
            linewidth=1.7,
            label=str(book_title),
        )
    axis.set_xlabel("Segment in reading order")
    axis.set_ylabel("Mean Euclidean distance to other segments")
    axis.set_title("Narrative feature distance through the book — Codex exploratory extraction", loc="left")
    axis.grid(alpha=0.2)
    axis.legend(frameon=False)
    for target in (Path(png_path), Path(svg_path)):
        target.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(png_path, dpi=220)
    figure.savefig(svg_path)
    plt.close(figure)


def plot_segment_distance_matrix(
    frame: pd.DataFrame,
    standardized_matrix: np.ndarray,
    *,
    png_path: str | Path,
    svg_path: str | Path,
) -> pd.DataFrame:
    """Plot exact pairwise distances among segments in reading order."""
    order = np.argsort(frame["segment_index"].astype(int).to_numpy())
    ordered = frame.iloc[order].reset_index(drop=True)
    matrix = np.asarray(standardized_matrix, dtype=np.float64)[order]
    squared = np.maximum(
        np.einsum("ij,ij->i", matrix, matrix)[:, None]
        + np.einsum("ij,ij->i", matrix, matrix)[None, :]
        - 2 * matrix @ matrix.T,
        0,
    )
    distances = np.sqrt(squared)
    labels = [str(int(value) + 1) for value in ordered["segment_index"]]
    distance_frame = pd.DataFrame(distances, index=labels, columns=labels)
    size = max(7.5, min(12.0, len(labels) * 0.55))
    figure, axis = plt.subplots(figsize=(size, size), constrained_layout=True)
    image = axis.imshow(distances, cmap="viridis")
    axis.set_xticks(range(len(labels)), labels)
    axis.set_yticks(range(len(labels)), labels)
    axis.set_xlabel("Segment")
    axis.set_ylabel("Segment")
    axis.set_title("Segment-to-segment distance — book-local standardized feature space", loc="left")
    figure.colorbar(image, ax=axis, label="Euclidean distance")
    for target in (Path(png_path), Path(svg_path)):
        target.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(png_path, dpi=220)
    figure.savefig(svg_path)
    plt.close(figure)
    return distance_frame


def plot_book_distance_matrix(
    frame: pd.DataFrame,
    standardized_matrix: np.ndarray,
    *,
    png_path: str | Path,
    svg_path: str | Path,
) -> pd.DataFrame:
    books = sorted(frame["book_title"].astype(str).unique())
    centroids = np.vstack(
        [standardized_matrix[frame["book_title"].astype(str).to_numpy() == book].mean(axis=0) for book in books]
    )
    squared = np.maximum(
        np.einsum("ij,ij->i", centroids, centroids)[:, None]
        + np.einsum("ij,ij->i", centroids, centroids)[None, :]
        - 2 * centroids @ centroids.T,
        0,
    )
    distances = np.sqrt(squared)
    distance_frame = pd.DataFrame(distances, index=books, columns=books)
    figure, axis = plt.subplots(figsize=(max(6, len(books)), max(5, len(books) * 0.8)), constrained_layout=True)
    image = axis.imshow(distances, cmap="viridis")
    axis.set_xticks(range(len(books)), books, rotation=30, ha="right")
    axis.set_yticks(range(len(books)), books)
    axis.set_title("Book-to-book centroid distance (standardized feature space)", loc="left")
    figure.colorbar(image, ax=axis, label="Euclidean distance")
    for target in (Path(png_path), Path(svg_path)):
        target.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(png_path, dpi=220)
    figure.savefig(svg_path)
    plt.close(figure)
    return distance_frame
