"""Validate the deliverable, including metadata lost by many Windows ZIP tools."""
import hashlib
import json
from pathlib import Path
import stat
import zipfile

from scripts.package_mac_source import ROOT, create_bundle


def test_source_kit_is_complete_executable_and_contains_no_private_data(tmp_path):
    path, manifest = create_bundle(ROOT, tmp_path / "Mac-Baupaket.zip")
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        members = {name.split("/", 1)[1]: name for name in archive.namelist()}
        assert {"MAC-START.txt", "MAC_INSTALL.md", "Mac-DMG-erstellen.command", "package-lock.json",
                "desktop/Installation-Mac.txt", "bookanalyzer/quality.py", "src/QualityOverview.tsx",
                "config/reference_files.yaml", "requirements.lock"} <= members.keys()
        forbidden = {"input", "data", ".bookanalyzer", ".git", ".venv", "node_modules", "outputs", "vendor", "build", "release"}
        assert all(not (set(Path(name).parts) & forbidden) for name in members)
        assert "config/rights_approval.yaml" not in members
        command = archive.getinfo(members["Mac-DMG-erstellen.command"])
        assert command.create_system == 3
        assert stat.S_IMODE(command.external_attr >> 16) == 0o755
        script = archive.read(command)
        assert script.startswith(b"#!/bin/bash\n") and b"\r" not in script
        assert b"package:mac:release" not in script
        assert b"npm run test:packaged" in script
        assert b"npm run test:runtime" in script
        assert json.loads(archive.read(members["source-manifest.json"])) == manifest
        for name, checksum in manifest["files"].items():
            assert hashlib.sha256(archive.read(members[name])).hexdigest() == checksum
    assert path.with_suffix(".zip.sha256").read_text().startswith(hashlib.sha256(path.read_bytes()).hexdigest())
