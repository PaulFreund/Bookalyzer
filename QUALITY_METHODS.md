# Lokale Qualitätsmethoden

Methodenversion 2.1.0 · 51 Kennzahlen · unabhängig von StoryScope.

Alle Werte sind deskriptiv. Es gibt weder einen kalibrierten KI-Detektor noch eine literarische Gesamtnote. Silben werden geschätzt; Wortlisten sind kleine offene Heuristiken. Keine Grammatik- oder Faktenprüfung.

Gesamttexte und Kapitel verwenden die ursprünglichen eingeschlossenen Abschnittstexte. Absatzgrenzen bleiben erhalten; eine andere Segmentgröße verändert die Gesamtanalyse nicht. Satzlänge, Streuung, Redeanteil und gleitende Wortvielfalt werden im Textprofil und in der Qualitätsansicht gleich berechnet. Nicht lemmatisierte, kleingeschriebene Wortformen; Zahlen zählen nicht als Wörter. Mindestlängen sind vorsichtige Anzeigegrenzen, keine statistische Validierung. Alte Baselines ohne gespeicherte Originalstruktur werden kenntlich gemacht; Absatzdeltas bleiben dort leer.

Vergleiche: gleiche Sprache und Methodenversion. Die Grenze für lange Sätze muss für dieses Delta übereinstimmen. Prozentdeltas sind Prozentpunkte. Alte Baselines bleiben unverändert; aktuelle lokale Auswertungen werden getrennt gecacht.

## Einordnung auf einen Blick

Vier Karten zeigen Lesefluss, Wortwahl, Wiederholungen und Konsistenz. Es gibt keine Gesamtpunktzahl. Die Vorgaben sind editierbare Schreibziele, keine validierten Qualitätsnormen:

| Profil | Langer Satz | Ziel: maximaler Anteil langer Sätze |
| --- | --- | --- |
| Erzähltext (Standard) | mehr als 30 Wörter | 10 % |
| Sachtext | mehr als 25 Wörter | 5 % |
| Fachtext | mehr als 35 Wörter | 15 % |

Grün bedeutet ausschließlich: das gewählte Längenziel wird eingehalten. Orange empfiehlt eine Prüfung, Blau bezeichnet eine Beobachtung und Grau eine unzureichende Grundlage. Unter 300 Wörtern bleibt die Einordnung grau; einzelne Messwerte können ab ihrer jeweiligen Mindestlänge erscheinen. Weniger lange Sätze oder mehr Wortvielfalt machen einen Text nicht automatisch besser.

Bis zu drei nächste Schritte stammen aus verschiedenen Bereichen (Wiederholung, Lesefluss, Wortwahl). Die feste Reihenfolge berücksichtigt doppelte Absätze, doppelte Sätze, eine Überschreitung des Satzlängenziels, Kommaketten, nahe Wortwiederholungen und Füllwortkandidaten. Alle Fundstellen werden mit ihren Positionen erfasst. Der Überblick zeigt bis zu drei offene Beispiele pro Schwerpunkt; nach einer Markierung als beabsichtigt rücken weitere offene Stellen nach. Angezeigt werden offene und gesamte Trefferzahl. Unter Details lassen sich sämtliche Fundstellen durchblättern und nach Regel sowie Bearbeitungsstatus filtern. Dort können auch später markierte Fundstellen wieder aktiviert werden. Die Messwerte bleiben unverändert. Entscheidungen gelten für den Text-Hash und den jeweiligen Gesamttext bzw. das jeweilige Kapitel und bleiben nach einem Neustart erhalten. Die Bibliothek speichert ein kompaktes Positionsverzeichnis; Textausschnitte werden seitenweise geladen.

## Baselines, Streuung und Kapitel

Für einen Zieltext mit N Wörtern werden bis zu neun nicht überlappende Ausschnitte mit genau N Wörtern aus der Baseline ausgewählt. Ihre Startpositionen sind gleichmäßig über den verfügbaren Text verteilt; bei nur einem Ausschnitt wird die Mitte verwendet. Wörter werden nicht zufällig gezogen. Satz- oder Absatzränder können angeschnitten werden. Der Median liefert den Vergleichswert. Das Quartilband zeigt die mittleren 50 % ab drei verfügbaren Ausschnitten; es ist kein Konfidenzintervall und keine Fehlerwahrscheinlichkeit.

