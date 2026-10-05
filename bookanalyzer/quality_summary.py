"""Explain measurements and editable writing goals without inventing a quality score."""
from statistics import median

from .quality import percentile
from .quality_evidence import decision_key

PROFILES = {"narrative": "Erzähltext", "informative": "Sachtext", "technical": "Fachtext"}
PRIORITIES = [
    ("paragraphRepeat", "Doppelte Absätze prüfen", "Ein Absatz erscheint mehrfach. Prüfe, ob das beabsichtigt ist.", "Wiederholung"),
    ("sentenceRepeat", "Wiederholte Sätze prüfen", "Gleiche Wortfolgen können den Lesefluss bremsen oder ein bewusstes Stilmittel sein.", "Wiederholung"),
    ("longSentences", "Lange Sätze gezielt lesen", "Prüfe, ob sich die Information an diesen Stellen leicht erfassen lässt.", "Lesefluss"),
    ("commaChains", "Dichte Satzstruktur prüfen", "Mehrere Kommas können auf viele Einschübe oder eine Aufzählung hinweisen.", "Lesefluss"),
    ("nearRepeat", "Nahe Wortwiederholungen prüfen", "Lies die Wörter im Zusammenhang. Namen und bewusste Wiederholungen können sinnvoll sein.", "Wortwahl"),
    ("fillers", "Füllwortkandidaten prüfen", "Entscheide im Kontext, ob das Wort eine Funktion für Aussage oder Figurenstimme hat.", "Wortwahl"),
]


def peer_bands(rows):
    """Leave-one-chapter-out reference; length-controlled local descriptors only."""
    result = {}
    for row in rows:
        others = [r for r in rows if r["id"] != row["id"] and r["quality"]["words"] >= 300]
        bands = {}
        for metric in ("sentenceMean", "mattr", "nearRepeat"):
            valid = [r["quality"]["values"][metric] for r in others if r["quality"]["values"][metric] is not None]
            if len(valid) >= 4:
                bands[metric] = dict(low=percentile(valid, .25), high=percentile(valid, .75), median=median(valid), n=len(valid))
        result[row["id"]] = bands
    return result


