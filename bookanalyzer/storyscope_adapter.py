"""Audited adapter around StoryScope's unmodified Stage 5 implementation."""

from __future__ import annotations

import importlib
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from .config import load_yaml, project_path
from .feature_matrix import (
    FeatureValidationError,
    load_taxonomy,
    validate_feature_frame,
)
from .provenance import (
    assert_storyscope_immutable,
    new_run_id,
    sha256_file,
    utc_now,
    write_json,
)
from .segment import assert_segments_approved


EXPECTED_PROVIDER = "vertex"
EXPECTED_MODEL = "gemini-3-flash-preview"
RIGHTS_CONFIRMATION = "I confirm that the rights holder approved external processing"


def record_rights_approval(
    *,
    rights_holder: str,
    approver: str,
    confirmation: str,
    provider: str = EXPECTED_PROVIDER,
    model: str = EXPECTED_MODEL,
    authorization_note: str = "",
    segments_path: str | Path = "data/processed/book_segments.parquet",
    output_path: str | Path = "config/rights_approval.yaml",
) -> Path:
    if confirmation != RIGHTS_CONFIRMATION:
        raise ValueError(
            "The exact confirmation text is required; no external-processing approval was recorded."
        )
    if not rights_holder.strip() or not approver.strip():
        raise ValueError("Both rights holder and approver are required")
    if not provider.strip() or not model.strip():
        raise ValueError("Both provider and model are required")
    import yaml

    segments = project_path(segments_path)
    payload = {
        "approved": True,
        "approved_at_utc": utc_now(),
        "rights_holder": rights_holder.strip(),
        "approver": approver.strip(),
        "scope": {
            "segments_path": str(segments),
            "segments_sha256": sha256_file(segments),
            "provider": provider.strip(),
            "model": model.strip(),
        },
        "authorization_note": authorization_note.strip(),
    }
    target = project_path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    temporary.replace(target)
    return target


def assert_rights_approval(
    segments_path: str | Path = "data/processed/book_segments.parquet",
    approval_path: str | Path = "config/rights_approval.yaml",
    *,
    provider: str = EXPECTED_PROVIDER,
    model: str = EXPECTED_MODEL,
) -> dict[str, Any]:
    approval_file = project_path(approval_path)
    if not approval_file.is_file():
        raise RuntimeError(
            "External processing is not authorized. A rights-holder approval record is required."
        )
    approval = load_yaml(approval_file)
    segments = project_path(segments_path)
    scope = approval.get("scope", {})
    if approval.get("approved") is not True:
        raise RuntimeError("Rights-holder approval record is not affirmative")
    if scope.get("segments_sha256") != sha256_file(segments):
        raise RuntimeError("Rights-holder approval does not cover the current segment file")
    if scope.get("provider") != provider or scope.get("model") != model:
        raise RuntimeError("Rights-holder approval does not cover the configured provider/model")
    return approval


def _load_stage5(vendor_dir: Path):
    vendor_text = str(vendor_dir)
    if vendor_text not in sys.path:
        sys.path.insert(0, vendor_text)
    return importlib.import_module("storyscope.5_feature_application.apply_features")


def _validate_model_config(path: str | Path) -> dict[str, Any]:
    config = load_yaml(path)
    stage = config.get("pipeline", {}).get("feature_application", {})
    if stage.get("provider") != EXPECTED_PROVIDER:
        raise RuntimeError(
            f"Feature extraction provider must be {EXPECTED_PROVIDER!r}, found {stage.get('provider')!r}"
        )
    if stage.get("model") != EXPECTED_MODEL:
        raise RuntimeError(
            f"Feature extraction model must be {EXPECTED_MODEL!r}, found {stage.get('model')!r}"
        )
    if stage.get("allow_model_fallback") is not False:
        raise RuntimeError("allow_model_fallback must be explicitly false")
    if stage.get("response_mime_type") != "application/json":
        raise RuntimeError("JSON response mode must be configured")
    return config


