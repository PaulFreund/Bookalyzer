"""Command-line entry point for the staged Bookalyzer workflow."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from .codex_adapter import (
    CODEX_PROVIDER,
    DEFAULT_REASONING_EFFORT,
    configured_codex_model,
    extract_features_with_codex,
)
from .config import PROJECT_ROOT, load_analysis_config, project_path
from .feature_matrix import compile_feature_jsons, load_taxonomy, resolve_feature_set
from .ingest import discover_books, ingest_books
from .paper_encoder import PaperEncoder
from .provenance import (
    REFERENCE_FILENAMES,
    STORYSCOPE_COMMIT,
    assert_storyscope_immutable,
    create_reference_manifest,
    download_reference_artifacts,
    sha256_file,
    storyscope_state,
)
from .rarity import build_reference
from .report import (
    analyze_books,
    analyze_books_internal,
    generate_internal_report,
    generate_report,
)
from .reproduction import reproduce_figure5
from .segment import approve_segments, segment_books
from .storyscope_adapter import (
    EXPECTED_MODEL,
    EXPECTED_PROVIDER,
    RIGHTS_CONFIRMATION,
    extract_features,
    record_rights_approval,
)


def _doctor(verify_hashes: bool) -> tuple[dict[str, Any], bool]:
    checks: dict[str, Any] = {}
    critical_ok = True
    checks["python"] = {
        "version": sys.version.split()[0],
        "executable": sys.executable,
        "required": ">=3.11,<3.12",
        "ok": sys.version_info[:2] == (3, 11),
    }
    critical_ok &= checks["python"]["ok"]
    state = storyscope_state()
    state["ok"] = state["commit"] == STORYSCOPE_COMMIT and state["clean"]
    checks["storyscope"] = state
    critical_ok &= state["ok"]

    reference_dir = project_path("data/reference/storyscope")
    reference_files = {
        name: {
            "exists": (reference_dir / name).is_file(),
            "size_bytes": (reference_dir / name).stat().st_size if (reference_dir / name).is_file() else None,
        }
        for name in REFERENCE_FILENAMES
    }
    checks["reference_files"] = reference_files
    critical_ok &= all(item["exists"] for item in reference_files.values())
    manifest_path = project_path("data/reference/manifest.json")
    checks["reference_manifest"] = {"exists": manifest_path.is_file(), "hashes_verified": False}
    critical_ok &= manifest_path.is_file()
    if verify_hashes and manifest_path.is_file():
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        expected = {entry["name"]: entry["sha256"] for entry in manifest.get("files", [])}
        mismatches = []
        for name in REFERENCE_FILENAMES:
            path = reference_dir / name
            if path.is_file() and expected.get(name) != sha256_file(path):
                mismatches.append(name)
        checks["reference_manifest"].update(
            {"hashes_verified": True, "mismatches": mismatches, "ok": not mismatches}
        )
        critical_ok &= not mismatches

    taxonomy_path = reference_dir / "taxonomy.json"
    if taxonomy_path.is_file():
        _, specs = load_taxonomy(taxonomy_path)
        feature_sets = {}
        for name in ("full_304", "public_nonstyle_265"):
            ids = resolve_feature_set(name, specs)
            feature_sets[name] = {
                "features": len(ids),
                "encoded_dimensions": PaperEncoder(specs, ids).encoded_dimension,
            }
        checks["taxonomy"] = {
            "features": len(specs),
            "dimensions": len(set(spec.dimension_key for spec in specs.values())),
            "feature_sets": feature_sets,
            "paper_narrative_257": "blocked: eight official feature IDs are unavailable",
            "ok": len(specs) == 304,
        }
        critical_ok &= len(specs) == 304

    try:
        books = discover_books("input/books")
    except FileNotFoundError:
        books = []
    checks["book_inputs"] = {
        "count": len(books),
        "files": [path.name for path in books],
        "note": "No book input is required for the public-artifact reproduction stage.",
    }
    checks["vertex"] = {
        "project_configured": bool(os.environ.get("GOOGLE_CLOUD_PROJECT")),
        "note": "Required only after segment and rights-holder approval.",
    }
    reproduction_metrics = project_path("reproduction/metrics.json")
    if reproduction_metrics.is_file():
        with reproduction_metrics.open("r", encoding="utf-8") as handle:
            checks["reproduction"] = json.load(handle)
    else:
        checks["reproduction"] = {"status": "not_run"}
    checks["critical_ok"] = bool(critical_ok)
    return checks, bool(critical_ok)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bookalyzer",
        description="StoryScope-compatible per-segment narrative rarity analysis",
    )
    parser.add_argument("--debug", action="store_true", help="Show tracebacks for failures")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Check runtime and immutable artifacts")
    doctor.add_argument("--verify-hashes", action="store_true")

    download = subparsers.add_parser("download-reference", help="Download hash-locked StoryScope artifacts")
    download.add_argument("--force", action="store_true")
    subparsers.add_parser("manifest-reference", help="Hash downloaded StoryScope artifacts")

    ingest = subparsers.add_parser("ingest", help="Import EPUB, DOCX, TXT, and text PDFs")
    ingest.add_argument("--input", default="input/books")
    ingest.add_argument("--output", default="data/processed")
    ingest.add_argument("--language", default="und")

    segment = subparsers.add_parser("segment", help="Create deterministic segments and preview")
    segment.add_argument("--sections", default="data/processed/book_sections.parquet")
    segment.add_argument("--output", default="data/processed/book_segments.parquet")
    segment.add_argument("--config", default="config/analysis.yaml")
    segment.add_argument("--preview", action="store_true", help="Retained for documented CLI compatibility")

    approve = subparsers.add_parser("approve-segments", help="Record manual preview approval")
    approve.add_argument("--approver", required=True)
    approve.add_argument("--note", default="")

    rights = subparsers.add_parser(
        "approve-external-processing",
        help="Record explicit rights-holder approval for external processing",
    )
    rights.add_argument("--rights-holder", required=True)
    rights.add_argument("--approver", required=True)
    rights.add_argument("--confirm", required=True, help=f"Exact required text: {RIGHTS_CONFIRMATION}")
    rights.add_argument("--provider", default=EXPECTED_PROVIDER)
    rights.add_argument("--model")
    rights.add_argument("--authorization-note", default="")

    reference = subparsers.add_parser("build-reference", help="Fit encoder/scaler on train+validation")
    reference.add_argument("--feature-set", default="public_nonstyle_265")

    reproduction = subparsers.add_parser("reproduce-figure5", help="Run the public quality gate")
    reproduction.add_argument("--feature-set", default="public_nonstyle_265")
    reproduction.add_argument("--backend", choices=["auto", "faiss", "numpy"], default="auto")
    reproduction.add_argument("--query-batch-size", type=int, default=256)
    reproduction.add_argument("--reference-block-size", type=int, default=4096)

    extract = subparsers.add_parser("extract", help="Run audited StoryScope Stage 5 extraction")
    extract.add_argument("--pilot", type=int)
    extract.add_argument("--parallel", type=int, default=4)
    extract.add_argument("--dim-workers", type=int, default=5)
    extract.add_argument("--no-resume", action="store_true")

    codex_extract = subparsers.add_parser(
        "extract-codex",
        help="Run exploratory Stage 5 extraction through the authenticated Codex CLI",
    )
    codex_extract.add_argument("--pilot", type=int)
    codex_extract.add_argument("--parallel", type=int, default=3)
    codex_extract.add_argument("--model")
    codex_extract.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    codex_extract.add_argument("--timeout-seconds", type=int, default=900)
    codex_extract.add_argument("--no-resume", action="store_true")

    compile_parser = subparsers.add_parser("compile-features", help="Validate and combine feature JSONs")
    compile_parser.add_argument("--raw", default="data/features/raw")
    compile_parser.add_argument("--output", default="data/features/book_features.parquet")

    rarity = subparsers.add_parser("rarity", help="Score book segments against the fitted reference")
    rarity.add_argument("--feature-set", default="public_nonstyle_265")
    rarity.add_argument("--backend", choices=["auto", "faiss", "numpy"], default="auto")

    subparsers.add_parser("report", help="Regenerate figures and methods report from caches")
    internal_rarity = subparsers.add_parser(
        "internal-rarity",
        help="Score segments against the other supplied book segments",
    )
    internal_rarity.add_argument("--feature-set", default="public_nonstyle_265")
    internal_rarity.add_argument("--backend", choices=["auto", "faiss", "numpy"], default="auto")
    subparsers.add_parser(
        "internal-report",
        help="Generate exploratory book-internal diagrams without the external reference",
    )
    return parser


def dispatch(args: argparse.Namespace) -> int:
    if args.command == "doctor":
        checks, ok = _doctor(args.verify_hashes)
        print(json.dumps(checks, indent=2, ensure_ascii=False, default=str))
        return 0 if ok else 2
    if args.command == "manifest-reference":
        print(create_reference_manifest())
        return 0
    if args.command == "download-reference":
        print(download_reference_artifacts(force=args.force))
        return 0
    if args.command == "ingest":
        config = load_analysis_config()
        settings = config["ingest"]
        inventory, sections = ingest_books(
            args.input,
            args.output,
            language=args.language,
            exclude_frontmatter=bool(settings["exclude_frontmatter"]),
            exclude_backmatter=bool(settings["exclude_backmatter"]),
            pdf_min_words_per_page=int(settings["pdf_min_words_per_page"]),
            repeated_margin_fraction=float(settings["repeated_margin_fraction"]),
        )
        print(f"Imported {len(inventory)} books into {len(sections)} sections.")
        return 0
    if args.command == "segment":
        config = load_analysis_config(args.config)
        settings = config["segmentation"]
        segments = segment_books(
            args.sections,
            args.output,
            target_words=int(settings["target_words"]),
            min_words=int(settings["min_words"]),
            max_words=int(settings["max_words"]),
        )
        print(
            f"Created {len(segments)} non-overlapping segments. Review "
            f"{project_path(args.output).parent / 'segment_preview.md'} before approval."
        )
        return 0
    if args.command == "approve-segments":
        print(approve_segments(approver=args.approver, note=args.note))
        return 0
    if args.command == "approve-external-processing":
        model = args.model
        if model is None:
            model = configured_codex_model() if args.provider == CODEX_PROVIDER else EXPECTED_MODEL
        print(
            record_rights_approval(
                rights_holder=args.rights_holder,
                approver=args.approver,
                confirmation=args.confirm,
                provider=args.provider,
                model=model,
                authorization_note=args.authorization_note,
            )
        )
        return 0
    if args.command == "build-reference":
        artifacts = build_reference(feature_set=args.feature_set)
        print(
            f"Built {artifacts.feature_set}: {len(artifacts.matrix)} rows × "
            f"{artifacts.matrix.shape[1]} encoded columns."
        )
        return 0
    if args.command == "reproduce-figure5":
        metrics = reproduce_figure5(
            feature_set=args.feature_set,
            backend=args.backend,
            query_batch_size=args.query_batch_size,
            reference_block_size=args.reference_block_size,
        )
        print(json.dumps(metrics, indent=2, ensure_ascii=False, default=str))
        return 0
    if args.command == "extract":
        manifest = extract_features(
            pilot=args.pilot,
            parallel=args.parallel,
            dim_workers=args.dim_workers,
            resume=not args.no_resume,
        )
        print(json.dumps(manifest, indent=2, ensure_ascii=False, default=str))
        return 0
    if args.command == "extract-codex":
        manifest = extract_features_with_codex(
            pilot=args.pilot,
            parallel=args.parallel,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            timeout_seconds=args.timeout_seconds,
            resume=not args.no_resume,
        )
        print(json.dumps(manifest, indent=2, ensure_ascii=False, default=str))
        return 0
    if args.command == "compile-features":
        frame = compile_feature_jsons(
            args.raw,
            "vendor/storyscope/data/taxonomy.json",
            "data/processed/book_segments.parquet",
            args.output,
        )
        print(f"Compiled {len(frame)} validated segment feature rows to {project_path(args.output)}")
        return 0
    if args.command == "rarity":
        frame = analyze_books(feature_set=args.feature_set, backend=args.backend)
        print(f"Scored {len(frame)} book segments.")
        return 0
    if args.command == "report":
        print(json.dumps(generate_report(), indent=2, ensure_ascii=False))
        return 0
    if args.command == "internal-rarity":
        frame = analyze_books_internal(feature_set=args.feature_set, backend=args.backend)
        print(f"Scored {len(frame)} book segments against the other supplied segments.")
        return 0
    if args.command == "internal-report":
        print(json.dumps(generate_internal_report(), indent=2, ensure_ascii=False))
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return dispatch(args)
    except Exception as error:
        if args.debug:
            raise
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
