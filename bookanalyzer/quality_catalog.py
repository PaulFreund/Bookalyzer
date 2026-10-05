"""Versioned, inspectable definitions for the offline quality laboratory."""
VERSION = "2.1.0"
GROUPS = [
    {"id": "readability", "label": "Lesbarkeit"},
    {"id": "vocabulary", "label": "Wortschatz"},
    {"id": "rhythm", "label": "Rhythmus"},
    {"id": "repetition", "label": "Wiederholungen"},
    {"id": "cohesion", "label": "Zusammenhang"},
    {"id": "style", "label": "Stilhinweise"},
]
SOURCES = [
    {"id": "readability", "label": "quanteda · Lesbarkeitsformeln und Literatur", "url": "https://quanteda.io/reference/textstat_readability.html"},
    {"id": "lexical", "label": "quanteda · Lexikalische Vielfalt und Literatur", "url": "https://quanteda.io/reference/textstat_lexdiv.html"},
    {"id": "hdd", "label": "McCarthy & Jarvis (2010) · MTLD, vocd-D und HD-D", "url": "https://doi.org/10.3758/BRM.42.2.381"},
    {"id": "lix", "label": "LIX · Definition des Lesbarkeitsindex", "url": "https://www.lix.se/"},
    {"id": "flesch", "label": "textstat · Sprachvarianten der Flesch-Formel", "url": "https://github.com/textstat/textstat"},
]


def metric(id, label, group, unit, formula, note, *, languages=None, min_words=100, source=None, kind="descriptive"):
    ranges = {"Index": [0, 100], "%": [0, 100], "Wörter": [0, 60], "Bit": [0, 16],
              "Buchstaben": [0, 12], "CV": [0, 2], "r": [-1, 1], "relativ": [0, 2], "/100 W.": [0, 10]}
    display_range = {"mtld": [0, 250], "yule": [0, 1000], "paragraphMean": [0, 300],
                     "fleschDe": [-50, 120], "fleschEn": [-50, 120], "wiener": [0, 20],
                     "fkGrade": [0, 20], "rix": [0, 20]}.get(id, ranges.get(unit, [0, 100]))
    return dict(id=id, label=label, group=group, unit=unit, formula=formula, note=note,
                languages=languages or ["de", "en", "und"], minWords=min_words, source=source, kind=kind,
                displayRange=display_range)