def select_pilot_segments(frame: pd.DataFrame, limit: int) -> pd.DataFrame:
    if limit < 1:
        raise ValueError("Pilot size must be positive")
    candidates: list[int] = []
    for _, group in frame.groupby("book_id", sort=True):
        ordered = group.sort_values("segment_index")
        indices = [ordered.index[0], ordered.index[len(ordered) // 2], ordered.index[-1]]
        indices.extend([ordered["word_count"].idxmin(), ordered["word_count"].idxmax()])
        candidates.extend(indices)
    selected: list[int] = []
    for index in candidates:
        if index not in selected:
            selected.append(index)
    if len(selected) < limit:
        selected.extend(index for index in frame.index if index not in selected)
    return frame.loc[selected[:limit]].sort_values(["book_id", "segment_index"]).reset_index(drop=True)


@dataclass
class RecordedCall:
    dimension: str
    raw_path: Path
    duration_seconds: float


class RecordingProvider:
    """Capture pre-normalization JSON while delegating generation unchanged."""

    def __init__(self, provider: Any, raw_response_dir: Path):
        self.provider = provider
        self.model = provider.model
        self.raw_response_dir = raw_response_dir
        self.raw_response_dir.mkdir(parents=True, exist_ok=True)
        self.calls: list[RecordedCall] = []
        self._lock = threading.Lock()

    def generate_json(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        match = re.search(r"specializing in ([^.\n]+)", prompt, flags=re.IGNORECASE)
        dimension = re.sub(r"[^a-z0-9]+", "_", match.group(1).lower()).strip("_") if match else "unknown"
        started = time.perf_counter()
        result = self.provider.generate_json(prompt, **kwargs)
        duration = time.perf_counter() - started
        with self._lock:
            suffix = len([call for call in self.calls if call.dimension == dimension])
            name = f"{dimension}{f'_{suffix}' if suffix else ''}.json"
            raw_path = self.raw_response_dir / name
            write_json(
                raw_path,
                {
                    "dimension": dimension,
                    "model": self.model,
                    "duration_seconds": duration,
                    "response": result,
                },
            )
            self.calls.append(RecordedCall(dimension, raw_path, duration))
        return result


def _normalization_log(calls: Sequence[RecordedCall], normalized: dict[str, Any]) -> list[dict[str, Any]]:
    raw_values: dict[str, Any] = {}
    for call in calls:
        with call.raw_path.open("r", encoding="utf-8") as handle:
            response = json.load(handle).get("response", {})
        raw_values.update({key: value for key, value in response.items() if not key.startswith("_")})
    decisions = []
    for feature_id in sorted(set(raw_values) | set(normalized)):
        raw = raw_values.get(feature_id, "__MISSING__")
        final = normalized.get(feature_id, "__MISSING__")
        if raw != final:
            decisions.append({"feature_id": feature_id, "raw": raw, "normalized": final})
    return decisions


def extract_features(
    *,
    segments_path: str | Path = "data/processed/book_segments.parquet",
    taxonomy_path: str | Path = "vendor/storyscope/data/taxonomy.json",
    output_dir: str | Path = "data/features/raw",
    model_config_path: str | Path = "config/models.yaml",
    vendor_dir: str | Path = "vendor/storyscope",
    parallel: int = 4,
    dim_workers: int = 5,
    pilot: int | None = None,
    resume: bool = True,
) -> dict[str, Any]:
    assert_storyscope_immutable(vendor_dir)
    segment_approval = assert_segments_approved(segments_path)
    rights_approval = assert_rights_approval(segments_path)
    config = _validate_model_config(model_config_path)
    stage_config = config["pipeline"]["feature_application"]
    provider_config = config.get("providers", {}).get(EXPECTED_PROVIDER, {})
    project = provider_config.get("project") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise RuntimeError(
            "Vertex project is not configured. Set GOOGLE_CLOUD_PROJECT or providers.vertex.project."
        )

    vendor = project_path(vendor_dir)
    stage5 = _load_stage5(vendor)
    vertex_module = importlib.import_module("storyscope.providers.vertex_provider")
    base_provider = vertex_module.VertexProvider(
        model=stage_config["model"],
        max_tokens=int(stage_config["max_tokens"]),
        project=project,
        location=provider_config.get("location", "us-central1"),
    )
    taxonomy = stage5.Taxonomy.from_json(str(project_path(taxonomy_path)))
    _, specs = load_taxonomy(taxonomy_path)
    segments = pd.read_parquet(project_path(segments_path))
    selected = select_pilot_segments(segments, pilot) if pilot is not None else segments.copy()
    run_id = new_run_id("extract-pilot" if pilot is not None else "extract")
    root = project_path(output_dir)
    source_dir = root / "human"
    response_root = root.parent / "raw_responses" / run_id
    source_dir.mkdir(parents=True, exist_ok=True)

    tasks: list[tuple[pd.Series, Path]] = []
    for _, row in selected.iterrows():
        safe_title = stage5.safe_filename(str(row["title"]))
        output_path = source_dir / f"prompt_{int(row['prompt_id']):05d}__{safe_title}.features.json"
        if resume and output_path.is_file():
            continue
        tasks.append((row, output_path))

    started_at = utc_now()
    failures: list[dict[str, Any]] = []

    def worker(row: pd.Series, output_path: Path) -> dict[str, Any]:
        prompt_id = int(row["prompt_id"])
        recording_provider = RecordingProvider(base_provider, response_root / f"prompt_{prompt_id:05d}")
        started = time.perf_counter()
        features, dimension_details = stage5.extract_story_features(
            recording_provider,
            taxonomy,
            str(row["human_story"]),
            dim_workers=dim_workers,
        )
        duration = time.perf_counter() - started
        missing = set(specs).difference(features)
        unknown = set(features).difference(specs)
        if missing or unknown:
            raise FeatureValidationError(
                f"prompt {prompt_id}: {len(missing)} missing and {len(unknown)} unknown features; "
                f"dimension details={dimension_details}"
            )
        validate_feature_frame(pd.DataFrame([{**features}]), specs)
        payload = {
            "story_title": str(row["title"]),
            "prompt_id": prompt_id,
            "segment_id": str(row["segment_id"]),
            "book_id": str(row["book_id"]),
            "author": "human",
            "features": features,
            "metadata": {
                "run_id": run_id,
                "provider": EXPECTED_PROVIDER,
                "model": base_provider.model,
                "region": provider_config.get("location", "us-central1"),
                "total_features": taxonomy.total_features,
                "features_extracted": len(features),
                "dimension_details": dimension_details,
                "duration_seconds": duration,
                "resume_enabled": resume,
                "raw_response_paths": [str(call.raw_path) for call in recording_provider.calls],
                "normalization_decisions": _normalization_log(recording_provider.calls, features),
            },
        }
        write_json(output_path, payload)
        return {"prompt_id": prompt_id, "output": str(output_path), "duration_seconds": duration}

    successes: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(worker, row, path): (row, path) for row, path in tasks}
        for future in as_completed(futures):
            row, output_path = futures[future]
            try:
                successes.append(future.result())
            except Exception as error:
                failures.append(
                    {
                        "prompt_id": int(row["prompt_id"]),
                        "segment_id": str(row["segment_id"]),
                        "output": str(output_path),
                        "error": repr(error),
                    }
                )
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "provider": EXPECTED_PROVIDER,
        "model": EXPECTED_MODEL,
        "region": provider_config.get("location", "us-central1"),
        "thinking_mode_requested": stage_config.get("thinking_mode"),
        "thinking_mode_note": (
            "The immutable published Vertex provider does not expose a thinking parameter; "
            "no undocumented provider patch was applied."
        ),
        "json_response_mode": True,
        "selected_segments": int(len(selected)),
        "new_tasks": len(tasks),
        "successful": len(successes),
        "failed": len(failures),
        "successes": sorted(successes, key=lambda item: item["prompt_id"]),
        "failures": sorted(failures, key=lambda item: item["prompt_id"]),
        "segment_approval": segment_approval,
        "rights_approval": rights_approval,
        "segments_sha256": sha256_file(project_path(segments_path)),
        "taxonomy_sha256": sha256_file(project_path(taxonomy_path)),
        "model_config_sha256": sha256_file(project_path(model_config_path)),
        "storyscope_commit": "642e746804e1ee4138ffdcf13b7412eb3dc2a70b",
        "parallel": parallel,
        "dimension_workers": dim_workers,
        "resume": resume,
        "pilot": pilot,
    }
    manifest_path = root.parent / f"{run_id}.manifest.json"
    write_json(manifest_path, manifest)
    if failures:
        raise RuntimeError(
            f"Feature extraction had {len(failures)} failures; see {manifest_path}. "
            "Resume is safe after correcting the cause."
        )
    return manifest
