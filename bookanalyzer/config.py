"""Configuration loading and project path resolution."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
from typing import Any

import yaml


PROJECT_ROOT = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]


def project_path(value: str | Path) -> Path:
    """Resolve a configured path relative to the project root."""
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_yaml(path: str | Path) -> dict[str, Any]:
    resolved = project_path(path)
    with resolved.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Configuration root must be a mapping: {resolved}")
    return data


def load_analysis_config(path: str | Path = "config/analysis.yaml") -> dict[str, Any]:
    return deepcopy(load_yaml(path))
