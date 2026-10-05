"""Portable source kit with a strict public-file allowlist and Unix script mode."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import stat
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "MAC-START.txt", "MAC_INSTALL.md", "Mac-DMG-erstellen.command",
    "README.md", "DESKTOP.md", "QUALITY_METHODS.md", "IMPLEMENTATION.md", "CHANGELOG.md",
    "package.json", "package-lock.json", "pyproject.toml", "requirements.lock",
    "requirements-build.txt", "tsconfig.json", "vite.config.mjs", "index.html",
    ".gitignore", ".gitattributes", ".gitmodules", ".github/workflows/macos.yml",
    "config/analysis.yaml", "config/feature_sets.yaml", "config/models.yaml",
    "config/reference_files.yaml",
    "docs/demo.md", "docs/demo-analysis.json", "docs/screenshots/overview.png",
    "docs/screenshots/chapters.png", "docs/screenshots/details.png",
)
TREES = {
    "bookanalyzer": {".py"}, "src": {".ts", ".tsx", ".css", ".svg"},
    "desktop": {".cjs", ".py", ".plist", ".txt", ".png", ".ico", ".icns", ".svg"},
    "scripts": {".py", ".cjs"}, "tests": {".py"},
}


def bundle_files(root: Path):
    files = [root / name for name in FILES]
    for directory, suffixes in TREES.items():
        files.extend(p for p in (root / directory).rglob("*")
                     if p.is_file() and p.suffix in suffixes and "__pycache__" not in p.parts)
    for path in files:
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Missing or unsafe source file: {path}")
    return sorted(set(files))


def create_bundle(root: Path, destination: Path | None = None):
    version = json.loads((root / "package.json").read_text(encoding="utf-8"))["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?", version):
        raise ValueError("Invalid release version")
    folder = f"Bookalyzer-{version}-Mac-Baupaket"
    destination = destination or root / "release" / f"{folder}.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"version": version, "public_source_only": True, "files": {}}
    def entry(name, executable=False):
        item = zipfile.ZipInfo(f"{folder}/{name}")
        item.create_system = 3
        item.external_attr = (stat.S_IFREG | (0o755 if executable else 0o644)) << 16
        item.compress_type = zipfile.ZIP_DEFLATED
        return item
    with zipfile.ZipFile(destination, "w") as archive:
        for path in bundle_files(root):
            name = path.relative_to(root).as_posix()
            content = path.read_bytes()
            if name.endswith(".command"):
                content = content.replace(b"\r\n", b"\n")
            archive.writestr(entry(name, name.endswith(".command")), content)
            manifest["files"][name] = hashlib.sha256(content).hexdigest()
        archive.writestr(entry("source-manifest.json"), json.dumps(manifest, indent=2, sort_keys=True)+"\n")
    checksum = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(".zip.sha256").write_text(f"{checksum}  {destination.name}\n", encoding="utf-8")
    return destination, manifest


if __name__ == "__main__":
    path, manifest = create_bundle(ROOT, Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    print(json.dumps({"path": str(path), "files": len(manifest["files"]), "bytes": path.stat().st_size}))
