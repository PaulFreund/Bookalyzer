"""Resumable StoryScope Stage 5 extraction through the authenticated Codex CLI.

This is an explicitly exploratory provider path.  It keeps the published
per-dimension prompts and normalization logic, but it does not claim the model
equivalence required for a paper-compatible StoryScope reproduction.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd

from .config import PROJECT_ROOT, load_yaml, project_path
from .feature_matrix import FeatureValidationError, load_taxonomy, validate_feature_frame
from .provenance import (
    assert_storyscope_immutable,
    new_run_id,
    sha256_file,
    sha256_text,
    utc_now,
    write_json,
)
from .segment import assert_segments_approved
from .storyscope_adapter import assert_rights_approval, select_pilot_segments


CODEX_PROVIDER = "codex-cli"
DEFAULT_CODEX_MODEL = "gpt-5.6-sol"
DEFAULT_REASONING_EFFORT = "low"
_ALLOWED_REASONING_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}


def _load_stage5(vendor_dir: Path):
    vendor_text = str(vendor_dir)
    if vendor_text not in sys.path:
        sys.path.insert(0, vendor_text)
    return importlib.import_module("storyscope.5_feature_application.apply_features")


def _codex_config_path() -> Path:
    configured = os.environ.get("CODEX_HOME")
    root = Path(configured) if configured else Path.home() / ".codex"
    return root / "config.toml"


def configured_codex_model(default: str = DEFAULT_CODEX_MODEL) -> str:
    """Return the local CLI's configured model without exposing other settings."""
    path = _codex_config_path()
    if not path.is_file():
        return default
    try:
        with path.open("rb") as handle:
            payload = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return default
    model = payload.get("model")
    return str(model).strip() if model else default


def resolve_codex_executable(executable: str = "codex") -> Path:
    if executable == "codex" and os.environ.get("BOOKANALYZER_CODEX"):
        executable = os.environ["BOOKANALYZER_CODEX"]
    resolved = shutil.which(executable)
    if sys.platform == "win32" and executable == "codex":
        # Some older desktop helpers leave a shim pointing to a stale plugin binary.
        legacy_shim = False
        if resolved and Path(resolved).suffix.lower() in (".cmd", ".bat"):
            try:
                legacy_shim = ".plugin-appserver" in Path(resolved).read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
        if not resolved or legacy_shim:
            local = os.environ.get("LOCALAPPDATA")
            if local:
                candidates = list((Path(local) / "OpenAI/Codex/bin").glob("*/codex.exe"))
                if candidates:
                    resolved = str(max(candidates, key=lambda path: path.stat().st_mtime))
    if not resolved and sys.platform == "darwin" and executable == "codex":
        for directory in (Path("/opt/homebrew/bin"), Path("/usr/local/bin"), Path.home() / ".local/bin"):
            candidate = directory / "codex"
            if candidate.is_file() and os.access(candidate, os.X_OK):
                resolved = str(candidate)
                break
    if not resolved:
        raise FileNotFoundError(
            "Codex CLI is not installed or is not on PATH; no alternative provider was used."
        )
    return Path(resolved)


