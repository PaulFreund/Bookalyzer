"""Hashes, immutable-source checks, and machine-readable run manifests."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import uuid
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import PROJECT_ROOT, project_path
from .config import load_yaml


STORYSCOPE_COMMIT = "642e746804e1ee4138ffdcf13b7412eb3dc2a70b"
REFERENCE_URL = "https://huggingface.co/datasets/jjrussell10/storyscope/resolve/main"
REFERENCE_FILENAMES = (
    "stories_train.parquet",
    "stories_val.parquet",
    "stories_test.parquet",
    "storyscope_features.parquet",
    "taxonomy.json",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: str | Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: str | Path, payload: Any) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    return target


def _git(args: list[str], cwd: Path) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def git_commit(path: str | Path = PROJECT_ROOT) -> str | None:
    return _git(["rev-parse", "HEAD"], Path(path))


def storyscope_state(vendor_dir: str | Path = "vendor/storyscope") -> dict[str, Any]:
    path = project_path(vendor_dir)
    if getattr(sys, "frozen", False):
        # Frozen distributions have no Git dependency. The build records hashes
        # only after checking the exact, clean upstream checkout.
        manifest = json.loads((PROJECT_ROOT / "bundle-manifest.json").read_text(encoding="utf-8"))
        changed = [name for name, digest in manifest["vendor_files"].items()
                   if not (path / name).is_file() or sha256_file(path / name) != digest]
        return {"path": str(path), "commit": manifest["storyscope_commit"],
                "expected_commit": STORYSCOPE_COMMIT, "clean": not changed,
                "status": ", ".join(changed), "verification": "bundled file hashes"}
    commit = git_commit(path)
    status = _git(["status", "--short"], path)
    return {
        "path": str(path),
        "commit": commit,
        "expected_commit": STORYSCOPE_COMMIT,
        "clean": status == "",
        "status": status,
    }


def assert_storyscope_immutable(vendor_dir: str | Path = "vendor/storyscope") -> None:
    state = storyscope_state(vendor_dir)
    if state["commit"] != STORYSCOPE_COMMIT:
        raise RuntimeError(
            "StoryScope commit mismatch: "
            f"expected {STORYSCOPE_COMMIT}, found {state['commit']!r}"
        )
    if not state["clean"]:
        raise RuntimeError(
            "The vendored StoryScope checkout has local changes; restore it before running. "
            f"Status: {state['status']}"
        )


def installed_versions(names: Iterable[str] | None = None) -> dict[str, str]:
    if names is None:
        names = (
            "beautifulsoup4",
            "EbookLib",
            "google-genai",
            "joblib",
            "matplotlib",
            "numpy",
            "pandas",
            "pyarrow",
            "pypdf",
            "python-docx",
            "PyYAML",
            "scikit-learn",
            "scipy",
        )
    versions: dict[str, str] = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def pip_freeze() -> list[str]:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--all"],
        text=True,
        capture_output=True,
        check=False,
    )
    return sorted(line for line in result.stdout.splitlines() if line.strip())


def new_run_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"


def file_record(path: str | Path) -> dict[str, Any]:
    item = Path(path)
    stat = item.stat()
    return {
        "path": str(item.resolve()),
        "size_bytes": stat.st_size,
        "sha256": sha256_file(item),
        "modified_at_utc": datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat(timespec="seconds"),
    }


def create_reference_manifest(
    reference_dir: str | Path = "data/reference/storyscope",
    output: str | Path = "data/reference/manifest.json",
) -> Path:
    directory = project_path(reference_dir)
    missing = [name for name in REFERENCE_FILENAMES if not (directory / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing reference artifacts: {', '.join(missing)}")
    files = []
    for name in REFERENCE_FILENAMES:
        record = file_record(directory / name)
        record.update(
            {
                "name": name,
                "source_url": f"{REFERENCE_URL}/{name}",
                "downloaded_at_utc": record["modified_at_utc"],
            }
        )
        files.append(record)
    payload = {
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "dataset": "jjrussell10/storyscope",
        "files": files,
    }
    return write_json(project_path(output), payload)


def download_reference_artifacts(
    *,
    reference_dir: str | Path = "data/reference/storyscope",
    lock_path: str | Path = "config/reference_files.yaml",
    force: bool = False,
) -> Path:
    """Download immutable-by-hash Hugging Face artifacts and create their manifest."""
    directory = project_path(reference_dir)
    directory.mkdir(parents=True, exist_ok=True)
    lock = load_yaml(lock_path)
    locked_files = lock.get("files", {})
    if set(locked_files) != set(REFERENCE_FILENAMES):
        raise ValueError("Reference lock must describe exactly the five required artifacts")
    for name in REFERENCE_FILENAMES:
        target = directory / name
        expected_hash = str(locked_files[name]["sha256"])
        expected_size = int(locked_files[name]["size_bytes"])
        if target.is_file() and not force:
            if target.stat().st_size == expected_size and sha256_file(target) == expected_hash:
                continue
            raise RuntimeError(
                f"Existing reference artifact does not match its lock: {target}. "
                "Move it aside or explicitly use --force."
            )
        temporary = target.with_suffix(target.suffix + ".part")
        url = f"{REFERENCE_URL}/{name}?download=true"
        try:
            with urllib.request.urlopen(url) as response, temporary.open("wb") as handle:
                while block := response.read(1024 * 1024):
                    handle.write(block)
            if temporary.stat().st_size != expected_size:
                raise RuntimeError(
                    f"Size mismatch for {name}: expected {expected_size}, got {temporary.stat().st_size}"
                )
            actual_hash = sha256_file(temporary)
            if actual_hash != expected_hash:
                raise RuntimeError(
                    f"SHA-256 mismatch for {name}: expected {expected_hash}, got {actual_hash}"
                )
            temporary.replace(target)
        except Exception:
            if temporary.is_file():
                temporary.unlink()
            raise
    return create_reference_manifest(reference_dir=directory)


def build_run_manifest(
    *,
    run_id: str,
    command: str,
    parameters: dict[str, Any],
    inputs: Iterable[str | Path] = (),
    outputs: Iterable[str | Path] = (),
) -> dict[str, Any]:
    input_records = [file_record(path) for path in inputs if Path(path).is_file()]
    output_records = [file_record(path) for path in outputs if Path(path).is_file()]
    return {
        "schema_version": 1,
        "run_id": run_id,
        "created_at_utc": utc_now(),
        "command": command,
        "parameters": parameters,
        "bookanalyzer_commit": git_commit(),
        "storyscope": storyscope_state(),
        "runtime": {
            "python": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
            "packages": installed_versions(),
            "pip_freeze": pip_freeze(),
        },
        "inputs": input_records,
        "outputs": output_records,
    }
