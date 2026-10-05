"""Immutable personal baselines and chapter comparisons; no authorship classifier."""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from .config import PROJECT_ROOT
from .feature_matrix import canonicalize_feature_frame, resolve_feature_set
from .paper_encoder import PaperEncoder
from .provenance import sha256_file, sha256_text, utc_now, write_json
from .segment import assert_no_text_loss

METRICS = ("sentenceMean", "sentenceVariation", "vocabulary", "dialogue")


def create_baseline(service, identifier, name):
    from .desktop_text import document_text
    document = service._document(identifier)
    if document["status"] != "ready":
        raise ValueError("Nur fertige Analysen können als Baseline gespeichert werden.")
    if document["segmentCount"] > 3000:
        raise ValueError("Eine Baseline darf höchstens 3.000 Segmente enthalten.")
    if not isinstance(name, str) or len(name) > 120:
        raise ValueError("Baseline-Namen auf 120 Zeichen begrenzen.")
    snapshot = json.loads(json.dumps(document))
    baseline_id = uuid.uuid4().hex
    directory = service.root / "baselines" / baseline_id
    directory.mkdir(parents=True)
    source = service._directory(identifier)
    document_text(service, identifier)
    hashes = {}
    for filename in ("segments.parquet", "features.parquet", "text.json", "sections.parquet"):
        if (source / filename).is_file():
            shutil.copy2(source / filename, directory / filename)
            hashes[filename] = sha256_file(directory / filename)
    # Store the taxonomy as well: later software updates cannot silently change the space.
    shutil.copy2(service._taxonomy()[0], directory / "taxonomy.json")
    hashes["taxonomy.json"] = sha256_file(directory / "taxonomy.json")
    segments = pd.read_parquet(directory / "segments.parquet")
    baseline = {
        "id": baseline_id, "name": name.strip() or document["title"],
        "documentId": identifier, "documentTitle": document["title"],
        "createdAt": utc_now(), "wordCount": document["wordCount"],
        "segmentCount": document["segmentCount"], "narrative": bool(document.get("narrative")),
        "hashes": hashes, "textSha256": sha256_text(" ".join(" ".join(segments.human_story).split())),
    }
    write_json(directory / "snapshot.json", snapshot)
    hashes["snapshot.json"] = sha256_file(directory / "snapshot.json")
    shutil.copy2(PROJECT_ROOT / "config/feature_sets.yaml", directory / "feature_sets.yaml")
    hashes["feature_sets.yaml"] = sha256_file(directory / "feature_sets.yaml")
    with service.lock:
        service.state["baselines"].append(baseline)
        service._persist()
    return baseline