Ist die Baseline kürzer, entfallen Deltas für Entropie, Hapaxanteil, häufigste Wortformen sowie Phrasen-, Satz-, Absatz- und Satzanfangswiederholungen. Die übrigen Messwerte bleiben beschreibend vergleichbar, ohne Streuungsband. Für alte Textgrundlagen ohne Originalabsätze entfallen außerdem Absatzlänge, Absatzstreuung, Absatzwiederholungen, Absatzanschluss und geringe Überlappung. Sprache, Methodenversion und aktivierte Bereiche werden zusätzlich geprüft. Neue Baselines frieren Originaltext und Absatzstruktur mit Hashes ein.

Konsistenz prüft mittlere Satzlänge, MATTR-100 und nahe Wortwiederholungen. Gegen eine Baseline werden mindestens drei passende Ausschnitte benötigt. Ohne Baseline dienen mindestens vier weitere Kapitel mit je mindestens 300 Wörtern als Vergleich; das aktuelle Kapitel gehört nicht zur Referenz. Ein Hinweis erscheint erst außerhalb des Quartilbands zuzüglich 1,5 Bandbreiten, mindestens jedoch 3 Wörter Satzlänge, 5 Prozentpunkte Wortvielfalt bzw. 2 Prozentpunkte Wiederholungen. Diese Regeln sind heuristische Suchhilfen für Stilwechsel, keine wissenschaftlich validierte Qualitätsklassifikation.

Jede starke Abweichung nennt die betroffene Kennzahl und Richtung, zum Beispiel „deutlich längere Sätze“. Die Erklärung zeigt Messwert, Einheit, Vergleichsbereich, Herkunft und Anzahl der Vergleichsausschnitte bzw. anderen Kapitel. Ein Diagramm stellt den Text dem Referenzmedian und dem Quartilband gegenüber. Für jede Abweichung gibt es einen konkreten Lesehinweis. Diese Erklärungen und Diagramme erscheinen auch im Kurzbericht. Fehlende Wortvielfaltsdaten unterdrücken keinen gültigen Satzlängenvergleich; kurze Texte erhalten keine starke Stileinordnung.

Die Merkmalsmatrix verwendet feste, im Katalog veröffentlichte Anzeigebereiche pro Kennzahl. Auswahlwechsel ändern die Farbe nicht. Bei Deltas stehen Blau und Violett für entgegengesetzte Richtungen, Null bleibt neutral. Werte außerhalb eines Anzeigebereichs bleiben als Zahlen erhalten; die Farbe sättigt am Rand. Balkenachsen erweitern sich bei Bedarf, ohne Werte abzuschneiden.

## Lesbarkeit

### LIX (Index)

**Formel:** Wörter/Sätze + 100 × Wörter mit >6 Buchstaben/Wörter

Höher bedeutet formal komplexer. Keine Bewertung von Handlung oder Verständlichkeit im Kontext.

Typ: index. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### RIX (Index)

**Formel:** Wörter mit >6 Buchstaben / Sätze

Wort- und Satzlängenmaß; sprach- und genreabhängig.

Typ: index. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Flesch–Amstad ≈ (Index)

**Formel:** 180 − Wörter/Sätze − 58,5 × Silben/Wörter

Deutsch. Höher bedeutet formal leichter. Silben werden über Vokalgruppen geschätzt; kein Schulstufenurteil, Werte nicht auf 0–100 beschnitten.

Typ: estimate. Sprache: de. Mindestlänge: 100 Wörter.

### Flesch Reading Ease ≈ (Index)

**Formel:** 206,835 − 1,015 × Wörter/Sätze − 84,6 × Silben/Wörter

Englisch; höhere Werte bedeuten formal leichter. Vokalgruppen statt Aussprachelexikon, deshalb nur Näherung.

Typ: estimate. Sprache: en. Mindestlänge: 100 Wörter.

### Flesch–Kincaid ≈ (Index)

**Formel:** 0,39 × Wörter/Sätze + 11,8 × Silben/Wörter − 15,59

Für englische Sachtexte entwickelt. Geschätzte Silben; keine Empfehlung eines Lesealters.

Typ: estimate. Sprache: en. Mindestlänge: 100 Wörter.

### Wiener Sachtextformel 1 ≈ (Index)

**Formel:** 0,1935 × MS + 0,1672 × SL + 0,1297 × IW − 0,0327 × ES − 0,875

