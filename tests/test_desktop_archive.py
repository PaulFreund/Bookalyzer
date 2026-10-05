"""Snapshots preserve the full library and never damage live data on failed import."""
import base64
import hashlib
import json
import stat
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from bookanalyzer import desktop_archive
from bookanalyzer.desktop import DEFAULTS, DesktopService


@pytest.fixture
def service(tmp_path):
    app = DesktopService(tmp_path / "library", seed=False)
    app.state["seeded"] = True
    app._persist()
    yield app
    app.library_discard(app.archive_import["preview"]["id"]) if app.archive_import else None
    app.executor.shutdown(wait=True)


def document(service, title="Buch.txt"):
    doc = service.prepare(title, base64.b64encode(
        ("Kapitel 1\n" + "Der Wind kommt vom Meer. Sie wartet auf den Regen. " * 60).encode()
    ).decode(), {**DEFAULTS, "minWords": 100, "targetWords": 200, "maxWords": 300, "detectChapters": True})
    service._complete(doc, pd.read_parquet(service._directory(doc["id"]) / "segments.parquet"))
    service._persist()
    return doc


def library_bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def rewrite_archive(path, changes=None, *, version=1, additions=None, keep_hash=False):
    with zipfile.ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(files["manifest.json"])
    manifest["version"] = version
    for name, content in (changes or {}).items():
        files["library/" + name] = content
        if not keep_hash:
            manifest["files"][name] = {"size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    files["manifest.json"] = json.dumps(manifest).encode()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
        for name, content in (additions or {}).items():
            archive.writestr(name, content)


def test_full_round_trip_including_hidden_files_baselines_and_decisions(service, tmp_path):
    visible = document(service)
    hidden = document(service, "Ausgeblendet.txt")
    baseline = service.baseline_create(hidden["id"], "Feste Referenz")
    service.remove(hidden["id"])
    service.settings({**DEFAULTS, "language": "en", "longSentenceWords": 42})
    finding = service.quality([visible["id"]])["rows"][0]["quality"]
    evidence = finding["evidence"][0]
    service.quality_decision(visible["id"], finding["textSha256"], evidence["metric"],
                             evidence["start"], evidence["end"], True)
    response = service._directory(visible["id"]) / "responses" / "segment" / "cached.json"
    response.parent.mkdir(parents=True)
    response.write_text('{"saved":true}', encoding="utf-8")
    expected = library_bytes(service.root)
    archive = tmp_path / "Vollständiger Datenbestand.zip"
    service.call("library_export", {"path": str(archive)})
    with zipfile.ZipFile(archive) as zip_file:
        manifest = json.loads(zip_file.read("manifest.json"))
        assert set(manifest["files"]) == set(expected)
        for name, content in expected.items():
            assert zip_file.read("library/" + name) == content
            assert manifest["files"][name]["sha256"] == hashlib.sha256(content).hexdigest()
    document(service, "Später.txt")
    old = library_bytes(service.root)
    preview = service.library_inspect(str(archive))
    assert preview["documentCount"] == 1
    assert preview["baselineCount"] == 1
    assert library_bytes(service.root) == old  # Preview never writes to the live library.
    service.comparisons["stale"] = True
    result = service.library_import(preview["id"], replaceConfirmed=True)
    assert service.comparisons == {}
    assert library_bytes(service.root) == expected
    assert response.read_text(encoding="utf-8") == '{"saved":true}'
    assert service._document(visible["id"])["qualityDecisions"]
    assert service.state["settings"]["longSentenceWords"] == 42
    assert service.baseline_compare([visible["id"]], baseline["id"])["rows"]
    assert len(service.chapters(visible["id"])["chapters"]) == 1
    with zipfile.ZipFile(result["backupPath"]) as backup:
        assert json.loads(backup.read("library/library.json"))["documents"][-1]["title"] == "Später"
    reopened = DesktopService(service.root, seed=False)
    try:
        assert reopened._document(visible["id"])["qualityDecisions"]
        assert reopened.state["baselines"] == service.state["baselines"]
    finally:
        reopened.executor.shutdown(wait=True)


def test_empty_library_can_be_exported_and_restored(service, tmp_path):
    archive = tmp_path / "empty.zip"
    service.library_export(archive)
    preview = service.library_inspect(archive)
    assert preview["documentCount"] == preview["baselineCount"] == 0
    service.library_import(preview["id"], True)
    assert service.state["documents"] == []


def test_confirmation_and_valid_preview_required(service, tmp_path):
    archive = tmp_path / "data.zip"
    service.library_export(archive)
    preview = service.library_inspect(archive)
    before = library_bytes(service.root)
    with pytest.raises(ValueError, match="bestätigen"):
        service.library_import(preview["id"])
    with pytest.raises(ValueError, match="erneut"):
        service.library_import("unknown", True)
    assert library_bytes(service.root) == before
    service.library_discard(preview["id"])
    with pytest.raises(ValueError, match="erneut"):
        service.library_import(preview["id"], True)


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/escape", "library/../escape",
                                  "library/back\\slash", "library/CON.txt", "library/file:stream",
                                  "library/trailing.", "library/trailing "])