def summarize(row, decisions=None, peers=None):
    q = row["quality"]
    values, counts = q["values"], q["evidenceCounts"]
    comparison = row.get("comparison")
    decisions = decisions or []
    ignored = set(decisions)
    evidence = [{**e, "key": decision_key(q, e, row.get("chapterIndex")),
                 "intentional": decision_key(q, e, row.get("chapterIndex")) in ignored} for e in q["evidence"]]
    q["evidence"] = evidence
    cutoff, goal = q["longSentenceWords"], q["longSentenceShare"]
    short = q["words"] < 300
    cards = []
    def number(value):
        return f"{value:.1f}".replace(".", ",")

    def card(id, label, status, title, detail, metric, value=None, target=None):
        if short or values.get(metric) is None:
            status = "unknown"
            detail = q["reasons"].get(metric) or "Weniger als 300 Wörter: nur eine erste Beobachtung, keine stabile Einordnung."
            if short:
                title = "Erste Beobachtung · kurzer Text"
            if values.get(metric) is None:
                title = "Zu wenig Grundlage"
        cards.append(dict(id=id, label=label, status=status, title=title, detail=detail, metric=metric,
                          value=values.get(metric) if value is None else value, target=target))

    share = values.get("longSentences")
    card("flow", "Lesefluss", "review" if share is not None and share > goal else "fit",
         "Mehr lange Sätze als gewünscht" if share is not None and share > goal else "Dein Längenziel wird eingehalten",
         f"{number(share)} % der Sätze haben mehr als {cutoff} Wörter. Dein Ziel: höchstens {goal} %." if share is not None else "",
         "longSentences", target=goal)
    vocab = values.get("mattr")
    band = comparison.get("bands", {}).get("mattr") if comparison else None
    adequate_band = band and band["n"] >= 3
    vocab_title = "Deine Wortvielfalt"
    if adequate_band and vocab is not None:
        vocab_title = "Weniger Vielfalt als die Referenz" if vocab < band["low"] else "Mehr Vielfalt als die Referenz" if vocab > band["high"] else "Ähnlich vielfältig wie die Referenz"
    card("vocabulary", "Wortwahl", "observe", vocab_title,
         (f"Im Mittel {number(vocab)} verschiedene Wortformen je 100 Wörter." if vocab is not None else "") +
         (f" Referenz: {number(band['low'])}–{number(band['high'])}. Eine Abweichung ist kein Qualitätsurteil." if adequate_band else
          " Ein passender Referenztext hilft bei der Einordnung."), "mattr")
    duplicates = counts.get("paragraphRepeat", 0) + counts.get("sentenceRepeat", 0)
    intentional_counts = q.get("intentionalCounts", {})
    pending_duplicates = duplicates-sum(intentional_counts.get(key, 0) for key in ("paragraphRepeat", "sentenceRepeat"))
    card("repetition", "Wiederholungen", "review" if pending_duplicates else "observe",
         f"{pending_duplicates} Textduplikate prüfen" if pending_duplicates else "Textduplikate als beabsichtigt markiert" if duplicates else "Keine längeren Textduplikate erkannt",
         "Erfasst werden gleiche Sätze ab 5 Wörtern und Absätze ab 12 Wörtern. Bewusste Wiederholungen bleiben möglich.", "sentenceRepeat")
    bands = comparison.get("bands", {}) if comparison else (peers or {})
    differences, eligible = [], []
    reference_name = comparison["name"] if comparison else "Übrige Kapitel"
    reference = "in deiner Referenz" if comparison else "in den übrigen Kapiteln"
    subject = "Dieses Kapitel" if row.get("chapterIndex") is not None else "Dein Text"
    descriptions = {
        "sentenceMean": ("Mittlere Satzlänge", "kürzere Sätze", "längere Sätze", "Wörter je Satz",
                         "Prüfe, ob der andere Satzrhythmus zur Szene und deiner beabsichtigten Wirkung passt."),
        "mattr": ("Wortvielfalt", "weniger Wortvielfalt", "mehr Wortvielfalt", "Wortformen je 100 Wörter",
                  "Prüfe, ob die Wortwahl zur Figurenstimme oder zum Thema passt. Mehr Vielfalt ist nicht automatisch besser."),
        "nearRepeat": ("Nahe Wortwiederholungen", "weniger nahe Wortwiederholungen", "mehr nahe Wortwiederholungen", "%",
                       "Prüfe Namen und wiederkehrende Begriffe im Kontext. Bewusste Wiederholungen können sinnvoll sein."),
    }
    for key, minimum in (("sentenceMean", 3), ("mattr", 5), ("nearRepeat", 2)):
        b, value = bands.get(key), values.get(key)
        if b and b["n"] >= (3 if comparison else 4) and value is not None:
            eligible.append(key)
            margin = max(minimum, 1.5 * (b["high"] - b["low"]))
            if not short and (value < b["low"]-margin or value > b["high"]+margin):
                label, lower, higher, unit, suggestion = descriptions[key]
                direction = "lower" if value < b["low"] else "higher"
                observation = lower if direction == "lower" else higher
                differences.append(dict(metric=key, label=label, direction=direction,
                                        title=f"Deutlich {observation}",
                                        explanation=f"{subject} hat deutlich {observation} als {reference}.",
                                        detail=f"{number(value)} {unit}; Vergleichsbereich: {number(b['low'])}–{number(b['high'])} {unit}.",
                                        suggestion=suggestion, value=value, band=b, unit=unit,
                                        reference=reference_name, referenceKind="baseline" if comparison else "chapters"))
    enough = bool(eligible)
    card("consistency", "Konsistenz", "review" if differences else "observe" if enough else "unknown",
         differences[0]["title"] if differences else "Keine deutliche Stilabweichung" if enough else "Vergleichsbasis ergänzen",
         " ".join(d["explanation"] + " " + d["detail"] for d in differences) + " Eine Stilabweichung ist kein Qualitätsurteil." if differences else
         ("Keine starke Abweichung in den vergleichbaren Kennzahlen. Eine ähnliche Schreibweise ist keine Qualitätsgarantie." if enough else
          "Mindestens drei passende Referenzausschnitte oder, ohne Baseline, vier weitere Kapitel ab 300 Wörtern werden benötigt."),
         differences[0]["metric"] if differences else eligible[0] if eligible else "mattr")
    priorities, used_groups = [], set()
    for key, title, explanation, group in PRIORITIES:
        examples = [e for e in evidence if e["metric"] == key and not e["intentional"]]
        if not examples or group in used_groups:
            continue
        if key == "longSentences" and (share is None or share <= goal):
            continue
        priorities.append(dict(metric=key, title=title, explanation=explanation, count=counts.get(key, 0),
                               openCount=counts.get(key, 0)-intentional_counts.get(key, 0),
                               evidence=examples[:3], group=group))
        used_groups.add(group)
        if len(priorities) == 3:
            break
    return dict(profile=PROFILES[q["textProfile"]], cards=cards, priorities=priorities, deviations=differences,
                consistencyReference=dict(name=reference_name, kind="baseline" if comparison else "chapters",
                                          bands={key: bands[key] for key in eligible}),
                intentional=sum(intentional_counts.values()),
                note="Einordnung nach deinen Schreibzielen und Vergleichstexten. Keine Gesamtnote; Handlung, Fakten und Urheberschaft werden damit nicht bewertet.")
