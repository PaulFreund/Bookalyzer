"""Reproduce the README's local analysis using Kafka's public-domain novella.

The download, source text and desktop library stay under ignored outputs/.
This script never imports the project's existing book analyses or calls a model.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bookanalyzer.desktop import DEFAULTS, DesktopService

SOURCE_URL = "https://www.gutenberg.org/cache/epub/22367/pg22367.txt"
SOURCE_SHA256 = "359d3f5983c812393f4bd7ee49a350ffffc7d476015e58d6b84b6c848dd2b0e9"
BOOK_URL = "https://www.gutenberg.org/ebooks/22367"
TITLE = "Die Verwandlung"
SETTINGS = {
    **DEFAULTS,
    "mode": "local",
    "language": "de",
    "detectChapters": True,
    "excludeFrontmatter": False,
    "excludeBackmatter": False,
    "targetWords": 3000,
    "minWords": 1500,
    "maxWords": 4500,
}


def prepare_text(raw: str) -> str:
    start = re.search(r"(?m)^I\.\s*$", raw)
    end = re.search(r"(?m)^\*\*\* END OF (?:THE|THIS) PROJECT GUTENBERG", raw)
    if start is None or end is None or end.start() <= start.start():
        raise ValueError("The source does not have the expected novel and license boundaries.")
    body = raw[start.start():end.start()]
    # Spell out the original Roman-numbered headings for the TXT chapter importer.
    body = re.sub(r"(?m)^([IVX]+)\.\s*$", r"\n\nTeil \1\n\n", body)
    paragraphs = [" ".join(block.split()) for block in re.split(r"\n\s*\n", body) if block.strip()]
    text = "\n\n".join(paragraphs) + "\n"
    if re.findall(r"(?m)^Teil ([IVX]+)$", text) != ["I", "II", "III"]:
        raise ValueError("Expected exactly the novella's three parts.")
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=ROOT / "outputs/readme-demo")
    parser.add_argument("--source", type=Path, help="Use an already-downloaded Gutenberg original.")
    args = parser.parse_args()
    destination = args.destination.resolve()
    source_dir = destination / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    original = args.source or source_dir / "project-gutenberg-22367.txt"
    if not original.is_file():
        if args.source:
            raise FileNotFoundError(original)
        request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Bookalyzer-README-demo"})
        with urllib.request.urlopen(request, timeout=60) as response:
            original.write_bytes(response.read())
    raw = original.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("The Gutenberg source differs from the README's pinned edition.")
    text = prepare_text(raw.decode("utf-8-sig"))
    payload = text.encode("utf-8")
    text_path = source_dir / f"{TITLE}.txt"
    text_path.write_bytes(payload)
    service = DesktopService(destination / "library", seed=False)
    # Prevent the source app's first-launch migration from importing private project data.
    service.state["seeded"] = True
    service.state["settings"] = dict(SETTINGS)
    service._persist()
    try:
        documents = service.state["documents"]
        if documents:
            if len(documents) != 1 or documents[0]["name"] != text_path.name:
                raise ValueError("Destination contains other documents; choose a new demo destination.")
            document = documents[0]
            imported = json.loads((service._directory(document["id"]) / "import.json").read_text(encoding="utf-8"))
            if imported["source_sha256"] != hashlib.sha256(payload).hexdigest():
                raise ValueError("Demo source changed; choose a new destination to preserve the old analysis.")
            if document["status"] != "ready":
                raise ValueError("Existing demo is incomplete; choose a new destination.")
        else:
            document = service.prepare(text_path.name, base64.b64encode(payload).decode("ascii"), SETTINGS)
            service.start([document["id"]])
            service.executor.shutdown(wait=True)
            if document["status"] != "ready":
                raise RuntimeError(document.get("error") or "The local analysis did not finish.")
        overview = service.quality(ids=[document["id"]])
        chapters = service.quality(ids=[], bookId=document["id"])
        if document["chapterCount"] != 3 or len(chapters["rows"]) != 3:
            raise ValueError("The analysis must contain all three original parts.")
        metrics = overview["rows"][0]["quality"]
        summary = {
            "book": {"title": TITLE, "author": "Franz Kafka", "language": "de", "source": BOOK_URL},
            "source": {"download": SOURCE_URL, "sha256": hashlib.sha256(raw).hexdigest(),
                       "analysis_text_sha256": hashlib.sha256(payload).hexdigest(),
                       "processing": ["Remove Gutenberg wrapper, credits and original title pages.",
                                      "Rename I., II., III. to Teil I, Teil II, Teil III.",
                                      "Unwrap print-width lines while preserving paragraph boundaries."]},
            "analysis": {"mode": "local", "word_count": document["wordCount"],
                         "chapter_count": document["chapterCount"], "segment_count": document["segmentCount"],
                         "metric_count": len(overview["catalog"]["metrics"]),
                         "segmentation": {k: SETTINGS[k] for k in ("targetWords", "minWords", "maxWords", "detectChapters")},
                         "metrics": metrics["values"]},
            "chapters": [{"title": row["title"], "word_count": row["quality"]["words"],
                          "metrics": row["quality"]["values"]} for row in chapters["rows"]],
        }
        (destination / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"title": TITLE, "words": document["wordCount"], "chapters": 3,
                          "segments": document["segmentCount"], "metrics": summary["analysis"]["metric_count"],
                          "source_sha256": summary["source"]["sha256"],
                          "library": str(service.root)}, ensure_ascii=False))
    finally:
        service.executor.shutdown(wait=True)


if __name__ == "__main__":
    main()