class BaselineSpace:
    def __init__(self, service, identifier):
        service._directory(identifier)  # validate before constructing a path
        self.info = next((b for b in service.state["baselines"] if b["id"] == identifier), None)
        if self.info is None:
            raise ValueError("Baseline nicht gefunden.")
        self.directory = service.root / "baselines" / identifier
        for filename, expected in self.info["hashes"].items():
            if sha256_file(self.directory / filename) != expected:
                raise ValueError("Baseline-Dateien wurden verändert. Bitte eine neue Baseline anlegen.")
        self.document = json.loads((self.directory / "snapshot.json").read_text(encoding="utf-8"))
        from .desktop_text import text_basis
        from .quality import basic_metrics
        # Derive current local counts without altering frozen narrative features or files.
        self.document["metrics"] = basic_metrics(text_basis(self.directory)["text"])
        self.matrix = None
        if self.info["narrative"]:
            from .feature_matrix import load_taxonomy
            _, self.specs = load_taxonomy(self.directory / "taxonomy.json")
            self.feature_ids = resolve_feature_set(self.document["settings"]["featureSet"], self.specs,
                                                   config_path=self.directory / "feature_sets.yaml")
            reference = pd.read_parquet(self.directory / "features.parquet")
            normalized, _ = canonicalize_feature_frame(reference, self.specs, self.feature_ids)
            self.encoder = PaperEncoder(self.specs, self.feature_ids)
            encoded = self.encoder.fit_transform(normalized)
            self.scaler = StandardScaler().fit(encoded)
            self.matrix = self.scaler.transform(encoded)
            self.k = min(25, len(reference))

    def score(self, document, features, metrics, *, text_hash=None):
        reference = self.document["metrics"]
        deltas = {key: round(metrics[key] - reference[key], 3)
                  if metrics.get(key) is not None and reference.get(key) is not None else None
                  for key in METRICS}
        result = {"delta": deltas, "distance": None, "values": [], "reason": None, "warnings": []}
        if document["settings"]["language"] != self.document["settings"]["language"]:
            result["warnings"].append("Unterschiedliche Textsprachen; Sprachwerte nur eingeschränkt vergleichbar.")
        if document["settings"]["targetWords"] != self.document["settings"]["targetWords"]:
            result["warnings"].append("Unterschiedliche Segmentgrößen können narrative Distanzen beeinflussen.")
        if self.matrix is None or not document.get("narrative"):
            result["reason"] = "Narrative Distanz benötigt StoryScope-Merkmale in Text und Baseline."
        elif features is None or features.empty:
            result["reason"] = "Keine vollständig zuordenbaren Kapitelmerkmale. Erneut mit Kapitelerkennung analysieren."
        elif document["id"] == self.info["documentId"] or text_hash == self.info["textSha256"]:
            result["reason"] = "Referenztext selbst: keine narrative Distanz zur eigenen Baseline."
        elif document["settings"]["featureSet"] != self.document["settings"]["featureSet"]:
            result["reason"] = "Unterschiedliche Feature-Sets; narrative Distanz gesperrt."
        elif document["narrative"]["model"] != self.document["narrative"]["model"]:
            result["reason"] = "Unterschiedliche Extraktionsmodelle; narrative Distanz gesperrt."
        elif (document["narrative"].get("reasoningEffort") or document["settings"].get("reasoningEffort") or "low") != (
                self.document["narrative"].get("reasoningEffort") or self.document["settings"].get("reasoningEffort") or "low"):
            result["reason"] = "Unterschiedliche Reasoning-Level; narrative Distanz gesperrt."
        elif document["settings"]["language"] != self.document["settings"]["language"]:
            result["reason"] = "Unterschiedliche Textsprachen; narrative Distanz gesperrt."
        elif document.get("provenance", {}).get("taxonomySha256") != self.info["hashes"]["taxonomy.json"]:
            result["reason"] = "Unterschiedliche Taxonomie-Versionen; narrative Distanz gesperrt."
        else:
            normalized, _ = canonicalize_feature_frame(features, self.specs, self.feature_ids)
            query = self.scaler.transform(self.encoder.transform(normalized))
            # Bounded memory: evaluate one query at a time; never refit on targets.
            values = []
            for row in query:
                distances = np.linalg.norm(self.matrix - row, axis=1)
                values.append(float(np.partition(distances, self.k - 1)[:self.k].mean()))
            result.update(distance=float(np.mean(values)), values=values)
            if len(self.matrix) < 5:
                result["warnings"].append("Kleine Baseline: weniger als fünf Segmente. Distanz rein deskriptiv.")
        return result

    def metadata(self):
        return {**self.info, "metrics": self.document["metrics"], "k": getattr(self, "k", None),
                "dimensions": self.matrix.shape[1] if self.matrix is not None else None,
                "note": "Encoder und Z-Standardisierung ausschließlich auf der gespeicherten Baseline. "
                        "Mittlere Distanz zu bis zu 25 Baseline-Segmenten, danach ungewichtetes Segmentmittel. "
                        "Konstante Baseline-Spalten behalten Skalierung 1. Kein Perzentil und kein Urheberschaftsnachweis."}


def compare_baseline(service, ids, baseline_id):
    if not isinstance(ids, list) or len(ids) > 6 or len(set(ids)) != len(ids):
        raise ValueError("Maximal sechs unterschiedliche Texte vergleichen.")
    baseline = BaselineSpace(service, baseline_id)
    rows = []
    for identifier in ids:
        document = service._document(identifier)
        if document["status"] != "ready":
            raise ValueError("Analyse noch nicht fertig.")
        directory = service._directory(identifier)
        features = pd.read_parquet(directory / "features.parquet") if document.get("narrative") else None
        segments = pd.read_parquet(directory / "segments.parquet")
        text_hash = sha256_text(" ".join(" ".join(segments.human_story).split()))
        rows.append({"id": identifier, "title": document["title"], "metrics": document["metrics"],
                     **baseline.score(document, features, document["metrics"], text_hash=text_hash)})
    return {"baseline": baseline.metadata(), "rows": rows}