def test_unsafe_zip_paths_rejected_without_writes(service, tmp_path, name):
    archive = tmp_path / "unsafe.zip"
    service.library_export(archive)
    before = library_bytes(service.root)
    rewrite_archive(archive, additions={name: b"bad"})
    with pytest.raises(ValueError):
        service.library_inspect(archive)
    with pytest.raises(ValueError, match="Pfad"):
        desktop_archive.portable_path(name)
    assert library_bytes(service.root) == before
    assert not (tmp_path / "escape").exists()
    assert not list(tmp_path.glob(".bookalyzer-import-*"))


@pytest.mark.parametrize("kind", ["checksum", "version", "invalid-state", "missing-data", "baseline-hash", "invalid-parquet"])
def test_invalid_snapshots_leave_current_data_untouched(service, tmp_path, kind):
    doc = document(service)
    baseline = service.baseline_create(doc["id"], "Baseline")
    archive = tmp_path / "broken.zip"
    service.library_export(archive)
    before = library_bytes(service.root)
    if kind == "checksum":
        rewrite_archive(archive, {"library.json": b"x" * len(before["library.json"])}, keep_hash=True)
    elif kind == "version":
        rewrite_archive(archive, version=999)
    elif kind == "invalid-state":
        rewrite_archive(archive, {"library.json": b'{"documents": []}'})
    elif kind == "missing-data":
        with zipfile.ZipFile(archive) as zip_file:
            files = {name: zip_file.read(name) for name in zip_file.namelist() if not name.endswith("segments.parquet")}
        with zipfile.ZipFile(archive, "w") as zip_file:
            for name, data in files.items():
                zip_file.writestr(name, data)
    elif kind == "baseline-hash":
        rewrite_archive(archive, {f"baselines/{baseline['id']}/snapshot.json": b"{}"})
    elif kind == "invalid-parquet":
        rewrite_archive(archive, {f"{doc['id']}/segments.parquet": b"broken parquet"})
    with pytest.raises(ValueError):
        service.library_inspect(archive)
    assert library_bytes(service.root) == before
    assert service.archive_import is None


