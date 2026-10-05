"""Offline, bounded-cost text diagnostics. No trained authorship or quality score."""
from __future__ import annotations

import math
import hashlib
import re
from bisect import bisect_left
from collections import Counter
from statistics import mean, pstdev

from .quality_catalog import CATALOG, GROUPS, SOURCES, VERSION

WORD = re.compile(r"[^\W\d_]+(?:[’'-][^\W\d_]+)*", re.UNICODE)
STOP = {
    "de": set("der die das den dem des ein eine einer einem einen eines und oder aber als auch an am auf aus bei bis durch für gegen im in ins mit nach ohne um über unter vom von vor zum zur zu ist sind war waren wird werden wurde wurden sein seine sich es er sie ihr ihre ich du wir ihr sie mein meine nicht noch nur so da dann denn wenn weil dass wie was wer wo schon sehr hat haben hatte hatten kann können könnte muss doch man mich mir dich dir uns euch dieser diese dieses einem einer alle mehr als".split()),
    "en": set("a an the and or but as at by for from in into of on onto to with without is are was were be been being am he she it they we you i me him her them us my your his its our their this that these those there here not no so if when while because which who what where how can could may might must will would shall should do does did have has had than then also just very only some all any each".split()),
}
LEXICONS = {
    "fillers": {"de": "eigentlich irgendwie gewissermaßen sozusagen halt eben quasi praktisch regelrecht letztendlich", "en": "actually basically essentially literally anyway anyhow somehow just really"},
    "hedges": {"de": "vielleicht möglicherweise vermutlich wahrscheinlich offenbar anscheinend scheinbar eventuell wohl womöglich", "en": "perhaps possibly probably apparently seemingly presumably maybe arguably"},
    "intensifiers": {"de": "sehr äußerst extrem völlig total absolut unglaublich wirklich besonders überaus ungemein", "en": "very extremely totally absolutely incredibly truly utterly quite deeply highly"},
    "connectors": {"de": "deshalb deswegen daher dennoch jedoch trotzdem außerdem zudem folglich während hingegen somit weil obwohl damit schließlich", "en": "therefore however moreover nevertheless nonetheless furthermore consequently whereas although because hence thus meanwhile"},
    "firstPerson": {"de": "ich mich mir mein meine meiner meinem meinen meines wir uns unser unsere unserer unserem unseren unseres", "en": "i me my mine myself we us our ours ourselves"},
    "negations": {"de": "nicht nie niemals niemand niemanden nichts kein keine keiner keinem keinen keines weder", "en": "not no never nobody nothing neither nowhere cannot can't don't doesn't didn't isn't aren't wasn't weren't won't wouldn't shouldn't couldn't"},
    "sensory": {"de": "sehen sah blick blickte glanz schimmer licht dunkel hell hören hörte klang rauschen knistern roch riechen duft geruch schmecken geschmack süß bitter salzig kalt warm rau weich berühren berührte", "en": "see saw gaze glanced glow glimmer light dark bright hear heard sound rustle whisper smell smelled scent taste sweet bitter salty cold warm rough soft touch touched"},
    "cognition": {"de": "denken dachte denkt wissen wusste weiß fühlen fühlte fühlt glauben glaubte glaubt hoffen hoffte erinnert erinnerte erinnerung angst freude trauer zweifel", "en": "think thought thinks know knew knows feel felt feels believe believed believes hope hoped remember remembered memory fear joy grief doubt"},
}
ABBREVIATIONS = set("dr prof mr mrs ms st nr bzw ca usw usw z b u a d h e g i vgl abb evtl etc vs inc jr sr jan feb mar apr jun jul aug sep sept oct okt nov dec dez".split())
STOP["de"].update("ihn ihm ihnen ihrer ihrem ihren ihres unserer unserem unseren euer eure euren dessen deren dies solche solch würde würden konnte konnten sollte sollten hatte hätte hätten ihm man ja nein auch".split())


def sentence_spans(text):
    """Keep Python character offsets into the exact input, including non-BMP text."""
    start = 0
    for match in re.finditer(r'[.!?…]+["”’“»«]*(?=\s|$)|\n[ \t]*\n', text):
        stop = match.end()
        if match.group() == ".":
            preceding = re.search(r"([^\W\d_]+)$", text[max(0, match.start() - 20):match.start()])
            if preceding and (preceding[1].lower() in ABBREVIATIONS or len(preceding[1]) == 1):
                continue
        left = start + len(text[start:stop]) - len(text[start:stop].lstrip())
        right = stop - (len(text[start:stop]) - len(text[start:stop].rstrip()))
        if WORD.search(text[left:right]):
            yield left, right
        start = stop
    left = start + len(text[start:]) - len(text[start:].lstrip())
    right = len(text.rstrip())
    if WORD.search(text[left:right]):
        yield left, right