def codex_cli_version(executable: str | Path) -> str:
    result = subprocess.run(
        [str(executable), "--version"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Unable to read Codex CLI version: {result.stderr.strip()}")
    return result.stdout.strip()


def _number_from_taxonomy_value(value: Any) -> int | float | None:
    match = re.match(r"^\s*(-?\d+(?:\.\d+)?)", str(value))
    if not match:
        return None
    number = float(match.group(1))
    return int(number) if number.is_integer() else number


def dimension_output_schema(dimension: Any) -> dict[str, Any]:
    """Build an exact JSON Schema for one published StoryScope dimension."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for feature in dimension.features:
        values = [str(value) for value in feature.values]
        if feature.type == "multi_select":
            base: dict[str, Any] = {
                "type": "array",
                "items": {"type": "string", "enum": values},
            }
        elif feature.type == "scale":
            numbers = [
                number
                for number in (_number_from_taxonomy_value(value) for value in feature.values)
                if number is not None
            ]
            base = {"type": "number", "enum": list(dict.fromkeys(numbers))}
        else:
            base = {"type": "string", "enum": values}
        if feature.condition:
            base = {"anyOf": [base, {"type": "string", "enum": ["n/a"]}]}
        properties[feature.id] = base
        required.append(feature.id)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _validate_dimension_response(response: Any, dimension: Any) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise FeatureValidationError(
            f"Dimension {dimension.key} returned {type(response).__name__}, expected an object"
        )
    expected = {feature.id for feature in dimension.features}
    actual = set(response)
    missing = expected.difference(actual)
    unknown = actual.difference(expected)
    if missing or unknown:
        raise FeatureValidationError(
            f"Dimension {dimension.key} has {len(missing)} missing and {len(unknown)} unknown keys"
        )
    return response


def _run_codex_dimension(
    *,
    executable: Path,
    model: str,
    reasoning_effort: str,
    prompt: str,
    schema_path: Path,
    result_path: Path,
    timeout_seconds: int,
    attempts: int,
) -> tuple[dict[str, Any], float]:
    result_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = result_path.with_suffix(result_path.suffix + ".codex-tmp")
    temporary.unlink(missing_ok=True)
    instruction = (
        "This is a closed-set literary classification task. Do not browse, run commands, "
        "inspect files, or explain the result. Analyze only the story supplied below and return "
        "the JSON object required by the schema.\n\n"
    )
    command = [
        str(executable),
        "--ask-for-approval",
        "never",
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--model",
        model,
        "-c",
        f'model_reasoning_effort="{reasoning_effort}"',
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(temporary),
        "-",
    ]
    last_error = "Codex CLI did not run"
    for attempt in range(1, attempts + 1):
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                input=instruction + prompt,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
                timeout=timeout_seconds,
            )
            duration = time.perf_counter() - started
        except subprocess.TimeoutExpired as error:
            last_error = f"Codex CLI timed out after {timeout_seconds}s: {error}"
        else:
            if completed.returncode == 0 and temporary.is_file():
                try:
                    response = json.loads(temporary.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as error:
                    last_error = f"Codex returned invalid structured JSON: {error}"
                else:
                    temporary.unlink(missing_ok=True)
                    return response, duration
            else:
                stderr = completed.stderr.strip().replace("\x00", "")
                last_error = (
                    f"Codex CLI exited {completed.returncode}: "
                    f"{stderr[-2000:] if stderr else 'no diagnostic output'}"
                )
        temporary.unlink(missing_ok=True)
        if attempt < attempts:
            time.sleep(min(2**attempt, 8))
    raise RuntimeError(last_error)


def _cached_dimension(
    path: Path,
    *,
    prompt_hash: str,
    schema_hash: str,
    model: str,
    reasoning_effort: str,
    dimension: Any,
) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("provider") != CODEX_PROVIDER
            or payload.get("model") != model
            or payload.get("reasoning_effort") != reasoning_effort
            or payload.get("prompt_sha256") != prompt_hash
            or payload.get("schema_sha256") != schema_hash
        ):
            return None
        return _validate_dimension_response(payload.get("response"), dimension)
    except (OSError, json.JSONDecodeError, FeatureValidationError):
        return None


def extract_features_with_codex(
    *,
    segments_path: str | Path = "data/processed/book_segments.parquet",
    taxonomy_path: str | Path = "vendor/storyscope/data/taxonomy.json",
    output_dir: str | Path = "data/features/raw",
    response_dir: str | Path = "data/features/codex_responses",
    schema_dir: str | Path = "data/cache/codex_schemas",
    vendor_dir: str | Path = "vendor/storyscope",
    executable: str = "codex",
    model: str | None = None,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    parallel: int = 3,
    pilot: int | None = None,
    resume: bool = True,
    timeout_seconds: int = 900,
    attempts: int = 3,
    segment_approval_path: str | Path = "data/processed/segment_approval.json",
    rights_approval_path: str | Path = "config/rights_approval.yaml",
) -> dict[str, Any]:
    """Extract all 304 features with ten Codex calls per selected segment."""
    if parallel < 1:
        raise ValueError("parallel must be positive")
    if attempts < 1:
        raise ValueError("attempts must be positive")
    if reasoning_effort not in _ALLOWED_REASONING_EFFORTS:
        raise ValueError(f"Unsupported Codex reasoning effort: {reasoning_effort}")

    assert_storyscope_immutable(vendor_dir)
    resolved_model = model or configured_codex_model()
    segment_approval = assert_segments_approved(segments_path, segment_approval_path)
    rights_approval = assert_rights_approval(
        segments_path,
        approval_path=rights_approval_path,
        provider=CODEX_PROVIDER,
        model=resolved_model,
    )
    codex = resolve_codex_executable(executable)
    version = codex_cli_version(codex)
    stage5 = _load_stage5(project_path(vendor_dir))
    taxonomy = stage5.Taxonomy.from_json(str(project_path(taxonomy_path)))
    _, specs = load_taxonomy(taxonomy_path)
    segments = pd.read_parquet(project_path(segments_path))
    selected = select_pilot_segments(segments, pilot) if pilot is not None else segments.copy()

    run_id = new_run_id("extract-codex-pilot" if pilot is not None else "extract-codex")
    output_root = project_path(output_dir)
    source_dir = output_root / "human"
    response_root = project_path(response_dir)
    schemas = project_path(schema_dir)
    source_dir.mkdir(parents=True, exist_ok=True)
    response_root.mkdir(parents=True, exist_ok=True)
    schemas.mkdir(parents=True, exist_ok=True)

    schema_records: dict[str, tuple[Path, str]] = {}
    for dimension in taxonomy.dimensions:
        schema_path = schemas / f"{dimension.key}.schema.json"
        write_json(schema_path, dimension_output_schema(dimension))
        schema_records[dimension.key] = (schema_path, sha256_file(schema_path))

    rows: dict[int, pd.Series] = {}
    outputs: dict[int, Path] = {}
    skipped_outputs: list[str] = []
    for _, row in selected.iterrows():
        prompt_id = int(row["prompt_id"])
        rows[prompt_id] = row
        safe_title = stage5.safe_filename(str(row["title"]))
        output_path = source_dir / f"prompt_{prompt_id:05d}__{safe_title}.features.json"
        outputs[prompt_id] = output_path
        if resume and output_path.is_file():
            try:
                existing = json.loads(output_path.read_text(encoding="utf-8"))
                metadata = existing.get("metadata", {})
                features = existing.get("features", {})
                if (
                    existing.get("segment_id") == str(row["segment_id"])
                    and metadata.get("provider") == CODEX_PROVIDER
                    and metadata.get("model") == resolved_model
                    and metadata.get("reasoning_effort") == reasoning_effort
                    and set(features) == set(specs)
                ):
                    validate_feature_frame(pd.DataFrame([features]), specs)
                    skipped_outputs.append(str(output_path))
            except (OSError, json.JSONDecodeError, FeatureValidationError):
                pass

    skipped_ids = {
        prompt_id for prompt_id, path in outputs.items() if str(path) in skipped_outputs
    }
    tasks: list[tuple[int, Any, str, str, Path, str]] = []
    for prompt_id, row in rows.items():
        if prompt_id in skipped_ids:
            continue
        story = str(row["human_story"])
        for dimension in taxonomy.dimensions:
            prompt = stage5.build_dimension_prompt(dimension, story)
            prompt_hash = sha256_text(prompt)
            schema_path, schema_hash = schema_records[dimension.key]
            cache_path = response_root / f"prompt_{prompt_id:05d}" / f"{dimension.key}.json"
            tasks.append((prompt_id, dimension, prompt, prompt_hash, cache_path, schema_hash))

    started_at = utc_now()
    responses: dict[int, dict[str, dict[str, Any]]] = {prompt_id: {} for prompt_id in rows}
    details: dict[int, dict[str, dict[str, Any]]] = {prompt_id: {} for prompt_id in rows}
    failures: list[dict[str, Any]] = []
    cached_calls = 0
    new_calls = 0

    def worker(task: tuple[int, Any, str, str, Path, str]) -> dict[str, Any]:
        prompt_id, dimension, prompt, prompt_hash, cache_path, schema_hash = task
        schema_path, _ = schema_records[dimension.key]
        if resume:
            cached = _cached_dimension(
                cache_path,
                prompt_hash=prompt_hash,
                schema_hash=schema_hash,
                model=resolved_model,
                reasoning_effort=reasoning_effort,
                dimension=dimension,
            )
            if cached is not None:
                return {
                    "prompt_id": prompt_id,
                    "dimension": dimension.key,
                    "response": cached,
                    "cache_path": str(cache_path),
                    "cached": True,
                    "duration_seconds": 0.0,
                }
        response, duration = _run_codex_dimension(
            executable=codex,
            model=resolved_model,
            reasoning_effort=reasoning_effort,
            prompt=prompt,
            schema_path=schema_path,
            result_path=cache_path.with_suffix(".last-message.json"),
            timeout_seconds=timeout_seconds,
            attempts=attempts,
        )
        response = _validate_dimension_response(response, dimension)
        write_json(
            cache_path,
            {
                "schema_version": 1,
                "provider": CODEX_PROVIDER,
                "model": resolved_model,
                "reasoning_effort": reasoning_effort,
                "codex_cli_version": version,
                "prompt_id": prompt_id,
                "segment_id": str(rows[prompt_id]["segment_id"]),
                "dimension": dimension.key,
                "prompt_sha256": prompt_hash,
                "schema_sha256": schema_hash,
                "duration_seconds": duration,
                "created_at_utc": utc_now(),
                "response": response,
            },
        )
        return {
            "prompt_id": prompt_id,
            "dimension": dimension.key,
            "response": response,
            "cache_path": str(cache_path),
            "cached": False,
            "duration_seconds": duration,
        }

    completed_count = 0
    if tasks:
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {executor.submit(worker, task): task for task in tasks}
            for future in as_completed(futures):
                task = futures[future]
                prompt_id, dimension = task[0], task[1]
                completed_count += 1
                try:
                    result = future.result()
                    responses[prompt_id][dimension.key] = result["response"]
                    details[prompt_id][dimension.key] = {
                        "features_extracted": len(result["response"]),
                        "response_path": result["cache_path"],
                        "cached": result["cached"],
                        "duration_seconds": result["duration_seconds"],
                    }
                    if result["cached"]:
                        cached_calls += 1
                    else:
                        new_calls += 1
                except Exception as error:
                    failures.append(
                        {
                            "prompt_id": prompt_id,
                            "segment_id": str(rows[prompt_id]["segment_id"]),
                            "dimension": dimension.key,
                            "error": repr(error),
                        }
                    )
                print(
                    f"Codex dimensions: {completed_count}/{len(tasks)} "
                    f"({new_calls} new, {cached_calls} cached, {len(failures)} failed)",
                    flush=True,
                )

    failure_ids = {item["prompt_id"] for item in failures}
    completed_outputs: list[str] = []
    for prompt_id, row in rows.items():
        if prompt_id in skipped_ids or prompt_id in failure_ids:
            continue
        if set(responses[prompt_id]) != {dimension.key for dimension in taxonomy.dimensions}:
            failures.append(
                {
                    "prompt_id": prompt_id,
                    "segment_id": str(row["segment_id"]),
                    "dimension": "__aggregate__",
                    "error": "Not all ten dimension responses are available",
                }
            )
            continue
        raw_features: dict[str, Any] = {}
        for dimension in taxonomy.dimensions:
            raw_features.update(responses[prompt_id][dimension.key])
        features = stage5.normalize_features(raw_features, taxonomy)
        missing = set(specs).difference(features)
        unknown = set(features).difference(specs)
        if missing or unknown:
            failures.append(
                {
                    "prompt_id": prompt_id,
                    "segment_id": str(row["segment_id"]),
                    "dimension": "__aggregate__",
                    "error": f"{len(missing)} missing and {len(unknown)} unknown feature IDs",
                }
            )
            continue
        try:
            validate_feature_frame(pd.DataFrame([features]), specs)
        except FeatureValidationError as error:
            failures.append(
                {
                    "prompt_id": prompt_id,
                    "segment_id": str(row["segment_id"]),
                    "dimension": "__aggregate__",
                    "error": str(error),
                }
            )
            continue
        payload = {
            "story_title": str(row["title"]),
            "prompt_id": prompt_id,
            "segment_id": str(row["segment_id"]),
            "book_id": str(row["book_id"]),
            "author": "human",
            "features": features,
            "metadata": {
                "run_id": run_id,
                "provider": CODEX_PROVIDER,
                "model": resolved_model,
                "reasoning_effort": reasoning_effort,
                "codex_cli_version": version,
                "total_features": taxonomy.total_features,
                "features_extracted": len(features),
                "dimension_details": details[prompt_id],
                "resume_enabled": resume,
                "exploratory": True,
                "paper_compatible": False,
            },
        }
        write_json(outputs[prompt_id], payload)
        completed_outputs.append(str(outputs[prompt_id]))

    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "provider": CODEX_PROVIDER,
        "model": resolved_model,
        "reasoning_effort": reasoning_effort,
        "codex_cli_version": version,
        "selected_segments": int(len(selected)),
        "dimensions_per_segment": len(taxonomy.dimensions),
        "dimension_tasks": len(tasks),
        "new_dimension_calls": new_calls,
        "cached_dimension_calls": cached_calls,
        "skipped_complete_segments": len(skipped_ids),
        "completed_outputs": completed_outputs,
        "failed": len(failures),
        "failures": failures,
        "segment_approval": segment_approval,
        "rights_approval": rights_approval,
        "segments_sha256": sha256_file(project_path(segments_path)),
        "taxonomy_sha256": sha256_file(project_path(taxonomy_path)),
        "parallel": parallel,
        "resume": resume,
        "pilot": pilot,
        "exploratory": True,
        "paper_compatible": False,
    }
    manifest_path = output_root.parent / f"{run_id}.manifest.json"
    write_json(manifest_path, manifest)
    if failures:
        raise RuntimeError(
            f"Codex extraction had {len(failures)} failures; see {manifest_path}. "
            "Per-dimension resume data was preserved."
        )
    return manifest