def test_symlinks_and_case_collisions_rejected(service, tmp_path):
    archive = tmp_path / "links.zip"
    service.library_export(archive)
    with zipfile.ZipFile(archive, "a") as zip_file:
        info = zipfile.ZipInfo("library/link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zip_file.writestr(info, "../outside")
    with pytest.raises(ValueError, match="Ungültige"):
        service.library_inspect(archive)
    service.library_export(archive)
    rewrite_archive(archive, additions={"library/LIBRARY.JSON": b"{}"})
    with pytest.raises(ValueError, match="doppelte"):
        service.library_inspect(archive)


def test_size_limits_and_atomic_export(service, tmp_path, monkeypatch):
    archive = tmp_path / "data.zip"
    service.library_export(archive)
    previous_archive = archive.read_bytes()
    monkeypatch.setattr(desktop_archive, "MAX_ARCHIVE_BYTES", 1)
    with pytest.raises(ValueError, match="groß"):
        service.library_export(archive)
    assert archive.read_bytes() == previous_archive
    with pytest.raises(ValueError, match="groß"):
        service.library_inspect(archive)
    monkeypatch.setattr(desktop_archive, "MAX_ARCHIVE_BYTES", len(previous_archive))
    monkeypatch.setattr(desktop_archive, "MAX_DATA_BYTES", 1)
    with pytest.raises(ValueError, match="groß"):
        service.library_inspect(archive)


@pytest.mark.parametrize("supplement", [False, True])
def test_running_analysis_blocks_transfer_including_commit(service, tmp_path, supplement):
    doc = document(service)
    archive = tmp_path / "data.zip"
    service.library_export(archive)
    preview = service.library_inspect(archive)
    if supplement:
        doc["storyscope"] = {"status": "analyzing"}
    else:
        doc["status"] = "queued"
    for action in (lambda: service.library_export(archive), lambda: service.library_inspect(archive),
                   lambda: service.library_import(preview["id"], True)):
        with pytest.raises(ValueError, match="laufende"):
            action()


def test_export_cannot_include_itself(service):
    with pytest.raises(ValueError, match="außerhalb"):
        service.library_export(service.root / "backup.zip")


def test_failed_directory_swap_restores_previous_library(service, tmp_path, monkeypatch):
    archive = tmp_path / "empty.zip"
    service.library_export(archive)
    document(service)
    before = library_bytes(service.root)
    preview = service.library_inspect(archive)
    staged_root = service.archive_import["root"]
    original_replace = Path.replace
    def fail_swap(path, target):
        if path == staged_root:
            raise OSError("Simulated directory swap failure")
        return original_replace(path, target)
    monkeypatch.setattr(Path, "replace", fail_swap)
    with pytest.raises(OSError, match="Simulated"):
        service.library_import(preview["id"], True)
    assert library_bytes(service.root) == before
    assert len(service.state["documents"]) == 1
    assert list((tmp_path / "library-backups").glob("*.zip"))


def test_failed_backup_prevents_any_directory_swap(service, tmp_path, monkeypatch):
    archive = tmp_path / "data.zip"
    service.library_export(archive)
    preview = service.library_inspect(archive)
    before = library_bytes(service.root)
    def fail_backup(*_):
        raise OSError("Simulated backup failure")
    monkeypatch.setattr(desktop_archive, "export_library", fail_backup)
    with pytest.raises(OSError, match="backup failure"):
        service.library_import(preview["id"], True)
    assert library_bytes(service.root) == before


def test_failed_rollback_keeps_previous_directory_and_backup(service, tmp_path, monkeypatch):
    archive = tmp_path / "empty.zip"
    service.library_export(archive)
    document(service)
    before = library_bytes(service.root)
    preview = service.library_inspect(archive)
    staged_root = service.archive_import["root"]
    original_replace = Path.replace
    def fail_both_swaps(path, target):
        if path == staged_root or path.parent.name.startswith(".bookalyzer-previous-"):
            raise OSError("Simulated directory swap failure")
        return original_replace(path, target)
    monkeypatch.setattr(Path, "replace", fail_both_swaps)
    with pytest.raises(RuntimeError, match="Bisherige Daten"):
        service.library_import(preview["id"], True)
    previous = next(tmp_path.glob(".bookalyzer-previous-*/library"))
    assert library_bytes(previous) == before
    assert list((tmp_path / "library-backups").glob("*.zip"))


def test_interrupted_jobs_are_restored_without_automatic_restart(service, tmp_path):
    doc = document(service)
    archive = tmp_path / "interrupted.zip"
    service.library_export(archive)
    state = json.loads((service.root / "library.json").read_text(encoding="utf-8"))
    state["documents"][0]["storyscope"] = {"status": "queued"}
    rewrite_archive(archive, {"library.json": json.dumps(state).encode()})
    preview = service.library_inspect(archive)
    service.library_import(preview["id"], True)
    restored = service._document(doc["id"])
    assert restored["status"] == "ready"
    assert restored["storyscope"]["status"] == "error"
    assert "unterbrochen" in restored["storyscope"]["error"]


def test_restored_library_does_not_seed_project_data_on_restart(service, tmp_path, monkeypatch):
    service.state["seeded"] = False
    archive = tmp_path / "unseeded.zip"
    service.library_export(archive)
    preview = service.library_inspect(archive)
    service.library_import(preview["id"], True)
    def unexpected_seed(_):
        pytest.fail("A restored library must not load unrelated project data")
    monkeypatch.setattr(DesktopService, "_seed_existing", unexpected_seed)
    reopened = DesktopService(service.root)
    reopened.executor.shutdown(wait=True)
    assert reopened.state["documents"] == []
