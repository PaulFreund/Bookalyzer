"""Local desktop service. JSON-lines IPC; private uploads never enter the source tree.

The existing StoryScope pipeline remains authoritative for narrative features.
Local surface statistics are descriptive and never become authorship probabilities.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import PROJECT_ROOT
from .feature_matrix import load_taxonomy
from .ingest import extract_book
from .provenance import sha256_file, utc_now, write_json
from .segment import assert_no_text_loss, segment_books
from .quality_catalog import GROUPS as QUALITY_GROUPS, VERSION as QUALITY_VERSION
from .quality import basic_metrics

DEFAULTS = {
    "language": "de", "mode": "local", "targetWords": 5000,
    "minWords": 3000, "maxWords": 7000, "excludeFrontmatter": True,
    "excludeBackmatter": True, "featureSet": "public_nonstyle_265",
    "model": "", "reasoningEffort": "low", "parallel": 3, "detectChapters": False,
    "qualityGroups": [group["id"] for group in QUALITY_GROUPS], "longSentenceWords": 30,
    "textProfile": "narrative", "longSentenceShare": 10,
}
PALETTE = ["#7262c4", "#239d95", "#d39542", "#c56882", "#508bc4", "#7d9961"]
AXES = [
    {"id": "TMP_ORD_010", "label": "Zeitsprünge", "short": "Zeitstruktur",
     "description": "Ausmaß chronologischer Diskontinuität; 1–5, auf 0–100 skaliert."},
    {"id": "SIT_MET_303", "label": "Thematische Explizitheit", "short": "Explizitheit",
     "description": "Wie ausdrücklich der Text seine Themen erklärt; 1–5, auf 0–100 skaliert."},
    {"id": "PLT_STR_003", "label": "Dichte der Nebenhandlungen", "short": "Nebenhandlungen",
     "description": "Keine / wenige / mehrere verwobene Nebenhandlungen; ordinal auf 0–100 skaliert."},
    {"id": "EVT_SCH_003", "label": "Steigerung der Ereignisse", "short": "Eskalation",
     "description": "Stärke der Ereigniseskalation; 1–5, auf 0–100 skaliert."},
    {"id": "PLT_MOR_006", "label": "Geschlossenheit des Endes", "short": "Abschluss",
     "description": "Grad des narrativen Abschlusses; 1–5, auf 0–100 skaliert."},
    {"id": "PLT_MOR_002", "label": "Moralische Ambivalenz", "short": "Ambivalenz",
     "description": "Anteil der Segmente mit ambivalenter/gemischter moralischer Haltung zum Protagonisten. Gültige andere Kategorien zählen 0, ambivalent_or_morally_mixed zählt 100."},
]
WORD = re.compile(r"[^\W\d_]+(?:[’'-][^\W\d_]+)*", re.UNICODE)


def validate_settings(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) - set(DEFAULTS):
        raise ValueError("Unbekannte Einstellungen.")
    settings = {**DEFAULTS, **raw}
    if settings["language"] not in ("de", "en", "und"):
        raise ValueError("Ungültige Sprache.")
    if settings["mode"] not in ("local", "codex"):
        raise ValueError("Ungültiger Analysemodus.")
    if settings["featureSet"] not in ("public_nonstyle_265", "full_304"):
        raise ValueError("Dieses Feature-Set ist nicht verfügbar.")
    if (not isinstance(settings["qualityGroups"], list)
            or any(not isinstance(group, str) or group not in {g["id"] for g in QUALITY_GROUPS} for group in settings["qualityGroups"])
            or len(set(settings["qualityGroups"])) != len(settings["qualityGroups"])):
        raise ValueError("Ungültige Qualitätsbereiche.")
    if type(settings["longSentenceWords"]) is not int or not 15 <= settings["longSentenceWords"] <= 80:
        raise ValueError("Die Grenze für lange Sätze muss zwischen 15 und 80 Wörtern liegen.")
    if settings["textProfile"] not in ("narrative", "informative", "technical"):
        raise ValueError("Unbekanntes Textprofil.")
    if type(settings["longSentenceShare"]) is not int or not 0 <= settings["longSentenceShare"] <= 100:
        raise ValueError("Der Zielanteil langer Sätze muss zwischen 0 und 100 Prozent liegen.")
    for key in ("minWords", "targetWords", "maxWords", "parallel"):
        if type(settings[key]) is not int:
            raise ValueError("Segmentgrößen und Parallelität müssen ganze Zahlen sein.")
    if not 100 <= settings["minWords"] <= settings["targetWords"] <= settings["maxWords"] <= 20000:
        raise ValueError("Segmentgrößen: 100 ≤ Minimum ≤ Ziel ≤ Maximum ≤ 20.000 Wörter.")
    if not 1 <= settings["parallel"] <= 6:
        raise ValueError("Parallelität muss zwischen 1 und 6 liegen.")
    for key in ("excludeFrontmatter", "excludeBackmatter", "detectChapters"):
        if type(settings[key]) is not bool:
            raise ValueError("Ungültige Bereinigungseinstellung.")
    if not isinstance(settings["model"], str) or not re.fullmatch(r"[\w./-]{0,100}", settings["model"]):
        raise ValueError("Ungültige Modell-ID.")
    from .codex_catalog import REASONING_EFFORTS
    if settings["reasoningEffort"] not in ("", *REASONING_EFFORTS):
        raise ValueError("Ungültiger Reasoning-Level.")
    return settings


def surface_metrics(text: str) -> dict[str, Any]:
    return basic_metrics(text)


def axis_value(value: Any, spec: Any) -> float | None:
    """Only map taxonomy-valid scalar values. No reference imputation or guessing."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    raw = str(value).strip()
    if raw.lower() in ("n/a", "nan", "none", ""):
        return None
    if spec.id == "PLT_MOR_002" and raw in spec.values:
        return 100.0 if raw == "ambivalent_or_morally_mixed" else 0.0
    if spec.feature_type == "ordinal":
        return 100 * spec.values.index(raw) / (len(spec.values) - 1) if raw in spec.values else None
    if spec.feature_type == "scale":
        try:
            numeric = float(raw) if re.fullmatch(r"\d+(?:\.\d+)?", raw) else (
                float(raw.split("_", 1)[0]) if raw in spec.values else float("nan"))
            allowed = [float(v.split("_", 1)[0]) for v in spec.values]
            if numeric in allowed and max(allowed) > min(allowed):
                return 100 * (numeric - min(allowed)) / (max(allowed) - min(allowed))
        except (ValueError, TypeError):
            pass
    return None