def syllables(word, language):
    """Small deterministic estimate, deliberately not sold as pronunciation analysis."""
    word = word.lower().replace("’", "'")
    if language == "de":
        return max(1, len(re.findall(r"au|äu|eu|ei|ai|ie|[aeiouyäöü]", word)))
    groups = len(re.findall(r"[aeiouy]+", word))
    if word.endswith("e") and not re.search(r"[^aeiouy]le$", word) and groups > 1:
        groups -= 1
    return max(1, groups)


def basic_metrics(text):
    """Shared counts for every desktop view, independent of display minimums."""
    words = [w.lower().replace("’", "'") for w in WORD.findall(text)]
    lengths = [len(WORD.findall(text[a:b])) for a, b in sentence_spans(text)]
    average = mean(lengths) if lengths else 0
    quoted = sum(len(WORD.findall(next(g for g in m.groups() if g is not None))) for m in re.finditer(
        r'„([^“]+)“|“([^”]+)”|«([^»]+)»|»([^«]+)«|"([^"]+)"', text))
    return dict(words=len(words), sentences=len(lengths), sentenceMean=round(average, 4),
                sentenceVariation=round(pstdev(lengths)/average, 4) if average else 0,
                vocabulary=round(mattr(words), 4) if len(words) >= 100 else None,
                dialogue=round(min(100, 100*quoted/len(words)), 4) if words else 0,
                paragraphs=sum(bool(WORD.search(p)) for p in re.split(r"\n\s*\n", text)),
                histogram=[sum(low <= n < high for n in lengths) for low, high in
                           [(1, 6), (6, 11), (11, 16), (16, 21), (21, 31), (31, 41), (41, float("inf"))]])


def mattr(words, window=100):
    if len(words) < window:
        return None
    counts = Counter(words[:window])
    total = len(counts)
    for index in range(window, len(words)):
        previous = words[index - window]
        counts[previous] -= 1
        if not counts[previous]:
            del counts[previous]
        counts[words[index]] += 1
        total += len(counts)
    return 100 * total / (window * (len(words) - window + 1))


def hdd(counts, sample=42):
    n = sum(counts.values())
    if n < sample:
        return None
    # Group equal frequencies; avoids one hypergeometric evaluation per word type.
    value = 0.0
    for frequency, types in Counter(counts.values()).items():
        absent = 0 if n - frequency < sample else math.prod((n - frequency - j) / (n - j) for j in range(sample))
        value += types * (1 - absent)
    return 100 * value / sample


def mtld(words):
    def directional(sequence):
        factors, size, types = 0.0, 0, set()
        for word in sequence:
            size += 1
            types.add(word)
            if len(types) / size <= .72:
                factors += 1
                size, types = 0, set()
        if size:
            factors += (1 - len(types) / size) / .28
        return len(words) / factors if factors else None
    forward, backward = directional(words), directional(reversed(words))
    return (forward + backward) / 2 if forward is not None and backward is not None else None


def percentile(values, fraction):
    ordered = sorted(values)
    position = (len(values) - 1) * fraction
    left = int(position)
    return ordered[left] + (ordered[min(left + 1, len(values) - 1)] - ordered[left]) * (position - left)


