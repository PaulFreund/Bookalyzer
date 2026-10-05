"""Length-matched, deterministic reference windows; bands are descriptive, not CIs."""
from statistics import median

from .quality import WORD, deltas, percentile
from .quality_catalog import CATALOG

LENGTH_DEPENDENT = {"entropy", "hapax", "topWords", "trigramRepeat", "sentenceRepeat", "startRepeat", "paragraphRepeat"}
STRUCTURAL = {"paragraphMean", "paragraphCV", "paragraphRepeat", "cohesion", "shifts"}


def compare_to_reference(service, target, reference):
    from .desktop_quality import profile
    text, settings = reference["_text"], reference["_settings"]
    tokens = list(WORD.finditer(text))
    n = target["words"]
    total = len(tokens)
    samples = []
    if n and n <= total:
        count = min(9, total // n)
        starts = [round(i * (total-n) / (count-1)) for i in range(count)] if count > 1 else [(total-n)//2]
        for start in starts:
            chunk = text if n == total else text[tokens[start].start():tokens[start+n-1].end()]
            samples.append(profile(service, chunk, settings))
    bands = {}
    base = reference["quality"]
    values, reasons = dict(base["values"]), dict(base["reasons"])
    if samples:
        for spec in CATALOG:
            key = spec["id"]
            valid = [q["values"][key] for q in samples if q["values"][key] is not None]
            if valid:
                values[key] = round(median(valid), 4)
                reasons.pop(key, None)
                bands[key] = dict(low=round(percentile(valid, .25), 4), median=values[key],
                                  high=round(percentile(valid, .75), 4), n=len(valid))
            else:
                values[key] = None
                reasons[key] = samples[0]["reasons"].get(key, "Keine vergleichbaren Referenzfenster.")
    else:
        for key in LENGTH_DEPENDENT:
            values[key] = None
            reasons[key] = "Die Baseline ist kürzer als dieser Text. Für diese längenabhängige Kennzahl sind gleich lange Ausschnitte erforderlich."
    if target.get("basis", {}).get("origin") == "legacy_segments" or base.get("basis", {}).get("origin") == "legacy_segments":
        for key in STRUCTURAL:
            values[key] = None
            reasons[key] = "Alte Textgrundlage ohne Originalabsätze. Für diesen Vergleich neu importieren und eine neue Baseline speichern."
            bands.pop(key, None)
    result = deltas(target, {**base, "values": values, "reasons": reasons})
    # Never paint a reference band for a metric whose comparison is unavailable.
    bands = {k: v for k, v in bands.items() if result["values"].get(k) is not None}
    word_label = format(n, ",").replace(",", ".")
    note = "Baseline kürzer als der Text: längenabhängige Vergleiche nicht verfügbar."
    if samples:
        note = (f"Ein gleich langer Referenzausschnitt mit {word_label} Wörtern. " if len(samples) == 1 else
                f"{len(samples)} gleich lange, nicht überlappende Referenzausschnitte mit je {word_label} Wörtern. Vergleichswert: Median. ")
        note += ("Das Band zeigt die mittleren 50 % der Ausschnitte, kein Konfidenzintervall." if len(samples) >= 3 else
                 "Weniger als drei Ausschnitte: kein Streuungsband.")
    return result, dict(basis="matched_windows" if samples else "short_reference", name=reference["name"],
                        words=n if samples else total, windows=len(samples), values=values, bands=bands,
                        note=note)
