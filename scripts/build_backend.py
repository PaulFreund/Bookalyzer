"""Build a host-native sidecar containing Python and an explicit public asset allowlist."""
from pathlib import Path
import json
import platform
import shutil
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bookanalyzer.provenance import STORYSCOPE_COMMIT, assert_storyscope_immutable, sha256_file, write_json
from bookanalyzer.config import load_yaml


def main():
    if "--expected-arch" in sys.argv:
        expected = sys.argv[sys.argv.index("--expected-arch") + 1]
        actual = {"amd64": "x64", "x86_64": "x64", "aarch64": "arm64"}.get(platform.machine().lower(), platform.machine().lower())
        if actual != expected:
            raise RuntimeError(f"Python architecture {actual} does not match Electron/Node {expected}. Use a matching Python 3.11 environment.")
    assert_storyscope_immutable()
    staging = ROOT / "build/backend-assets"
    staging.mkdir(parents=True, exist_ok=True)
    vendor = ROOT / "vendor/storyscope"
    vendor_files = {}
    # Only the unmodified source and license, never upstream experiments or local books.
    for source in [*(vendor / "storyscope").rglob("*.py"), vendor / "LICENSE"]:
        relative = source.relative_to(vendor)
        destination = staging / "vendor/storyscope" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        vendor_files[relative.as_posix()] = sha256_file(source)
    for name in ("feature_sets.yaml",):
        target = staging / "config" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "config" / name, target)
    reference = ROOT / "data/reference/storyscope"
    reference.mkdir(parents=True, exist_ok=True)
    lock = load_yaml("config/reference_files.yaml")
    for name in ("taxonomy.json", "storyscope_features.parquet"):
        record = lock["files"][name]
        source = reference / name
        if not source.is_file():
            urllib.request.urlretrieve("https://huggingface.co/datasets/jjrussell10/storyscope/resolve/main/" + name, source)
        if sha256_file(source) != record["sha256"]:
            raise RuntimeError("Public reference hash mismatch: " + name)
        target = staging / "data/reference/storyscope" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    write_json(staging / "bundle-manifest.json", {
        "storyscope_commit": STORYSCOPE_COMMIT, "vendor_files": vendor_files,
        "platform": sys.platform, "architecture": platform.machine(),
        "public_assets_only": True,
    })
    if "--assets-only" in sys.argv:
        return
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
               "--onedir", "--console", "--name", "bookalyzer-service",
               "--distpath", str(ROOT / "build/runtime"), "--workpath", str(ROOT / "build/freezer"),
               "--specpath", str(ROOT / "build"), "--paths", str(ROOT), "--paths", str(vendor),
               "--add-data", str(staging) + ":.",
               "--hidden-import", "storyscope.5_feature_application.apply_features",
               "--collect-submodules", "sklearn",
               "--exclude-module", "tkinter", "--exclude-module", "IPython",
               "--exclude-module", "pytest", "--exclude-module", "reportlab",
               str(ROOT / "desktop/backend-entry.py")]
    subprocess.run(command, cwd=ROOT, check=True)
    print(json.dumps({"runtime": str(ROOT / "build/runtime/bookalyzer-service"), "platform": sys.platform}))


if __name__ == "__main__":
    main()
