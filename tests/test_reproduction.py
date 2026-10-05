from __future__ import annotations

import json

from bookanalyzer.reproduction import record_reproduction_blocker


def test_blocked_reproduction_never_claims_exact(tmp_path) -> None:
    output = tmp_path / "reproduction"
    metrics = record_reproduction_blocker(
        feature_set="public_nonstyle_265",
        error=ValueError("fixture incompatibility"),
        output_dir=output,
        cache_dir=tmp_path / "cache",
    )
    assert metrics["exact_reproduction_claimed"] is False
    assert metrics["book_quality_gate_passed"] is False
    with (output / "metrics.json").open(encoding="utf-8") as handle:
        persisted = json.load(handle)
    assert persisted["status"].startswith("blocked")