MS: % Wörter ≥3 Silben, SL: Ø Satzlänge, IW: % Wörter ≥6 Buchstaben, ES: % Einsilber. Silben geschätzt; Übertragung auf Belletristik explorativ.

Typ: estimate. Sprache: de. Mindestlänge: 100 Wörter.

### Mittlere Wortlänge (Buchstaben)

**Formel:** Buchstaben / Wörter

Bindestriche und Apostrophe zählen nicht als Buchstaben.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Lange Wörter (%)

**Formel:** 100 × Wörter mit >6 Buchstaben / Wörter

Deutsche Komposita erhöhen den Wert; nicht automatisch schwer verständlich.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.


## Wortschatz

### MATTR · 100 Wörter (%)

**Formel:** Mittlere Type-Token-Ratio aller gleitenden 100-Wort-Fenster × 100

Schrittweite 1, feste Fenstergröße, keine Lemmatisierung. Textprofil und Qualitätsansicht verwenden dieselbe Berechnung.

Typ: index. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### HD-D · 42 Wörter (%)

**Formel:** 100/42 × Σ[1 − C(N−Häufigkeit,42)/C(N,42)]

Erwartete Vielfalt einer Stichprobe ohne Zurücklegen. Feste Stichprobengröße 42; Formen werden kleingeschrieben, nicht lemmatisiert.

Typ: index. Sprache: de, en, und. Mindestlänge: 42 Wörter.

### MTLD · 0,72 (Wörter)

**Formel:** Mittlere Faktor-Länge bis TTR ≤0,72, vorwärts und rückwärts; Restfaktor (1−TTR)/0,28

Höher: Wiederholungen senken TTR erst später. Bei ausschließlich neuen Wörtern nicht bestimmbar; kurze Texte bleiben instabil.

Typ: index. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Wortentropie (Bit)

**Formel:** −Σ p(Wort) × log₂ p(Wort)

Beschreibt die Häufigkeitsverteilung. Längenabhängig, keine Modell-Perplexität und kein KI-Nachweis.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Simpson-Vielfalt (%)

**Formel:** 100 × [1 − Σ f(f−1)/(N(N−1))]

Wahrscheinlichkeit zweier verschiedener Wortformen bei Ziehung ohne Zurücklegen.

Typ: index. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Yule's K (Index)

**Formel:** 10.000 × (Σ f² − N)/N²

Höhere Werte zeigen stärkere lexikalische Konzentration.

Typ: index. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Einmalige Wortformen (%)

**Formel:** 100 × nur einmal vorkommende Wortformen / alle Wortformen

Anteil am Wortschatz (Types), nicht an allen Tokens. Stark längenabhängig.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Top-10-Wortkonzentration (%)

**Formel:** 100 × Häufigkeit der zehn häufigsten Nicht-Stoppwörter / Nicht-Stoppwörter

Kurze offen dokumentierte DE/EN-Stoppwortlisten. Figuren- und Ortsnamen bleiben enthalten.

Typ: heuristic. Sprache: de, en. Mindestlänge: 100 Wörter.


## Rhythmus

### Mittlere Satzlänge (Wörter)

**Formel:** Wörter / erkannte Sätze

Regelbasiert, mit häufigen DE/EN-Abkürzungen. Titel und ungewöhnliche Zeichensetzung können Satzgrenzen beeinflussen.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Satzlängenvariation (CV)

**Formel:** Populationsstandardabweichung / mittlere Satzlänge

Beschreibt Kontraste im Rhythmus. Hohe Variation ist kein Beweis menschlicher Urheberschaft.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### 90%-Satzlänge (Wörter)

**Formel:** 90. Perzentil, linear interpoliert

90 Prozent der erkannten Sätze sind höchstens so lang.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Lange Sätze (%)

**Formel:** 100 × Sätze über dem eingestellten Wortlimit / Sätze

Standardgrenze 30 Wörter, je Upload einstellbar. Ein langer Satz kann stilistisch sinnvoll sein.

Typ: heuristic. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Kurze Sätze (%)

**Formel:** 100 × Sätze mit höchstens 5 Wörtern / Sätze

Beschreibt kurze Einheiten, keine Grammatikprüfung.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Rhythmuswechsel (relativ)

**Formel:** Mittlere absolute Differenz benachbarter Satzlängen / Ø Satzlänge

Hoch bei abrupten Längenwechseln; niedrig bei ähnlich langen Nachbarsätzen.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Rhythmus-Autokorrelation (r)