def analyze(text, settings):
    from .quality_evidence import excerpt_at
    language = settings.get("language", "de")
    groups = settings.get("qualityGroups", [g["id"] for g in GROUPS])
    cutoff = settings.get("longSentenceWords", 30)
    tokens = list(WORD.finditer(text))
    words = [m.group().lower().replace("’", "'") for m in tokens]
    starts = [m.start() for m in tokens]
    n = len(words)
    counts = Counter(words)
    spans = list(sentence_spans(text))
    sentence_tokens = [(bisect_left(starts, a), bisect_left(starts, b)) for a, b in spans]
    lengths = [b - a for a, b in sentence_tokens]
    paragraphs = [(m.start(), m.end()) for m in re.finditer(r"\S[\s\S]*?(?=\n\s*\n|\Z)", text) if WORD.search(m.group())]
    paragraph_tokens = [(bisect_left(starts, a), bisect_left(starts, b)) for a, b in paragraphs]
    paragraph_lengths = [b - a for a, b in paragraph_tokens]
    values, reasons, evidence, evidence_counts = {}, {}, [], Counter()
    evidence_index = {}
    enabled = {m["id"] for m in CATALOG if m["group"] in groups}

    def evidence_at(key, a, b, label):
        if key not in enabled:
            return
        evidence_counts[key] += 1
        evidence_index.setdefault(key, []).append([a, b, label])
        if evidence_counts[key] <= 6:
            evidence.append(excerpt_at(text, key, a, b, label))

    def ratio(value, denominator=n):
        return 100 * value / denominator if denominator else None

    if n:
        word_lengths = [sum(ch.isalpha() for ch in w) for w in words]
        sentence_mean = n / max(1, len(spans))
        long_words = sum(length > 6 for length in word_lengths)
        estimated_syllables = {word: syllables(word, language) for word in counts}
        syllable_mean = sum(estimated_syllables[w] * f for w, f in counts.items()) / n
        multi = sum(f for w, f in counts.items() if estimated_syllables[w] >= 3)
        mono = sum(f for w, f in counts.items() if estimated_syllables[w] == 1)
        values.update(
            lix=sentence_mean + 100 * long_words / n, rix=long_words / max(1, len(spans)),
            fleschDe=180 - sentence_mean - 58.5 * syllable_mean,
            fleschEn=206.835 - 1.015 * sentence_mean - 84.6 * syllable_mean,
            fkGrade=.39 * sentence_mean + 11.8 * syllable_mean - 15.59,
            wiener=.1935 * 100 * multi/n + .1672 * sentence_mean + .1297 * 100 * sum(k >= 6 for k in word_lengths)/n - .0327 * 100 * mono/n - .875,
            wordLength=mean(word_lengths), longWords=ratio(long_words), mattr=mattr(words), hdd=hdd(counts), mtld=mtld(words),
            entropy=-sum((f/n) * math.log2(f/n) for f in counts.values()),
            simpson=100 * (1 - sum(f*(f-1) for f in counts.values())/(n*(n-1))) if n > 1 else None,
            yule=10000 * (sum(f*f for f in counts.values()) - n)/n**2,
            hapax=ratio(sum(f == 1 for f in counts.values()), len(counts)),
            sentenceMean=sentence_mean, sentenceCV=pstdev(lengths)/sentence_mean,
            sentenceP90=percentile(lengths, .9), longSentences=ratio(sum(k > cutoff for k in lengths), len(lengths)),
            shortSentences=ratio(sum(k <= 5 for k in lengths), len(lengths)),
            rhythmChange=mean(abs(a-b) for a, b in zip(lengths, lengths[1:]))/sentence_mean if len(lengths) > 1 else None,
            paragraphMean=mean(paragraph_lengths) if paragraph_lengths else None,
            paragraphCV=pstdev(paragraph_lengths)/mean(paragraph_lengths) if len(paragraph_lengths) >= 3 else None,
            questions=ratio(sum("?" in text[a:b] for a, b in spans), len(spans)),
            exclamations=ratio(sum("!" in text[a:b] for a, b in spans), len(spans)),
            commas=ratio(text.count(",")), commaChains=ratio(sum(text[a:b].count(",") >= 4 for a, b in spans), len(spans)),
            dashes=ratio(len(re.findall(r"[—–]|(?<!\S)-(?!\S)", text))),
            parentheses=ratio(text.count("(") + text.count("[")), ellipses=ratio(len(re.findall(r"…|\.{3,}", text))),
        )
        if len(lengths) >= 10 and pstdev(lengths[:-1]) and pstdev(lengths[1:]):
            left, right = lengths[:-1], lengths[1:]
            ml, mr = mean(left), mean(right)
            values["rhythmLag"] = mean((a-ml)*(b-mr) for a, b in zip(left, right))/(pstdev(left)*pstdev(right))
        quoted = []
        for match in re.finditer(r'„[^“]*“|“[^”]*”|«[^»]*»|»[^«]*«|"[^"]*"', text):
            quoted.append((match.start(), match.end()))
        values["dialogue"] = ratio(sum(bisect_left(starts, b)-bisect_left(starts, a) for a, b in quoted))

    stop = STOP.get(language, set())
    content_counts = Counter(w for w in words if w not in stop)
    values["topWords"] = ratio(sum(f for _, f in content_counts.most_common(10)), sum(content_counts.values()))
    last_seen, repeats = {}, 0
    for index, (word, token) in enumerate(zip(words, tokens)):
        if word not in stop:
            if index - last_seen.get(word, -100) <= 20:
                repeats += 1
                evidence_at("nearRepeat", token.start(), token.end(), "Gleiche Wortform innerhalb von 20 Wörtern")
            last_seen[word] = index
    values["nearRepeat"] = ratio(repeats, sum(content_counts.values()))

    trigrams, repeated_sentences, openings = Counter(), Counter(), Counter()
    tri_first = {}
    passive_hits = 0
    for (a, b), (ta, tb) in zip(spans, sentence_tokens):
        sw = words[ta:tb]
        if len(sw) > cutoff:
            evidence_at("longSentences", a, b, f"{len(sw)} Wörter, Grenze {cutoff}")
        if text[a:b].count(",") >= 4:
            evidence_at("commaChains", a, b, f"{text[a:b].count(',')} Kommas")
        if len(sw) >= 5:
            key = tuple(sw)
            if repeated_sentences[key]:
                evidence_at("sentenceRepeat", a, b, "Gleiche Wortfolge bereits im Text")
            repeated_sentences[key] += 1
        if len(sw) >= 2:
            key = tuple(sw[:2])
            if openings[key]:
                evidence_at("startRepeat", a, tokens[ta + 1].end(), "Wiederkehrender Satzanfang")
            openings[key] += 1
        for index in range(ta, tb - 2):
            key = tuple(words[index:index + 3])
            trigrams[key] += 1
            tri_first.setdefault(key, (tokens[index].start(), tokens[index + 2].end()))
        passive = False
        if language == "de":
            passive = bool(set(sw) & set("wird werden wurde wurden werde wirst werdet worden".split())) and any(re.fullmatch(r"ge.{2,}(?:t|en)|.{3,}iert", w) for w in sw)
        elif language == "en":
            passive = bool(set(sw) & set("be been being is are was were am".split())) and any((len(w) >= 5 and w.endswith(("ed", "en"))) or w in {"made", "built", "found", "told", "seen", "done", "said", "sent", "bought"} for w in sw)
        if passive:
            passive_hits += 1
            evidence_at("passive", a, b, "Hilfsverb + Partizipkandidat; Kontext prüfen")
    values.update(trigramRepeat=ratio(sum(f-1 for f in trigrams.values()), sum(trigrams.values())),
                  sentenceRepeat=ratio(sum(f-1 for f in repeated_sentences.values()), sum(repeated_sentences.values())),
                  startRepeat=ratio(sum(f-1 for f in openings.values()), sum(openings.values())),
                  passive=ratio(passive_hits, len(spans)))
    repeated_phrases = [(key, count) for key, count in trigrams.most_common() if count >= 2]
    for key, count in repeated_phrases:
        evidence_at("trigramRepeat", *tri_first[key], f"{count} Vorkommen dieser Dreierphrase")
    # Report the full number of distinct repeated phrases, not the capped sample.
    if "trigramRepeat" in enabled:
        evidence_counts["trigramRepeat"] = sum(count >= 2 for count in trigrams.values())

    duplicate_paragraphs, overlaps = Counter(), []
    previous = None
    for (a, b), (ta, tb) in zip(paragraphs, paragraph_tokens):
        pw = words[ta:tb]
        current = set(pw) - stop if len(pw) >= 12 else set()
        if len(pw) >= 12:
            key = tuple(pw)
            if duplicate_paragraphs[key]:
                evidence_at("paragraphRepeat", a, b, "Identischer Absatz (ohne Interpunktion)")
            duplicate_paragraphs[key] += 1
        if previous and current:
            overlap = len(previous & current) / len(previous | current)
            overlaps.append(overlap)
            if overlap < .05:
                evidence_at("shifts", a, b, "Wenig gemeinsame Wörter mit dem vorigen Absatz")
        previous = current
    values.update(paragraphRepeat=ratio(sum(f-1 for f in duplicate_paragraphs.values()), sum(duplicate_paragraphs.values())),
                  cohesion=100 * mean(overlaps) if overlaps else None,
                  shifts=ratio(sum(v < .05 for v in overlaps), len(overlaps)))

    for key, lists in LEXICONS.items():
        vocabulary = set(lists.get(language, "").split())
        hits = 0
        for word, token in zip(words, tokens):
            if word in vocabulary:
                hits += 1
                evidence_at(key, token.start(), token.end(), "Treffer der dokumentierten Wortliste")
        values[key] = ratio(hits)
    for key in ("nominal", "adverbs"):
        hits = 0
        for word, token in zip(words, tokens):
            candidate = (len(word) >= 6 and bool(re.search(r"(?:ung|heit|keit|ismus|ität|schaft)(?:en|e|s)?$" if language == "de" else r"(?:tion|sion|ment|ness|ity|ism)s?$", word))) if key == "nominal" else (len(word) >= 5 and word.endswith("weise" if language == "de" else "ly"))
            if candidate:
                hits += 1
                evidence_at(key, token.start(), token.end(), "Wortendungskandidat; keine Wortartenanalyse")
        values[key] = ratio(hits)

    for spec in CATALOG:
        key = spec["id"]
        value = values.get(key)
        reason = None
        if spec["group"] not in groups:
            reason = "Dieser Analysebereich ist für den Upload deaktiviert."
        elif language not in spec["languages"]:
            reason = "Für die eingestellte Sprache nicht verfügbar."
        elif n < spec["minWords"]:
            reason = f"Mindestens {spec['minWords']} Wörter erforderlich; vorhanden: {n}."
        elif value is None or not math.isfinite(value):
            reason = {"rhythmLag": "Mindestens 10 Sätze mit variierenden Längen erforderlich.",
                      "paragraphCV": "Mindestens 3 Absätze erforderlich.",
                      "cohesion": "Benachbarte Absätze mit jeweils mindestens 12 Wörtern und Nicht-Stoppwörtern erforderlich.",
                      "shifts": "Benachbarte Absätze mit jeweils mindestens 12 Wörtern und Nicht-Stoppwörtern erforderlich.",
                      "mtld": "Kein endlicher Faktor ermittelbar (z.B. ausschließlich unterschiedliche Wörter)."}.get(key, "Zu wenige passende Texteinheiten.")
        values[key] = None if reason else round(value, 4)
        if reason:
            reasons[key] = reason
    # Full-text counts are exact; chart bins alone aggregate long sentence sequences.
    cadence = []
    step = max(1, math.ceil(len(lengths)/160))
    for index in range(0, len(lengths), step):
        chunk = lengths[index:index+step]
        cadence.append(dict(first=index+1, last=index+len(chunk), mean=round(mean(chunk), 2), low=min(chunk), high=max(chunk), start=spans[index][0], end=spans[index+len(chunk)-1][1]))
    return dict(version=VERSION, textSha256=hashlib.sha256(text.encode("utf-8")).hexdigest(), language=language, groups=groups, longSentenceWords=cutoff,
                textProfile=settings.get("textProfile", "narrative"), longSentenceShare=settings.get("longSentenceShare", 10),
                words=n, sentences=len(spans), paragraphs=len(paragraphs), values=values, reasons=reasons,
                evidence=[e for e in evidence if e["metric"] not in reasons],
                evidenceIndex={k: v for k, v in evidence_index.items() if k not in reasons},
                evidenceCounts={k: v for k, v in evidence_counts.items() if k not in reasons}, cadence=cadence if "rhythm" in groups else [],
                keywords=[dict(word=w, count=f) for w, f in content_counts.most_common(20)] if "vocabulary" in groups and language in STOP else [],
                phrases=[dict(text=" ".join(k), count=f) for k, f in repeated_phrases[:16]] if "repetition" in groups else [])


