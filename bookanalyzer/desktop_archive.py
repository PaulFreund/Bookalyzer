"""Portable library snapshots, validated in isolation before restoring live data."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath

import pandas as pd

from .provenance import sha256_file, utc_now

FORMAT = "bookalyzer-library"
VERSION = 1
MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024
MAX_DATA_BYTES = 4 * MAX_ARCHIVE_BYTES
MAX_FILES = 100_000
MAX_JSON_BYTES = 32 * 1024 * 1024
ID = re.compile(r"[a-f0-9]{32}")
HASH = re.compile(r"[a-f0-9]{64}")


def portable_path(name):
    """Reject traversal and names that alias or target devices on Windows."""
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError("Ungültiger Pfad in der Sicherung.")
    path = PurePosixPath(name)
    if not path.parts or path.is_absolute() or path.as_posix() != name:
        raise ValueError("Ungültiger Pfad in der Sicherung.")
    for part in path.parts:
        if (part in (".", "..") or part.endswith((".", " "))
                or re.search(r'[\x00-\x1f<>:"|?*]', part)
                or re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", part.split(".")[0])):
            raise ValueError("Ungültiger Pfad in der Sicherung.")
    return path


def require_idle(service):
    if any(doc["status"] in ("queued", "analyzing")
           or doc.get("storyscope", {}).get("status") in ("queued", "analyzing")
           for doc in service.state["documents"]):
        raise ValueError("Bitte laufende Analysen vor dem Sichern oder Laden abschließen.")


def export_library(service, path):
    destination = Path(path).expanduser().resolve()
    if destination.suffix.lower() != ".zip":
        raise ValueError("Bitte eine ZIP-Datei als Ziel wählen.")
    if destination.is_relative_to(service.root):
        raise ValueError("Die Sicherung bitte außerhalb der Bibliothek speichern.")
    with service.lock:
        require_idle(service)
        service._persist()
        files, names, total = [], set(), 0
        for source in sorted(service.root.rglob("*")):
            if source.is_symlink() or getattr(source.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise ValueError("Verknüpfungen in der Bibliothek können nicht gesichert werden.")
            if not source.is_file():
                continue
            relative = source.relative_to(service.root).as_posix()
            portable_path(relative)
            if relative.casefold() in names:
                raise ValueError("Dateinamen in der Bibliothek sind nicht plattformübergreifend eindeutig.")
            names.add(relative.casefold())
            total += source.stat().st_size
            files.append((relative, source))
        if len(files) > MAX_FILES or total > MAX_DATA_BYTES:
            raise ValueError("Datenbestand zu groß (max. 100.000 Dateien und 4 GB entpackt).")
        manifest = {"format": FORMAT, "version": VERSION, "createdAt": utc_now(),
                    "files": {}}
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=destination.parent, prefix=".bookalyzer-export-") as temporary:
            archive_path = Path(temporary) / "library.zip"
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                for relative, source in files:
                    digest, size = hashlib.sha256(), 0
                    with source.open("rb") as reader, archive.open("library/" + relative, "w", force_zip64=True) as writer:
                        for block in iter(lambda: reader.read(1024 * 1024), b""):
                            writer.write(block)
                            digest.update(block)
                            size += len(block)
                    manifest["files"][relative] = {"size": size, "sha256": digest.hexdigest()}
                encoded = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
                if len(encoded) > MAX_JSON_BYTES:
                    raise ValueError("Sicherungsverzeichnis zu groß.")
                archive.writestr("manifest.json", encoded)
            if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
                raise ValueError("ZIP-Datei zu groß (max. 1 GB).")
            archive_path.replace(destination)
        return {"path": str(destination), "fileCount": len(files), "bytes": total}


def read_json(path):
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("Metadaten in der Sicherung sind zu groß.")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_document(document, directory):
    from .desktop import validate_settings
    from .desktop_text import text_basis
    if (not isinstance(document, dict) or not isinstance(document.get("id"), str)
            or not ID.fullmatch(document["id"])):
        raise ValueError("Ungültige Dokument-ID in der Sicherung.")
    for key in ("name", "title", "createdAt", "color"):
        if not isinstance(document.get(key), str):
            raise ValueError("Unvollständige Dokumentdaten in der Sicherung.")
    document["settings"] = validate_settings(document.get("settings"))
    if document.get("status") not in ("draft", "queued", "analyzing", "ready", "error"):
        raise ValueError("Ungültiger Analysestatus in der Sicherung.")
    for key in ("wordCount", "segmentCount"):
        if type(document.get(key)) is not int or document[key] < 1:
            raise ValueError("Ungültige Textgrößen in der Sicherung.")
    if not isinstance(document.get("segments"), list) or len(document["segments"]) != document["segmentCount"]:
        raise ValueError("Unvollständige Segmentdaten in der Sicherung.")
    segments = pd.read_parquet(directory / "segments.parquet")
    required = {"segment_index", "segment_id", "human_story", "word_count", "chapter_title"}
    if not required.issubset(segments.columns) or len(segments) != document["segmentCount"]:
        raise ValueError("Ungültige Analysesegmente in der Sicherung.")
    indices = []
    for segment in document["segments"]:
        if (not isinstance(segment, dict) or type(segment.get("index")) is not int
                or type(segment.get("words")) is not int
                or any(not isinstance(segment.get(key), str) for key in ("id", "title", "preview"))):
            raise ValueError("Ungültige Segmentdaten in der Sicherung.")
        indices.append(segment["index"])
    if (indices != segments.segment_index.astype(int).tolist()
            or [s["id"] for s in document["segments"]] != segments.segment_id.tolist()
            or int(segments.word_count.sum()) != document["wordCount"]):
        raise ValueError("Text und Segmentdaten in der Sicherung stimmen nicht überein.")
    if document.get("storyscope") is not None and not isinstance(document["storyscope"], dict):
        raise ValueError("Ungültige StoryScope-Daten in der Sicherung.")
    if document.get("narrative"):
        features = pd.read_parquet(directory / "features.parquet")
        if ("segment_id" not in features or len(features) != len(segments)
                or set(features.segment_id) != set(segments.segment_id)):
            raise ValueError("Unvollständige StoryScope-Merkmale in der Sicherung.")
    text_basis(directory)


def validate_library(root):
    from .desktop import validate_settings
    state = read_json(root / "library.json")
    if (not isinstance(state, dict) or not isinstance(state.get("documents"), list)
            or not isinstance(state.get("baselines", []), list) or type(state.get("seeded")) is not bool):
        raise ValueError("Ungültiges Bibliotheksverzeichnis in der Sicherung.")
    validate_settings(state.get("settings"))
    ids = set()
    for document in state["documents"]:
        identifier = document.get("id") if isinstance(document, dict) else None
        if not isinstance(identifier, str) or not ID.fullmatch(identifier) or identifier in ids:
            raise ValueError("Ungültige oder doppelte Dokument-ID in der Sicherung.")
        ids.add(identifier)
        validate_document(document, root / identifier)
    baseline_ids = set()
    for baseline in state.get("baselines", []):
        identifier = baseline.get("id") if isinstance(baseline, dict) else None
        if not isinstance(identifier, str) or not ID.fullmatch(identifier) or identifier in baseline_ids:
            raise ValueError("Ungültige oder doppelte Baseline-ID in der Sicherung.")
        baseline_ids.add(identifier)
        directory = root / "baselines" / identifier
        hashes = baseline.get("hashes")
        required = {"segments.parquet", "snapshot.json", "taxonomy.json", "feature_sets.yaml"}
        if not isinstance(hashes, dict) or not required.issubset(hashes):
            raise ValueError("Unvollständige Baseline in der Sicherung.")
        for filename, expected in hashes.items():
            if (len(portable_path(filename).parts) != 1 or not isinstance(expected, str)
                    or not HASH.fullmatch(expected) or sha256_file(directory / filename) != expected):
                raise ValueError("Baseline-Prüfsumme in der Sicherung stimmt nicht.")
        snapshot = read_json(directory / "snapshot.json")
        validate_document(snapshot, directory)
        if snapshot["id"] != baseline.get("documentId"):
            raise ValueError("Baseline und Referenztext in der Sicherung stimmen nicht überein.")
    return state


def unpack_archive(path, root):
    if Path(path).stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("ZIP-Datei zu groß (max. 1 GB).")
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_FILES + 1 or sum(info.file_size for info in entries) > MAX_DATA_BYTES + MAX_JSON_BYTES:
            raise ValueError("Sicherung zu groß (max. 100.000 Dateien und 4 GB entpackt).")
        names = set()
        for info in entries:
            portable_path(info.filename)
            mode = info.external_attr >> 16
            if (info.filename.casefold() in names or info.is_dir() or info.flag_bits & 1
                    or stat.S_IFMT(mode) not in (0, stat.S_IFREG)
                    or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                raise ValueError("Ungültige oder doppelte Dateien in der Sicherung.")
            names.add(info.filename.casefold())
        manifest_info = archive.getinfo("manifest.json")
        if manifest_info.file_size > MAX_JSON_BYTES:
            raise ValueError("Sicherungsverzeichnis zu groß.")
        manifest = json.loads(archive.read(manifest_info))
        if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
            raise ValueError("Bitte eine Bookalyzer-Datenbestandssicherung wählen.")
        if type(manifest.get("version")) is not int or manifest["version"] != VERSION:
            raise ValueError("Diese Sicherungsversion wird nicht unterstützt.")
        files = manifest.get("files")
        if not isinstance(files, dict) or "library.json" not in files:
            raise ValueError("Bibliotheksverzeichnis fehlt in der Sicherung.")
        if {info.filename for info in entries} != {"manifest.json", *("library/" + name for name in files)}:
            raise ValueError("Sicherung enthält fehlende oder zusätzliche Dateien.")
        total = 0
        for name, record in files.items():
            relative = portable_path(name)
            if (not isinstance(record, dict) or type(record.get("size")) is not int or record["size"] < 0
                    or not isinstance(record.get("sha256"), str) or not HASH.fullmatch(record["sha256"])):
                raise ValueError("Ungültige Prüfsummen in der Sicherung.")
            info = archive.getinfo("library/" + name)
            if record["size"] != info.file_size:
                raise ValueError("Dateigröße in der Sicherung stimmt nicht.")
            target = root.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            digest, size = hashlib.sha256(), 0
            with archive.open(info) as reader, target.open("xb") as writer:
                for block in iter(lambda: reader.read(1024 * 1024), b""):
                    size += len(block)
                    total += len(block)
                    if size > record["size"] or total > MAX_DATA_BYTES:
                        raise ValueError("Entpackter Datenbestand ist zu groß.")
                    writer.write(block)
                    digest.update(block)
            if size != record["size"] or digest.hexdigest() != record["sha256"]:
                raise ValueError("Prüfsumme in der Sicherung stimmt nicht. Die Datei ist beschädigt.")
        return manifest, total


def discard_import(service, id=None):
    pending = service.archive_import
    if pending and (id is None or pending["preview"]["id"] == id):
        service.archive_import = None
        pending["temporary"].cleanup()
    return {"discarded": True}


def inspect_library(service, path):
    from .desktop import DesktopService
    with service.lock:
        require_idle(service)
        discard_import(service)
        temporary = tempfile.TemporaryDirectory(dir=service.root.parent, prefix=".bookalyzer-import-", ignore_cleanup_errors=True)
        root = Path(temporary.name) / "library"
        root.mkdir()
        try:
            manifest, total = unpack_archive(path, root)
            validate_library(root)
            # Run the same local migrations as startup, while all writes are isolated.
            staged = DesktopService(root, seed=False)
            try:
                # An explicit restore initializes the library, including an empty one.
                # Development startup must not add unrelated project analyses later.
                staged.state["seeded"] = True
                staged._persist()
                state = staged.state
            finally:
                staged.executor.shutdown(wait=True)
            preview = {"id": uuid.uuid4().hex, "name": Path(path).name,
                       "createdAt": manifest.get("createdAt"), "fileCount": len(manifest["files"]),
                       "bytes": total, "documentCount": sum(d["status"] != "draft" for d in state["documents"]),
                       "baselineCount": len(state["baselines"])}
            service.archive_import = {"temporary": temporary, "root": root, "state": state, "preview": preview}
            return preview
        except Exception as error:
            temporary.cleanup()
            detail = ("Die Datei ist keine gültige ZIP-Sicherung oder ist beschädigt."
                      if isinstance(error, zipfile.BadZipFile) else str(error))
            raise ValueError("Sicherung konnte nicht geladen werden: " + detail) from error


def import_library(service, id, replaceConfirmed=False):
    with service.lock:
        require_idle(service)
        pending = service.archive_import
        if not pending or pending["preview"]["id"] != id:
            raise ValueError("Bitte die Sicherung erneut auswählen und prüfen.")
        if replaceConfirmed is not True:
            raise ValueError("Das Ersetzen des Datenbestands bitte ausdrücklich bestätigen.")
        backup_dir = service.root.parent / (service.root.name + "-backups")
        stamp = utc_now().replace(":", "-")
        backup = backup_dir / f"Bookalyzer-vor-Import-{stamp}-{uuid.uuid4().hex[:8]}.zip"
        export_library(service, backup)
        temporary = Path(tempfile.mkdtemp(dir=service.root.parent, prefix=".bookalyzer-previous-")).resolve()
        previous = temporary / "library"
        can_remove_previous = False
        try:
            service.root.replace(previous)
            try:
                pending["root"].replace(service.root)
            except Exception:
                try:
                    previous.replace(service.root)
                    can_remove_previous = True
                except OSError as rollback_error:
                    raise RuntimeError(f"Wiederherstellung fehlgeschlagen. Bisherige Daten: {previous}; ZIP-Sicherung: {backup}") from rollback_error
                raise
            service.state = pending["state"]
            service.comparisons.clear()
            can_remove_previous = True
        finally:
            # Never remove the prior library if restoring it also failed.
            if can_remove_previous and temporary.is_relative_to(service.root.parent):
                shutil.rmtree(temporary, ignore_errors=True)
        preview = pending["preview"]
        discard_import(service, id)
        return {"documentCount": preview["documentCount"], "baselineCount": preview["baselineCount"],
                "backupPath": str(backup)}