**Formel:** Pearson-Korrelation benachbarter Satzlängen (Lag 1)

Mindestens 10 Sätze und Varianz in beiden Reihen. Positiv: ähnliche Längen folgen aufeinander; negativ: Wechsel.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Mittlere Absatzlänge (Wörter)

**Formel:** Wörter / Absätze mit Wörtern

Absätze anhand von Leerzeilen. Layoutfehler beim Import können den Wert verändern.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Absatzlängenvariation (CV)

**Formel:** Standardabweichung / Mittelwert der Absatzlängen

Mindestens 3 Absätze. Beschreibt Abwechslung in der Textstruktur.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.


## Wiederholungen

### Wiederholte Dreierphrasen (%)

**Formel:** 100 × zusätzliche Vorkommen identischer Wort-Trigramme / alle Trigramme

Nur innerhalb eines Satzes; inklusive Funktionswörtern. Häufige Formulierungen sind nicht automatisch Klischees.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Wiederholte Sätze (%)

**Formel:** 100 × zusätzliche identische Sätze / Sätze mit ≥5 Wörtern

Kleingeschriebene Wortfolge ohne Interpunktion; keine semantischen Paraphrasen.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Wiederkehrende Satzanfänge (%)

**Formel:** 100 × zusätzliche gleiche erste zwei Wörter / Sätze mit ≥2 Wörtern

Anaphern und Dialogrhythmus können bewusst wiederholt sein.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Nahe Wortwiederholungen (%)

**Formel:** 100 × Nicht-Stoppwörter mit gleichem Wort in den vorherigen 20 Tokens / Nicht-Stoppwörter

Lokal wiederholte Wortformen, keine Lemmatisierung. Namen zählen mit.

Typ: heuristic. Sprache: de, en. Mindestlänge: 100 Wörter.

### Doppelte Absätze (%)

**Formel:** 100 × zusätzliche identische Absätze / Absätze mit ≥12 Wörtern

Identität der kleingeschriebenen Wortfolge; nur Absätze ab 12 Wörtern.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.


## Zusammenhang

### Lexikalischer Anschluss (%)

**Formel:** 100 × mittlerer Jaccard-Überlapp benachbarter Absatz-Wortmengen ohne Stoppwörter

Mindestens zwei benachbarte Absätze mit jeweils ≥12 Wörtern. Misst Wortanschluss, kein inhaltliches Verständnis.

Typ: heuristic. Sprache: de, en. Mindestlänge: 100 Wörter.

### Geringer Wortanschluss (%)

**Formel:** 100 × gültige Absatzpaare mit Jaccard <0,05 / gültige Absatzpaare

Hinweise auf Übergänge; Szenenwechsel und Synonyme führen ebenfalls zu niedrigen Werten.

Typ: heuristic. Sprache: de, en. Mindestlänge: 100 Wörter.

### Verknüpfungswörter (/100 W.)

**Formel:** Treffer einer offenen DE/EN-Konnektorenliste je 100 Wörter

Lexikalische Signale wie deshalb/however; keine Prüfung logischer Gültigkeit.

Typ: heuristic. Sprache: de, en. Mindestlänge: 100 Wörter.

### Ich-/Wir-Marker (/100 W.)

**Formel:** DE/EN-Pronomen der ersten Person je 100 Wörter

Dialog und Erzählstimme werden gemeinsam gezählt; kein verlässlicher Perspektivwechsel-Detektor.

Typ: heuristic. Sprache: de, en. Mindestlänge: 100 Wörter.


## Stilhinweise

### Zitierter Text (%)

**Formel:** Wörter innerhalb paariger Anführungszeichen / Wörter × 100

Erkennt „…“, “…” (auch deutsche Innenzitate), «…», »…« und gerade Doppelzeichen. Zitate sind nicht immer Dialog; ungeschlossene Paare werden ignoriert.

Typ: heuristic. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Fragesätze (%)

**Formel:** 100 × Satzeinheiten mit Fragezeichen / Sätze

Einfache Interpunktionszählung, auch innerhalb von Zitaten.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Ausrufesätze (%)

**Formel:** 100 × Satzeinheiten mit Ausrufezeichen / Sätze

Kein Maß für emotionale Intensität.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Kommas (/100 W.)

**Formel:** Kommas je 100 Wörter