def catalog():
    return dict(version=VERSION, groups=GROUPS, metrics=CATALOG, sources=SOURCES,
                lexicons=LEXICONS, stopwords={language: sorted(words) for language, words in STOP.items()},
                note="Deskriptive Messwerte und prüfbare Hinweise. Keine Qualitätsnote, keine kalibrierte KI- oder Mensch-Wahrscheinlichkeit. Sprache und Genre berücksichtigen; höhere Werte bedeuten nicht generell bessere Texte.")


def deltas(target, reference):
    values, reasons = {}, {}
    for spec in CATALOG:
        key = spec["id"]
        a, b = target["values"][key], reference["values"][key]
        reason = target["reasons"].get(key) or reference["reasons"].get(key)
        if target["version"] != reference["version"]:
            reason = "Unterschiedliche Methodenversionen."
        elif target["language"] != reference["language"]:
            reason = "Unterschiedliche Textsprachen: kein automatisches Qualitätsdelta."
        elif key == "longSentences" and target["longSentenceWords"] != reference["longSentenceWords"]:
            reason = "Unterschiedliche Wortgrenzen für lange Sätze."
        values[key] = round(a-b, 4) if a is not None and b is not None and not reason else None
        if reason:
            reasons[key] = reason
    return dict(values=values, reasons=reasons)