def chapter_sections(service, identifier):
    directory = service._directory(identifier)
    path = directory / "sections.parquet"
    if not path.is_file():
        # Recover sections for legacy project imports only if their text exactly matches.
        legacy = PROJECT_ROOT / "data/processed/book_sections.parquet"
        if not legacy.is_file():
            raise ValueError("Dieser alte Import enthält keine Kapitelstruktur. Bitte mit Kapitelerkennung neu hochladen.")
        segments = pd.read_parquet(directory / "segments.parquet")
        all_sections = pd.read_parquet(legacy)
        sections = all_sections[all_sections.book_id == segments.iloc[0].book_id].copy()
        if sections.empty:
            raise ValueError("Kapitelstruktur fehlt. Bitte neu hochladen.")
        assert_no_text_loss(sections, segments)
        sections.to_parquet(path, index=False)
    frame = pd.read_parquet(path)
    return frame[frame.included.astype(bool)].sort_values("chapter_index")


def chapters(service, identifier, baseline_id=None):
    from .desktop import AXES, axis_value, surface_metrics
    document = service._document(identifier)
    if document["status"] != "ready":
        raise ValueError("Analyse noch nicht fertig.")
    sections = chapter_sections(service, identifier)
    directory = service._directory(identifier)
    segments = pd.read_parquet(directory / "segments.parquet").sort_values("segment_index")
    features = pd.read_parquet(directory / "features.parquet") if document.get("narrative") else None
    baseline = BaselineSpace(service, baseline_id) if baseline_id else None
    text_hash = sha256_text(" ".join(" ".join(segments.human_story).split()))
    _, specs = service._taxonomy()
    rows = []
    # Common chapter space uses this book only, giving stable pairwise centroid distances.
    matrix_by_id = {}
    if features is not None and len(features):
        from .report import _book_internal_space
        _, matrix, _, _, _ = _book_internal_space(features, taxonomy_path=service._taxonomy()[0],
                                                 feature_set=document["settings"]["featureSet"])
        matrix_by_id = dict(zip(features.segment_id, matrix))
    centroids = []
    for section in sections.itertuples():
        index = int(section.chapter_index)
        overlapping = segments[(segments.chapter_index <= index) & (segments.chapter_end_index >= index)]
        complete = bool(len(overlapping) and (overlapping.chapter_index == index).all()
                        and (overlapping.chapter_end_index == index).all())
        part = features[features.segment_id.isin(overlapping.segment_id)] if features is not None and complete else None
        metrics = surface_metrics(str(section.content))
        profiles = []
        if part is not None and len(part) == len(overlapping):
            for axis in AXES:
                values = [axis_value(v, specs[axis["id"]]) for v in part[axis["id"]]]
                valid = [value for value in values if value is not None]
                profiles.append({**axis, "mean": float(np.mean(valid)) if valid else None,
                                 "values": values, "n": len(valid), "total": len(values)})
        else:
            part = None
        centroid = np.mean([matrix_by_id[sid] for sid in part.segment_id], axis=0) if part is not None else None
        centroids.append(centroid)
        row = {"id": f"{identifier}:{index}", "index": index, "title": str(section.chapter_title),
               "words": int(section.word_count), "metrics": metrics, "profiles": profiles,
               "segmentIndices": overlapping.segment_index.astype(int).tolist(),
               "narrativeComplete": part is not None,
               "short": int(section.word_count) < document["settings"]["minWords"]}
        if baseline:
            row["comparison"] = baseline.score(document, part, metrics, text_hash=text_hash)
        rows.append(row)
    # Sparse-friendly JSON: missing narrative coverage is null, never zero.
    distance = [[float(np.linalg.norm(a - b)) if a is not None and b is not None else None
                 for b in centroids] for a in centroids] if len(rows) <= 400 else None
    return {"documentId": identifier, "title": document["title"], "chapters": rows,
            "distance": distance, "baseline": baseline.metadata() if baseline else None,
            "note": "Kapitel aus Dokumentüberschriften bzw. EPUB-Abschnitten; TXT/PDF anhand Kapitel-/Chapter-Zeilen. "
                    "Kurze Kapitel bleiben eigenständig. Narrative Kapitelwerte nur für vollständig enthaltene Segmente. "
                    "Kapitelmatrix: Distanz der Segmentmittelwerte im gemeinsamen Merkmalsraum dieses Buchs."}