class DesktopService:
    def __init__(self, root: Path | None = None, *, seed: bool = True):
        self.root = Path(root or os.environ.get("BOOKANALYZER_DATA", PROJECT_ROOT / ".bookanalyzer")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.reference: dict[str, Any] | None = None
        self.comparisons: dict[str, Any] = {}
        self.model_catalog = None
        self.model_catalog_at = 0
        self.archive_import = None
        self.state_path = self.root / "library.json"
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
            for document in self.state["documents"]:
                if document["status"] in ("queued", "analyzing"):
                    document["status"] = "error"
                    document["error"] = "Analyse unterbrochen. Bereits extrahierte Merkmale sind gespeichert; mit Wiederholen fortsetzen."
                job = document.get("storyscope", {})
                if job.get("status") in ("queued", "analyzing"):
                    job["status"] = "error"
                    job["error"] = "StoryScope unterbrochen. Mit Fortsetzen werden gespeicherte Antworten wiederverwendet."
        else:
            self.state = {"settings": dict(DEFAULTS), "documents": [], "seeded": False}
        self.state.setdefault("baselines", [])
        self.state["settings"] = {**DEFAULTS, **self.state["settings"]}
        for document in self.state["documents"]:
            document["settings"] = {**DEFAULTS, **document["settings"]}
        if seed and not self.state["seeded"]:
            self._seed_existing()
            self.state["seeded"] = True
        for document in self.state["documents"]:
            profiles = document.get("narrative", {}).get("profiles", []) if document.get("narrative") else []
            if document["status"] == "ready" and (document.get("localMetricsVersion") != QUALITY_VERSION or
                    (profiles and [p["id"] for p in profiles] != [axis["id"] for axis in AXES])):
                directory = self._directory(document["id"])
                completed = document.get("completedAt")
                self._complete(document, pd.read_parquet(directory / "segments.parquet"),
                               pd.read_parquet(directory / "features.parquet") if (directory / "features.parquet").is_file() else None)
                if completed:
                    document["completedAt"] = completed
        self._persist()

    def _persist(self) -> None:
        with self.lock:
            write_json(self.state_path, self.state)

    def _directory(self, identifier: str) -> Path:
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-f0-9]{32}", identifier):
            raise ValueError("Ungültige Dokument-ID.")
        return self.root / identifier

    def _document(self, identifier: str) -> dict[str, Any]:
        self._directory(identifier)
        for document in self.state["documents"]:
            if document["id"] == identifier:
                return document
        raise ValueError("Dokument nicht gefunden.")

    def _taxonomy(self):
        path = PROJECT_ROOT / "data/reference/storyscope/taxonomy.json"
        if not path.is_file():
            path = PROJECT_ROOT / "vendor/storyscope/data/taxonomy.json"
        return path, load_taxonomy(path)[1]

    def _seed_existing(self) -> None:
        """Import available, already-computed results without changing pipeline files."""
        segment_path = PROJECT_ROOT / "data/processed/book_segments.parquet"
        feature_path = PROJECT_ROOT / "data/features/book_features.parquet"
        if not segment_path.is_file():
            return
        segments = pd.read_parquet(segment_path)
        features = pd.read_parquet(feature_path) if feature_path.is_file() else pd.DataFrame()
        for _, group in segments.groupby("book_id", sort=False):
            identifier = uuid.uuid4().hex
            directory = self._directory(identifier)
            directory.mkdir()
            group = group.sort_values("segment_index")
            group.to_parquet(directory / "segments.parquet", index=False)
            section_path = PROJECT_ROOT / "data/processed/book_sections.parquet"
            if section_path.is_file():
                sections = pd.read_parquet(section_path)
                sections[sections.book_id == group.iloc[0].book_id].to_parquet(directory / "sections.parquet", index=False)
            matching = features[features["segment_id"].isin(group.segment_id)].copy() if not features.empty else pd.DataFrame()
            if len(matching) == len(group):
                matching.to_parquet(directory / "features.parquet", index=False)
            settings = {**DEFAULTS, "language": str(group.iloc[0].get("language", "und"))}
            document = self._make_document(identifier, Path(str(group.iloc[0].source_file)).name,
                                           str(group.iloc[0].book_title), group, settings)
            document["source"] = "Vorhandene Projektanalyse"
            self._complete(document, group, matching if len(matching) == len(group) else None)
            self.state["documents"].append(document)

    def _make_document(self, identifier, name, title, segments, settings):
        document = {
            "id": identifier, "name": name, "title": title, "settings": settings,
            "createdAt": utc_now(), "status": "draft", "error": None,
            "color": PALETTE[len(self.state["documents"]) % len(PALETTE)],
            "wordCount": int(segments.word_count.sum()), "segmentCount": len(segments),
            "segments": [{"index": int(row.segment_index), "id": str(row.segment_id),
                          "title": str(row.chapter_title), "words": int(row.word_count),
                          "preview": str(row.human_story)[:260]}
                         for row in segments.itertuples()],
        }
        directory = self._directory(identifier)
        document["provenance"] = {"segmentsSha256": sha256_file(directory / "segments.parquet")}
        imported = directory / "import.json"
        if imported.is_file():
            document["provenance"]["sourceSha256"] = json.loads(imported.read_text(encoding="utf-8"))["source_sha256"]
        return document

    def _complete(self, document, segments, features=None):
        from .desktop_quality import profile
        from .desktop_text import document_text, segment_texts
        basis = document_text(self, document["id"])
        text = basis["text"]
        document["metrics"] = surface_metrics(text)
        document["segmentMetrics"] = [surface_metrics(t) for t in segment_texts(basis)]
        document["localMetricsVersion"] = QUALITY_VERSION
        document["textBasis"] = {key: basis[key] for key in ("origin", "sha256", "note")}
        quality = profile(self, text, document["settings"])
        document["qualitySummary"] = {key: quality[key] for key in ("version", "values", "reasons", "words", "language")}
        document["narrative"] = None
        if features is not None and not features.empty:
            _, specs = self._taxonomy()
            profiles = []
            for axis in AXES:
                values = [axis_value(v, specs[axis["id"]]) for v in features[axis["id"]]]
                valid = [v for v in values if v is not None]
                profiles.append({**axis, "mean": round(float(np.mean(valid)), 2) if valid else None,
                                 "values": values, "n": len(valid), "total": len(values)})
            models = sorted(set(str(v) for v in features.get("extraction_model", pd.Series(["unbekannt"]))))
            efforts = sorted(set(str(v) for v in features.get("extraction_reasoning_effort", pd.Series(dtype=str)).dropna()))
            document["narrative"] = {"profiles": profiles, "featureCount": len(specs),
                                     "model": ", ".join(models), "provider": "codex-cli",
                                     "reasoningEffort": ", ".join(efforts) or document["settings"]["reasoningEffort"],
                                     "exploratory": True}
            document.setdefault("provenance", {})["taxonomySha256"] = sha256_file(self._taxonomy()[0])
            feature_path = self._directory(document["id"]) / "features.parquet"
            if feature_path.is_file():
                document["provenance"]["featuresSha256"] = sha256_file(feature_path)
        document["status"] = "ready"
        document["completedAt"] = utc_now()
        document["error"] = None
        document["report"] = self._report_notes(document)

    @staticmethod
    def _report_notes(document):
        metrics = document["metrics"]
        notes = [
            format(document['wordCount'], ',').replace(',', '.') + f" Wörter in {document['segmentCount']} nicht überlappenden Segmenten.",
            f"Die mittlere Satzlänge beträgt {metrics['sentenceMean']:.1f} Wörter. "
            f"Die relative Streuung der Satzlängen beträgt {metrics['sentenceVariation']:.2f}.",
        ]
        if metrics["vocabulary"] is not None:
            notes.append(f"Pro vollständigem 100-Wort-Fenster sind im Mittel {metrics['vocabulary']:.1f} "
                         "verschiedene Wörter vorhanden. Das beschreibt lexikalische Vielfalt, keine literarische Qualität.")
        if document.get("narrative"):
            notes.append("304 StoryScope-Merkmale wurden dimensionsweise extrahiert. Das Profil zeigt sechs "
                         "einzeln interpretierbare Merkmale. Höhere Werte bedeuten eine stärkere Ausprägung, keine bessere Qualität.")
        else:
            notes.append("Dieses lokale Textprofil enthält keine StoryScope-Merkmalsextraktion und keine Aussage zur Urheberschaft.")
        if document["wordCount"] < 3000:
            notes.append("Kurzer Text: Die Studie untersucht überwiegend Geschichten um 5.000 Wörter; narrative Merkmale können hier instabil sein.")
        if document["settings"]["language"] != "en":
            notes.append("Sprachgrenze: Der veröffentlichte Referenzkorpus ist englisch. Ein Vergleich in einer anderen Sprache ist explorativ.")
        if document.get("qualitySummary"):
            values = document["qualitySummary"]["values"]
            count = sum(value is not None for value in values.values())
            notes.append(f"Das lokale Qualitätslabor enthält {count} verfügbare Kennzahlen; Formeln, Sprachgrenzen und Fundstellen sind dort einsehbar.")
        return notes

    def _references(self):
        if self.reference is not None:
            return self.reference
        path = PROJECT_ROOT / "data/reference/storyscope/storyscope_features.parquet"
        if not path.is_file():
            return {"available": False, "profiles": []}
        _, specs = self._taxonomy()
        frame = pd.read_parquet(path, columns=["source"] + [axis["id"] for axis in AXES])
        groups = {"human": frame[frame.source == "human"], "ai": frame[frame.source.isin(["claude", "gpt", "gemini", "kimi", "deepseek"])]}
        profiles = []
        for axis in AXES:
            item = dict(axis)
            for name, group in groups.items():
                values = [axis_value(v, specs[axis["id"]]) for v in group[axis["id"]]]
                valid = [v for v in values if v is not None]
                item[name] = {"mean": round(float(np.mean(valid)), 2) if valid else None,
                              "n": len(valid), "total": len(values),
                              "q25": round(float(np.percentile(valid, 25)), 2) if valid else None,
                              "q75": round(float(np.percentile(valid, 75)), 2) if valid else None}
            profiles.append(item)
        self.reference = {
            "available": True, "profiles": profiles, "rows": len(frame),
            "scope": "Veröffentlichte Merkmalswerte · alle Splits · deskriptiv, kein Klassifikator",
            "sha256": sha256_file(path),
            "policy": "Nur taxonomiekonforme Werte je Merkmal; fehlende/ungültige Werte ausgeschlossen. n und Gesamtzahl stehen pro Merkmal.",
        }
        return self.reference

    def bootstrap(self, **_):
        from .codex_adapter import configured_codex_model
        with self.lock:
            result = json.loads(json.dumps(self.state, ensure_ascii=False))
        result["documents"] = [doc for doc in result["documents"] if doc["status"] != "draft"]
        for document in result["documents"]:
            if (document["status"] in ("queued", "analyzing") or
                    document.get("storyscope", {}).get("status") in ("queued", "analyzing")) and document["settings"]["mode"] == "codex":
                response_dir = self._directory(document["id"]) / "responses"
                complete = sum(1 for path in response_dir.glob("*/*.json") if not path.name.endswith(".last-message.json"))
                document["progress"] = {"completed": complete, "total": document["segmentCount"] * 10}
        result["reference"] = self._references()
        result["model"] = configured_codex_model()
        gate = PROJECT_ROOT / "reproduction/metrics.json"
        metrics = json.loads(gate.read_text(encoding="utf-8")) if gate.is_file() else {}
        result["method"] = {
            "study": "StoryScope", "version": "v4 · 13. April 2026",
            "url": "https://arxiv.org/abs/2604.03136",
            "externalRarityAvailable": False,
            "externalReason": "Die vorhandene Referenzprüfung ist gesperrt: veröffentlichte Merkmalswerte sind teilweise nicht mit der Taxonomie vereinbar."
                             if not metrics.get("book_quality_gate_passed") else "Der Desktop zeigt den gemeinsamen internen Vergleich; externe Perzentile sind hier nicht implementiert.",
            "featureSet": "public_nonstyle_265", "library": str(self.root),
        }
        return result

    def settings(self, settings):
        validated = validate_settings(settings)
        with self.lock:
            self.state["settings"] = validated
            self._persist()
        return validated

    def codex_models(self, refresh=False):
        from .codex_adapter import configured_codex_model
        from .codex_catalog import read_models
        if refresh or self.model_catalog is None or time.monotonic() - self.model_catalog_at > 300:
            try:
                models = read_models()
                self.model_catalog = {"available": bool(models), "models": models,
                                      "reason": None if models else "Codex hat keine Modelle geliefert."}
            except (OSError, RuntimeError, TimeoutError, subprocess.SubprocessError) as error:
                self.model_catalog = {"available": False, "models": [],
                                      "reason": "Modellliste nicht verfügbar: " + str(error)}
            self.model_catalog_at = time.monotonic()
        return {**self.model_catalog, "configuredModel": configured_codex_model()}

    def _pin_codex_options(self, settings):
        from .codex_adapter import configured_codex_model, DEFAULT_REASONING_EFFORT
        result = dict(settings)
        result["model"] = result["model"] or configured_codex_model()
        model = next((m for m in self.codex_models()["models"] if m["id"] == result["model"]), None)
        result["reasoningEffort"] = result["reasoningEffort"] or (
            model.get("defaultReasoningEffort") if model else None) or DEFAULT_REASONING_EFFORT
        if model and model["reasoningEfforts"] and result["reasoningEffort"] not in model["reasoningEfforts"]:
            raise ValueError(f"{result['model']} unterstützt den Reasoning-Level {result['reasoningEffort']} nicht.")
        return result

    def prepare(self, name, base64data, settings):
        settings = validate_settings(settings)
        name = Path(str(name).replace("\\", "/")).name
        if Path(name).suffix.lower() not in (".txt", ".docx", ".epub", ".pdf"):
            raise ValueError("Bitte TXT, DOCX, EPUB oder ein textbasiertes PDF wählen.")
        if not isinstance(base64data, str) or len(base64data) > 42 * 1024 * 1024:
            raise ValueError("Datei zu groß (max. 30 MB).")
        payload = base64.b64decode(base64data, validate=True)
        if not payload or len(payload) > 30 * 1024 * 1024:
            raise ValueError("Datei leer oder größer als 30 MB.")
        identifier = uuid.uuid4().hex
        directory = self._directory(identifier)
        directory.mkdir()
        source = directory / ("source" + Path(name).suffix.lower())
        source.write_bytes(payload)
        inventory, sections, transformations = extract_book(
            source, language=settings["language"], exclude_frontmatter=settings["excludeFrontmatter"],
            exclude_backmatter=settings["excludeBackmatter"])
        # TXT has no document title; retain the user-visible filename.
        if source.suffix == ".txt" or inventory["book_title"] == source.stem:
            inventory["book_title"] = Path(name).stem
            for section in sections:
                section["book_title"] = inventory["book_title"]
        sections_frame = pd.DataFrame(sections)
        sections_frame.to_parquet(directory / "sections.parquet", index=False)
        segments = segment_books(directory / "sections.parquet", directory / "segments.parquet",
                                 target_words=settings["targetWords"], min_words=settings["minWords"],
                                 max_words=settings["maxWords"], respect_chapters=settings["detectChapters"])
        if len(segments) == 0:
            raise ValueError("Kein auswertbarer Text gefunden.")
        assert_no_text_loss(sections_frame, segments)
        write_json(directory / "import.json", {"inventory": inventory, "transformations": transformations,
                                              "settings": settings, "source_sha256": hashlib.sha256(payload).hexdigest()})
        document = self._make_document(identifier, name, inventory["book_title"], segments, settings)
        document["chapterCount"] = int(sections_frame[sections_frame.included.astype(bool)].chapter_index.nunique())
        with self.lock:
            self.state["documents"].append(document)
            self._persist()
        return document

    def start(self, ids, consent=False, approver="", previewConfirmed=False):
        if not isinstance(ids, list) or not ids or len(ids) > 12 or len(set(ids)) != len(ids):
            raise ValueError("Bitte 1–12 unterschiedliche Dokumente wählen.")
        documents = [self._document(identifier) for identifier in ids]
        if any(doc["status"] not in ("draft", "error") for doc in documents):
            raise ValueError("Diese Analyse wurde bereits gestartet.")
        external = any(doc["settings"]["mode"] == "codex" for doc in documents)
        if external and (consent is not True or previewConfirmed is not True or not str(approver).strip()):
            raise ValueError("Für StoryScope: Segmentvorschau prüfen und Übertragung an OpenAI ausdrücklich freigeben.")
        pinned = {doc["id"]: self._pin_codex_options(doc["settings"])
                  for doc in documents if doc["settings"]["mode"] == "codex"}
        for document in documents:
            with self.lock:
                # Pin the resolved model at authorization time, including retries.
                if document["settings"]["mode"] == "codex":
                    document["settings"] = pinned[document["id"]]
                document["status"] = "queued"
                document["error"] = None
                document["approval"] = {"consent": bool(consent), "previewConfirmed": bool(previewConfirmed),
                                         "approver": str(approver).strip(), "at": utc_now()}
                self._persist()
            self.executor.submit(self._run, document["id"])
        return {"started": ids}

    def retry(self, id):
        document = self._document(id)
        approval = document.get("approval", {})
        if document["status"] == "ready" and document.get("storyscope", {}).get("status") == "error":
            return self.storyscope_start(id, model=document["settings"]["model"],
                                        reasoningEffort=document["settings"]["reasoningEffort"],
                                        parallel=document["settings"]["parallel"],
                                        featureSet=document["settings"]["featureSet"],
                                        consent=approval.get("consent", False),
                                        approver=approval.get("approver", ""),
                                        previewConfirmed=approval.get("previewConfirmed", False))
        return self.start([id], consent=approval.get("consent", False), approver=approval.get("approver", ""),
                          previewConfirmed=approval.get("previewConfirmed", False))

    def storyscope_start(self, id, model="", parallel=3, featureSet="public_nonstyle_265", reasoningEffort="low",
                         consent=False, approver="", previewConfirmed=False):
        """Add narrative features to a completed local analysis without replacing its text."""
        with self.lock:
            document = self._document(id)
            if document["status"] != "ready":
                raise ValueError("Bitte zuerst die lokale Analyse abschließen.")
            if document.get("narrative"):
                raise ValueError("Für diesen Text ist StoryScope bereits fertig.")
            if document.get("storyscope", {}).get("status") in ("queued", "analyzing"):
                raise ValueError("StoryScope wurde für diesen Text bereits gestartet.")
            if consent is not True or previewConfirmed is not True or not str(approver).strip():
                raise ValueError("Für StoryScope: Segmentvorschau prüfen und Übertragung an OpenAI ausdrücklich freigeben.")
            settings = validate_settings({**document["settings"], "mode": "codex", "model": model,
                                          "parallel": parallel, "featureSet": featureSet, "reasoningEffort": reasoningEffort})
            settings = self._pin_codex_options(settings)
            previous = document.get("storyscope", {})
            if previous.get("status") == "error" and settings["model"] != document["settings"]["model"]:
                raise ValueError("Zum Fortsetzen bitte das bisherige Modell verwenden.")
            if previous.get("status") == "error" and settings["reasoningEffort"] != document["settings"]["reasoningEffort"]:
                raise ValueError("Zum Fortsetzen bitte den bisherigen Reasoning-Level verwenden.")
            document["settings"] = settings
            document["storyscope"] = {"status": "queued", "error": None, "startedAt": utc_now()}
            document["approval"] = {"consent": True, "previewConfirmed": True,
                                     "approver": str(approver).strip(), "at": utc_now()}
            self._persist()
            self.executor.submit(self._run, id, supplement=True)
        return {"started": [id]}

    def local_update(self, id, settings):
        """Recompute local diagnostics while preserving narrative features and authorization."""
        allowed = {"qualityGroups", "longSentenceWords", "longSentenceShare", "textProfile"}
        if not isinstance(settings, dict) or set(settings) - allowed:
            raise ValueError("Hier können nur die lokalen Qualitätsmethoden geändert werden.")
        with self.lock:
            document = self._document(id)
            failed_storyscope = document["status"] == "error" and document["settings"]["mode"] == "codex"
            if document["status"] != "ready" and not failed_storyscope:
                raise ValueError("Bitte die Textanalyse zuerst abschließen.")
            validated = validate_settings({**document["settings"], **settings})
            directory = self._directory(id)
            segments = pd.read_parquet(directory / "segments.parquet")
            features = pd.read_parquet(directory / "features.parquet") if document.get("narrative") else None
            if failed_storyscope:
                document["storyscope"] = {"status": "error", "error": document["error"],
                                           "startedAt": document.get("approval", {}).get("at", utc_now())}
            document["settings"] = validated
            self._complete(document, segments, features)
            self.comparisons.clear()
            self._persist()
        return document

    def _run(self, identifier, *, supplement=False):
        directory = self._directory(identifier)
        document = self._document(identifier)
        try:
            with self.lock:
                if supplement:
                    document["storyscope"]["status"] = "analyzing"
                else:
                    document["status"] = "analyzing"
                self._persist()
            segments = pd.read_parquet(directory / "segments.parquet")
            features = None
            if document["settings"]["mode"] == "codex":
                from .codex_adapter import CODEX_PROVIDER, extract_features_with_codex
                from .feature_matrix import compile_feature_jsons
                from .segment import approve_segments
                from .storyscope_adapter import RIGHTS_CONFIRMATION, record_rights_approval
                approval = document["approval"]
                model = document["settings"]["model"]
                approve_segments(directory / "segments.parquet", directory / "segment_approval.json",
                                 approver=approval["approver"], note="Desktop: Segmentvorschau explizit bestätigt.")
                record_rights_approval(rights_holder=approval["approver"], approver=approval["approver"],
                                       confirmation=RIGHTS_CONFIRMATION, provider=CODEX_PROVIDER, model=model,
                                       segments_path=directory / "segments.parquet", output_path=directory / "rights.yaml",
                                       authorization_note="Desktop: Übertragung an OpenAI für diesen Upload bestätigt.")
                taxonomy, _ = self._taxonomy()
                extract_features_with_codex(
                    segments_path=directory / "segments.parquet", taxonomy_path=taxonomy,
                    output_dir=directory / "raw", response_dir=directory / "responses",
                    schema_dir=directory / "schemas", model=model, parallel=document["settings"]["parallel"],
                    reasoning_effort=document["settings"]["reasoningEffort"],
                    segment_approval_path=directory / "segment_approval.json", rights_approval_path=directory / "rights.yaml")
                features = compile_feature_jsons(directory / "raw", taxonomy, directory / "segments.parquet", directory / "features.parquet")
                if len(features) != len(segments):
                    raise ValueError("Extraktion unvollständig. Mit Wiederholen fortsetzen; vollständige Antworten werden wiederverwendet.")
            with self.lock:
                self._complete(document, segments, features)
                if supplement:
                    document["storyscope"].update(status="ready", error=None, completedAt=utc_now())
                self.comparisons.clear()
                self._persist()
        except Exception as error:
            with self.lock:
                if supplement:
                    document["storyscope"].update(status="error", error=str(error))
                else:
                    document["status"] = "error"
                    document["error"] = str(error)
                self._persist()

    def compare(self, ids):
        if not isinstance(ids, list) or len(ids) > 6 or len(set(ids)) != len(ids):
            raise ValueError("Maximal sechs unterschiedliche Texte vergleichen.")
        documents = [self._document(identifier) for identifier in ids]
        documents = [doc for doc in documents if doc.get("narrative") and doc["status"] == "ready"]
        key = "|".join(sorted(doc["id"] + doc.get("completedAt", "") for doc in documents))
        if key in self.comparisons:
            return self.comparisons[key]
        if not documents:
            return {"available": False, "reason": "Für den narrativen Vergleich werden StoryScope-Merkmale benötigt.", "series": []}
        feature_sets = set(doc["settings"]["featureSet"] for doc in documents)
        if len(feature_sets) != 1:
            return {"available": False, "reason": "Für eine gemeinsame Seltenheitsskala müssen alle Texte dasselbe Feature-Set verwenden.", "series": []}
        if len({doc["narrative"]["model"] for doc in documents}) > 1:
            return {"available": False, "reason": "Unterschiedliche Extraktionsmodelle: eine gemeinsame narrative Distanz wäre nicht vergleichbar.", "series": []}
        if len({doc["narrative"].get("reasoningEffort") or doc["settings"].get("reasoningEffort") or "low" for doc in documents}) > 1:
            return {"available": False, "reason": "Unterschiedliche Reasoning-Level: eine gemeinsame narrative Distanz wäre nicht vergleichbar.", "series": []}
        frames = []
        for doc in documents:
            frame = pd.read_parquet(self._directory(doc["id"]) / "features.parquet").copy()
            frame["book_id"] = doc["id"]
            frame["segment_id"] = [doc["id"] + ":" + str(i) for i in range(len(frame))]
            frame["book_title"] = doc["title"]
            frames.append(frame)
        combined = pd.concat(frames, ignore_index=True)
        if len(combined) < 2:
            return {"available": False, "reason": "Interne Seltenheit benötigt mindestens zwei narrative Segmente.", "series": []}
        if len(combined) > 3000:
            return {"available": False, "reason": "Bitte die Auswahl auf maximal 3.000 Segmente begrenzen.", "series": []}
        from .report import _book_internal_space
        from .rarity import score_internal_leave_one_out
        taxonomy, _ = self._taxonomy()
        normalized, matrix, _, encoder, _ = _book_internal_space(
            combined, taxonomy_path=taxonomy, feature_set=next(iter(feature_sets)))
        scored = score_internal_leave_one_out(normalized, matrix, k=25, backend="numpy")
        series, centroids = [], []
        for doc in documents:
            mask = combined.book_id == doc["id"]
            rows = scored[mask].sort_values("segment_index")
            values = [float(value) for value in rows.internal_raw_rarity]
            series.append({"id": doc["id"], "title": doc["title"], "values": values,
                           "mean": float(np.mean(values)), "median": float(np.median(values)),
                           "indices": [int(value) for value in rows.segment_index]})
            centroids.append(matrix[mask].mean(axis=0))
        distance = [[float(np.linalg.norm(a - b)) for b in centroids] for a in centroids]
        result = {"available": True, "series": series, "distance": distance,
                  "featureSet": next(iter(feature_sets)), "dimensions": encoder.encoded_dimension,
                  "k": min(25, len(combined) - 1), "segments": len(combined),
                  "scope": "Gemeinsamer interner Referenzraum der ausgewählten Texte",
                  "note": "Z-Standardisierung auf dieser Auswahl. Mittlere euklidische Distanz zu den nächsten übrigen Segmenten. "
                          "Kein externes Perzentil; Werte ändern sich mit der Auswahl. Doppelimporte verändern die Referenz.",
                  "languages": sorted(set(doc["settings"]["language"] for doc in documents))}
        self.comparisons[key] = result
        return result

    def segment(self, id, index):
        document = self._document(id)
        if type(index) is not int or not 0 <= index < document["segmentCount"]:
            raise ValueError("Ungültiges Segment.")
        from .desktop_text import document_text, segment_texts
        return {"text": segment_texts(document_text(self, id))[index], **document["segments"][index]}

    def baseline_create(self, id, name=""):
        from .desktop_compare import create_baseline
        with self.lock:
            if self._document(id).get("storyscope", {}).get("status") in ("queued", "analyzing"):
                raise ValueError("Bitte StoryScope abschließen, bevor du eine neue Baseline dieses Textes speicherst.")
            return create_baseline(self, id, name)

    def baseline_remove(self, id):
        self._directory(id)
        with self.lock:
            self.state["baselines"] = [b for b in self.state["baselines"] if b["id"] != id]
            self._persist()
        return {"removed": id}

    def baseline_compare(self, ids, baselineId):
        from .desktop_compare import compare_baseline
        return compare_baseline(self, ids, baselineId)

    def chapters(self, id, baselineId=None):
        from .desktop_compare import chapters
        return chapters(self, id, baselineId)

    def chapter_text(self, id, index):
        from .desktop_compare import chapter_sections
        self._document(id)
        sections = chapter_sections(self, id)
        if type(index) is not int or index not in set(sections.chapter_index):
            raise ValueError("Kapitel nicht gefunden.")
        section = sections[sections.chapter_index == index].iloc[0]
        return {"text": str(section.content), "title": str(section.chapter_title)}

    def remove(self, id):
        document = self._document(id)
        if (document["status"] in ("queued", "analyzing") or
                document.get("storyscope", {}).get("status") in ("queued", "analyzing")):
            raise ValueError("Laufende Analyse kann nicht ausgeblendet werden.")
        with self.lock:
            self.state["documents"] = [doc for doc in self.state["documents"] if doc["id"] != id]
            self.comparisons.clear()
            self._persist()
        return {"removed": id}

    def call(self, method, params):
        if method not in ("bootstrap", "settings", "codex_models", "prepare", "start", "storyscope_start", "local_update", "compare", "segment", "remove", "retry",
                          "baseline_create", "baseline_remove", "baseline_compare", "chapters", "chapter_text",
                          "quality", "quality_progression", "quality_excerpt", "quality_decision", "quality_findings",
                          "library_export", "library_inspect", "library_import", "library_discard"):
            raise ValueError("Unbekannte Aktion.")
        if not isinstance(params, dict):
            raise ValueError("Ungültige Anfrage.")
        return getattr(self, method)(**params)

    def library_export(self, path):
        from .desktop_archive import export_library
        return export_library(self, path)

    def library_inspect(self, path):
        from .desktop_archive import inspect_library
        return inspect_library(self, path)

    def library_import(self, id, replaceConfirmed=False):
        from .desktop_archive import import_library
        return import_library(self, id, replaceConfirmed)

    def library_discard(self, id):
        from .desktop_archive import discard_import
        return discard_import(self, id)

    def quality(self, ids, bookId=None, baselineId=None):
        from .desktop_quality import report
        return report(self, ids, bookId, baselineId)

    def quality_progression(self, id, baselineId=None):
        from .desktop_quality import progression
        return progression(self, id, baselineId)

    def quality_excerpt(self, id, start, end, chapterIndex=None):
        from .desktop_quality import excerpt
        return excerpt(self, id, start, end, chapterIndex)

    def quality_decision(self, id, textSha256, metric, start, end, intentional, chapterIndex=None):
        from .desktop_quality import decision
        return decision(self, id, textSha256, metric, start, end, intentional, chapterIndex)

    def quality_findings(self, id, textSha256, metric=None, status="open", offset=0, limit=6, chapterIndex=None):
        from .desktop_quality import findings
        return findings(self, id, textSha256, metric, status, offset, limit, chapterIndex)


def main():
    # JSON-lines is UTF-8 in both directions, including frozen Python on Windows,
    # where PYTHONUTF8 in the environment alone does not configure the bootloader.
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    service = DesktopService(seed=not getattr(sys, "frozen", False))
    for line in sys.stdin:
        request = {}
        try:
            request = json.loads(line)
            result = service.call(request["method"], request.get("params", {}))
            response = {"id": request["id"], "result": result}
        except Exception as error:
            response = {"id": request.get("id"), "error": str(error)}
        print(json.dumps(response, ensure_ascii=False, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