CATALOG = [
    metric("lix", "LIX", "readability", "Index", "Wörter/Sätze + 100 × Wörter mit >6 Buchstaben/Wörter", "Höher bedeutet formal komplexer. Keine Bewertung von Handlung oder Verständlichkeit im Kontext.", source="lix", kind="index"),
    metric("rix", "RIX", "readability", "Index", "Wörter mit >6 Buchstaben / Sätze", "Wort- und Satzlängenmaß; sprach- und genreabhängig.", source="readability", kind="index"),
    metric("fleschDe", "Flesch–Amstad ≈", "readability", "Index", "180 − Wörter/Sätze − 58,5 × Silben/Wörter", "Deutsch. Höher bedeutet formal leichter. Silben werden über Vokalgruppen geschätzt; kein Schulstufenurteil, Werte nicht auf 0–100 beschnitten.", languages=["de"], source="flesch", kind="estimate"),
    metric("fleschEn", "Flesch Reading Ease ≈", "readability", "Index", "206,835 − 1,015 × Wörter/Sätze − 84,6 × Silben/Wörter", "Englisch; höhere Werte bedeuten formal leichter. Vokalgruppen statt Aussprachelexikon, deshalb nur Näherung.", languages=["en"], source="readability", kind="estimate"),
    metric("fkGrade", "Flesch–Kincaid ≈", "readability", "Index", "0,39 × Wörter/Sätze + 11,8 × Silben/Wörter − 15,59", "Für englische Sachtexte entwickelt. Geschätzte Silben; keine Empfehlung eines Lesealters.", languages=["en"], source="readability", kind="estimate"),
    metric("wiener", "Wiener Sachtextformel 1 ≈", "readability", "Index", "0,1935 × MS + 0,1672 × SL + 0,1297 × IW − 0,0327 × ES − 0,875", "MS: % Wörter ≥3 Silben, SL: Ø Satzlänge, IW: % Wörter ≥6 Buchstaben, ES: % Einsilber. Silben geschätzt; Übertragung auf Belletristik explorativ.", languages=["de"], source="readability", kind="estimate"),
    metric("wordLength", "Mittlere Wortlänge", "readability", "Buchstaben", "Buchstaben / Wörter", "Bindestriche und Apostrophe zählen nicht als Buchstaben."),
    metric("longWords", "Lange Wörter", "readability", "%", "100 × Wörter mit >6 Buchstaben / Wörter", "Deutsche Komposita erhöhen den Wert; nicht automatisch schwer verständlich."),
    metric("mattr", "MATTR · 100 Wörter", "vocabulary", "%", "Mittlere Type-Token-Ratio aller gleitenden 100-Wort-Fenster × 100", "Schrittweite 1, feste Fenstergröße, keine Lemmatisierung. Textprofil und Qualitätsansicht verwenden dieselbe Berechnung.", source="lexical", kind="index"),
    metric("hdd", "HD-D · 42 Wörter", "vocabulary", "%", "100/42 × Σ[1 − C(N−Häufigkeit,42)/C(N,42)]", "Erwartete Vielfalt einer Stichprobe ohne Zurücklegen. Feste Stichprobengröße 42; Formen werden kleingeschrieben, nicht lemmatisiert.", min_words=42, source="hdd", kind="index"),
    metric("mtld", "MTLD · 0,72", "vocabulary", "Wörter", "Mittlere Faktor-Länge bis TTR ≤0,72, vorwärts und rückwärts; Restfaktor (1−TTR)/0,28", "Höher: Wiederholungen senken TTR erst später. Bei ausschließlich neuen Wörtern nicht bestimmbar; kurze Texte bleiben instabil.", source="hdd", kind="index"),
    metric("entropy", "Wortentropie", "vocabulary", "Bit", "−Σ p(Wort) × log₂ p(Wort)", "Beschreibt die Häufigkeitsverteilung. Längenabhängig, keine Modell-Perplexität und kein KI-Nachweis."),
    metric("simpson", "Simpson-Vielfalt", "vocabulary", "%", "100 × [1 − Σ f(f−1)/(N(N−1))]", "Wahrscheinlichkeit zweier verschiedener Wortformen bei Ziehung ohne Zurücklegen.", source="lexical", kind="index"),
    metric("yule", "Yule's K", "vocabulary", "Index", "10.000 × (Σ f² − N)/N²", "Höhere Werte zeigen stärkere lexikalische Konzentration.", source="lexical", kind="index"),
    metric("hapax", "Einmalige Wortformen", "vocabulary", "%", "100 × nur einmal vorkommende Wortformen / alle Wortformen", "Anteil am Wortschatz (Types), nicht an allen Tokens. Stark längenabhängig."),
    metric("topWords", "Top-10-Wortkonzentration", "vocabulary", "%", "100 × Häufigkeit der zehn häufigsten Nicht-Stoppwörter / Nicht-Stoppwörter", "Kurze offen dokumentierte DE/EN-Stoppwortlisten. Figuren- und Ortsnamen bleiben enthalten.", languages=["de", "en"], kind="heuristic"),
    metric("sentenceMean", "Mittlere Satzlänge", "rhythm", "Wörter", "Wörter / erkannte Sätze", "Regelbasiert, mit häufigen DE/EN-Abkürzungen. Titel und ungewöhnliche Zeichensetzung können Satzgrenzen beeinflussen."),
    metric("sentenceCV", "Satzlängenvariation", "rhythm", "CV", "Populationsstandardabweichung / mittlere Satzlänge", "Beschreibt Kontraste im Rhythmus. Hohe Variation ist kein Beweis menschlicher Urheberschaft."),
    metric("sentenceP90", "90%-Satzlänge", "rhythm", "Wörter", "90. Perzentil, linear interpoliert", "90 Prozent der erkannten Sätze sind höchstens so lang."),
    metric("longSentences", "Lange Sätze", "rhythm", "%", "100 × Sätze über dem eingestellten Wortlimit / Sätze", "Standardgrenze 30 Wörter, je Upload einstellbar. Ein langer Satz kann stilistisch sinnvoll sein.", kind="heuristic"),
    metric("shortSentences", "Kurze Sätze", "rhythm", "%", "100 × Sätze mit höchstens 5 Wörtern / Sätze", "Beschreibt kurze Einheiten, keine Grammatikprüfung."),
    metric("rhythmChange", "Rhythmuswechsel", "rhythm", "relativ", "Mittlere absolute Differenz benachbarter Satzlängen / Ø Satzlänge", "Hoch bei abrupten Längenwechseln; niedrig bei ähnlich langen Nachbarsätzen."),
    metric("rhythmLag", "Rhythmus-Autokorrelation", "rhythm", "r", "Pearson-Korrelation benachbarter Satzlängen (Lag 1)", "Mindestens 10 Sätze und Varianz in beiden Reihen. Positiv: ähnliche Längen folgen aufeinander; negativ: Wechsel."),
    metric("paragraphMean", "Mittlere Absatzlänge", "rhythm", "Wörter", "Wörter / Absätze mit Wörtern", "Absätze anhand von Leerzeilen. Layoutfehler beim Import können den Wert verändern."),
    metric("paragraphCV", "Absatzlängenvariation", "rhythm", "CV", "Standardabweichung / Mittelwert der Absatzlängen", "Mindestens 3 Absätze. Beschreibt Abwechslung in der Textstruktur."),
    metric("trigramRepeat", "Wiederholte Dreierphrasen", "repetition", "%", "100 × zusätzliche Vorkommen identischer Wort-Trigramme / alle Trigramme", "Nur innerhalb eines Satzes; inklusive Funktionswörtern. Häufige Formulierungen sind nicht automatisch Klischees."),
    metric("sentenceRepeat", "Wiederholte Sätze", "repetition", "%", "100 × zusätzliche identische Sätze / Sätze mit ≥5 Wörtern", "Kleingeschriebene Wortfolge ohne Interpunktion; keine semantischen Paraphrasen."),
    metric("startRepeat", "Wiederkehrende Satzanfänge", "repetition", "%", "100 × zusätzliche gleiche erste zwei Wörter / Sätze mit ≥2 Wörtern", "Anaphern und Dialogrhythmus können bewusst wiederholt sein."),
    metric("nearRepeat", "Nahe Wortwiederholungen", "repetition", "%", "100 × Nicht-Stoppwörter mit gleichem Wort in den vorherigen 20 Tokens / Nicht-Stoppwörter", "Lokal wiederholte Wortformen, keine Lemmatisierung. Namen zählen mit.", languages=["de", "en"], kind="heuristic"),
    metric("paragraphRepeat", "Doppelte Absätze", "repetition", "%", "100 × zusätzliche identische Absätze / Absätze mit ≥12 Wörtern", "Identität der kleingeschriebenen Wortfolge; nur Absätze ab 12 Wörtern."),
    metric("cohesion", "Lexikalischer Anschluss", "cohesion", "%", "100 × mittlerer Jaccard-Überlapp benachbarter Absatz-Wortmengen ohne Stoppwörter", "Mindestens zwei benachbarte Absätze mit jeweils ≥12 Wörtern. Misst Wortanschluss, kein inhaltliches Verständnis.", languages=["de", "en"], kind="heuristic"),
    metric("shifts", "Geringer Wortanschluss", "cohesion", "%", "100 × gültige Absatzpaare mit Jaccard <0,05 / gültige Absatzpaare", "Hinweise auf Übergänge; Szenenwechsel und Synonyme führen ebenfalls zu niedrigen Werten.", languages=["de", "en"], kind="heuristic"),
    metric("connectors", "Verknüpfungswörter", "cohesion", "/100 W.", "Treffer einer offenen DE/EN-Konnektorenliste je 100 Wörter", "Lexikalische Signale wie deshalb/however; keine Prüfung logischer Gültigkeit.", languages=["de", "en"], kind="heuristic"),
    metric("firstPerson", "Ich-/Wir-Marker", "cohesion", "/100 W.", "DE/EN-Pronomen der ersten Person je 100 Wörter", "Dialog und Erzählstimme werden gemeinsam gezählt; kein verlässlicher Perspektivwechsel-Detektor.", languages=["de", "en"], kind="heuristic"),
    metric("dialogue", "Zitierter Text", "style", "%", "Wörter innerhalb paariger Anführungszeichen / Wörter × 100", "Erkennt „…“, “…” (auch deutsche Innenzitate), «…», »…« und gerade Doppelzeichen. Zitate sind nicht immer Dialog; ungeschlossene Paare werden ignoriert.", kind="heuristic"),
    metric("questions", "Fragesätze", "style", "%", "100 × Satzeinheiten mit Fragezeichen / Sätze", "Einfache Interpunktionszählung, auch innerhalb von Zitaten."),
    metric("exclamations", "Ausrufesätze", "style", "%", "100 × Satzeinheiten mit Ausrufezeichen / Sätze", "Kein Maß für emotionale Intensität."),
    metric("commas", "Kommas", "style", "/100 W.", "Kommas je 100 Wörter", "Beschreibt Interpunktion; Aufzählungen erhöhen den Wert."),
    metric("commaChains", "Kommaketten", "style", "%", "100 × Sätze mit ≥4 Kommas / Sätze", "Kandidat für dichte Satzstruktur, keine syntaktische Analyse.", kind="heuristic"),
    metric("dashes", "Gedankenstriche", "style", "/100 W.", "Halbgeviert-/Geviertstriche und freistehende Bindestriche je 100 Wörter", "Kann Unterbrechungen, Dialog oder Aufzählungen markieren."),
    metric("parentheses", "Klammeröffnungen", "style", "/100 W.", "Anzahl ( und [ je 100 Wörter", "Formales Signal für Einschübe, kein Test auf korrekte Klammerung."),
    metric("ellipses", "Auslassungspunkte", "style", "/100 W.", "… oder mindestens drei Punkte je 100 Wörter", "Beschreibt Zögern, Auslassung oder typografische Gewohnheiten."),
    metric("fillers", "Füllwortkandidaten", "style", "/100 W.", "Treffer der kuratierten DE/EN-Liste je 100 Wörter", "z.B. eigentlich/irgendwie bzw. basically/actually. Kontext kann sie sinnvoll machen; kein Streichvorschlag ohne Lesen.", languages=["de", "en"], kind="heuristic"),
    metric("hedges", "Abschwächungen", "style", "/100 W.", "Treffer der DE/EN-Liste für Unsicherheit je 100 Wörter", "z.B. vielleicht/possibly. Kann präzise Unsicherheit oder die Figurenstimme ausdrücken.", languages=["de", "en"], kind="heuristic"),
    metric("intensifiers", "Verstärker", "style", "/100 W.", "Treffer der DE/EN-Verstärkerliste je 100 Wörter", "z.B. sehr/extremely. Beschreibt eine Stilentscheidung.", languages=["de", "en"], kind="heuristic"),
    metric("nominal", "Abstrakte Wortendungen", "style", "/100 W.", "DE: -ung/-heit/-keit/-ismus/-ität/-schaft; EN: -tion/-sion/-ment/-ness/-ity/-ism", "Wortformen ab 6 Buchstaben. Suffixkandidaten mit Flexionsvarianten; keine Wortarten- oder Nominalstilklassifikation.", languages=["de", "en"], kind="heuristic"),
    metric("adverbs", "Adverb-Endungskandidaten", "style", "/100 W.", "DE: -weise; EN: -ly, Wortlänge ≥5", "Grobe Wortformheuristik, die auch Nicht-Adverbien treffen und viele Adverbien übersehen kann.", languages=["de", "en"], kind="heuristic"),
    metric("passive", "Passivkandidaten", "style", "%", "Satzanteil mit werden/be-Hilfsverb und Partizipkandidat im selben Satz", "DE: ge…t/en oder …iert; EN: …ed/en plus kleine Ausnahmeliste. Keine Syntaxprüfung: Kopula, Futur und Adjektive können Fehlalarme erzeugen.", languages=["de", "en"], kind="heuristic"),
    metric("negations", "Verneinungsmarker", "style", "/100 W.", "DE/EN-Negationsliste je 100 Wörter", "Keine Auflösung von Skopus, Ironie oder doppelter Verneinung.", languages=["de", "en"], kind="heuristic"),
    metric("sensory", "Sinneswort-Marker", "style", "/100 W.", "Treffer der kleinen DE/EN-Sinneswortliste je 100 Wörter", "Nur lexikalische Hinweise auf Sehen/Hören/Geruch/Berührung. Keine Show-don’t-tell-Bewertung.", languages=["de", "en"], kind="heuristic"),
    metric("cognition", "Denk-/Gefühlsmarker", "style", "/100 W.", "Treffer der kleinen DE/EN-Liste für Denken und Fühlen je 100 Wörter", "Keine Sentimentanalyse, keine Aussage über die Qualität von Innenperspektiven.", languages=["de", "en"], kind="heuristic"),
]