Beschreibt Interpunktion; Aufzählungen erhöhen den Wert.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Kommaketten (%)

**Formel:** 100 × Sätze mit ≥4 Kommas / Sätze

Kandidat für dichte Satzstruktur, keine syntaktische Analyse.

Typ: heuristic. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Gedankenstriche (/100 W.)

**Formel:** Halbgeviert-/Geviertstriche und freistehende Bindestriche je 100 Wörter

Kann Unterbrechungen, Dialog oder Aufzählungen markieren.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Klammeröffnungen (/100 W.)

**Formel:** Anzahl ( und [ je 100 Wörter

Formales Signal für Einschübe, kein Test auf korrekte Klammerung.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Auslassungspunkte (/100 W.)

**Formel:** … oder mindestens drei Punkte je 100 Wörter

Beschreibt Zögern, Auslassung oder typografische Gewohnheiten.

Typ: descriptive. Sprache: de, en, und. Mindestlänge: 100 Wörter.

### Füllwortkandidaten (/100 W.)

**Formel:** Treffer der kuratierten DE/EN-Liste je 100 Wörter

z.B. eigentlich/irgendwie bzw. basically/actually. Kontext kann sie sinnvoll machen; kein Streichvorschlag ohne Lesen.

Typ: heuristic. Sprache: de, en. Mindestlänge: 100 Wörter.

### Abschwächungen (/100 W.)

**Formel:** Treffer der DE/EN-Liste für Unsicherheit je 100 Wörter

z.B. vielleicht/possibly. Kann präzise Unsicherheit oder die Figurenstimme ausdrücken.

Typ: heuristic. Sprache: de, en. Mindestlänge: 100 Wörter.

### Verstärker (/100 W.)

**Formel:** Treffer der DE/EN-Verstärkerliste je 100 Wörter

z.B. sehr/extremely. Beschreibt eine Stilentscheidung.

Typ: heuristic. Sprache: de, en. Mindestlänge: 100 Wörter.

### Abstrakte Wortendungen (/100 W.)

**Formel:** DE: -ung/-heit/-keit/-ismus/-ität/-schaft; EN: -tion/-sion/-ment/-ness/-ity/-ism

Wortformen ab 6 Buchstaben. Suffixkandidaten mit Flexionsvarianten; keine Wortarten- oder Nominalstilklassifikation.

Typ: heuristic. Sprache: de, en. Mindestlänge: 100 Wörter.

### Adverb-Endungskandidaten (/100 W.)

**Formel:** DE: -weise; EN: -ly, Wortlänge ≥5

Grobe Wortformheuristik, die auch Nicht-Adverbien treffen und viele Adverbien übersehen kann.

Typ: heuristic. Sprache: de, en. Mindestlänge: 100 Wörter.

### Passivkandidaten (%)

**Formel:** Satzanteil mit werden/be-Hilfsverb und Partizipkandidat im selben Satz

DE: ge…t/en oder …iert; EN: …ed/en plus kleine Ausnahmeliste. Keine Syntaxprüfung: Kopula, Futur und Adjektive können Fehlalarme erzeugen.

Typ: heuristic. Sprache: de, en. Mindestlänge: 100 Wörter.

### Verneinungsmarker (/100 W.)

**Formel:** DE/EN-Negationsliste je 100 Wörter

Keine Auflösung von Skopus, Ironie oder doppelter Verneinung.

Typ: heuristic. Sprache: de, en. Mindestlänge: 100 Wörter.

### Sinneswort-Marker (/100 W.)

**Formel:** Treffer der kleinen DE/EN-Sinneswortliste je 100 Wörter

Nur lexikalische Hinweise auf Sehen/Hören/Geruch/Berührung. Keine Show-don’t-tell-Bewertung.

Typ: heuristic. Sprache: de, en. Mindestlänge: 100 Wörter.

### Denk-/Gefühlsmarker (/100 W.)

**Formel:** Treffer der kleinen DE/EN-Liste für Denken und Fühlen je 100 Wörter

Keine Sentimentanalyse, keine Aussage über die Qualität von Innenperspektiven.

Typ: heuristic. Sprache: de, en. Mindestlänge: 100 Wörter.


## Wortlisten

Bei Dreierphrasen ist die Trefferzahl die Anzahl verschiedener wiederholter Phrasen; pro Phrase wird das erste Vorkommen verzeichnet. Die Übersicht wählt diese Beispiele nach Häufigkeit, andere Beispiele in Textreihenfolge. Das vollständige Fundstellenverzeichnis bleibt unter Details zugänglich und wird dort in Textreihenfolge seitenweise angezeigt.

### Füllwortkandidaten

de: eigentlich irgendwie gewissermaßen sozusagen halt eben quasi praktisch regelrecht letztendlich

en: actually basically essentially literally anyway anyhow somehow just really

### Abschwächungen

de: vielleicht möglicherweise vermutlich wahrscheinlich offenbar anscheinend scheinbar eventuell wohl womöglich

en: perhaps possibly probably apparently seemingly presumably maybe arguably

### Verstärker

de: sehr äußerst extrem völlig total absolut unglaublich wirklich besonders überaus ungemein

en: very extremely totally absolutely incredibly truly utterly quite deeply highly

### Verknüpfungswörter

de: deshalb deswegen daher dennoch jedoch trotzdem außerdem zudem folglich während hingegen somit weil obwohl damit schließlich

en: therefore however moreover nevertheless nonetheless furthermore consequently whereas although because hence thus meanwhile

### Ich-/Wir-Marker

de: ich mich mir mein meine meiner meinem meinen meines wir uns unser unsere unserer unserem unseren unseres

en: i me my mine myself we us our ours ourselves

### Verneinungsmarker

de: nicht nie niemals niemand niemanden nichts kein keine keiner keinem keinen keines weder

en: not no never nobody nothing neither nowhere cannot can't don't doesn't didn't isn't aren't wasn't weren't won't wouldn't shouldn't couldn't

### Sinneswort-Marker

de: sehen sah blick blickte glanz schimmer licht dunkel hell hören hörte klang rauschen knistern roch riechen duft geruch schmecken geschmack süß bitter salzig kalt warm rau weich berühren berührte

en: see saw gaze glanced glow glimmer light dark bright hear heard sound rustle whisper smell smelled scent taste sweet bitter salty cold warm rough soft touch touched

### Denk-/Gefühlsmarker

de: denken dachte denkt wissen wusste weiß fühlen fühlte fühlt glauben glaubte glaubt hoffen hoffte erinnert erinnerte erinnerung angst freude trauer zweifel

en: think thought thinks know knew knows feel felt feels believe believed believes hope hoped remember remembered memory fear joy grief doubt

### Stoppwörter de

aber, alle, als, am, an, auch, auf, aus, bei, bis, da, dann, das, dass, dem, den, denn, der, deren, des, dessen, dich, die, dies, diese, dieser, dieses, dir, doch, du, durch, ein, eine, einem, einen, einer, eines, er, es, euch, euer, eure, euren, für, gegen, haben, hat, hatte, hatten, hätte, hätten, ich, ihm, ihn, ihnen, ihr, ihre, ihrem, ihren, ihrer, ihres, im, in, ins, ist, ja, kann, konnte, konnten, können, könnte, man, mehr, mein, meine, mich, mir, mit, muss, nach, nein, nicht, noch, nur, oder, ohne, schon, sehr, sein, seine, sich, sie, sind, so, solch, solche, sollte, sollten, um, und, uns, unserem, unseren, unserer, unter, vom, von, vor, war, waren, was, weil, wenn, wer, werden, wie, wir, wird, wo, wurde, wurden, würde, würden, zu, zum, zur, über

### Stoppwörter en

a, all, also, am, an, and, any, are, as, at, be, because, been, being, but, by, can, could, did, do, does, each, for, from, had, has, have, he, her, here, him, his, how, i, if, in, into, is, it, its, just, may, me, might, must, my, no, not, of, on, only, onto, or, our, shall, she, should, so, some, than, that, the, their, them, then, there, these, they, this, those, to, us, very, was, we, were, what, when, where, which, while, who, will, with, without, would, you, your

## Quellen

- [quanteda · Lesbarkeitsformeln und Literatur](https://quanteda.io/reference/textstat_readability.html)
- [quanteda · Lexikalische Vielfalt und Literatur](https://quanteda.io/reference/textstat_lexdiv.html)
- [McCarthy & Jarvis (2010) · MTLD, vocd-D und HD-D](https://doi.org/10.3758/BRM.42.2.381)
- [LIX · Definition des Lesbarkeitsindex](https://www.lix.se/)
- [textstat · Sprachvarianten der Flesch-Formel](https://github.com/textstat/textstat)
