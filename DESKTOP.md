# Bookalyzer Desktop

Electron-App für TXT, DOCX, EPUB und textbasierte PDF: lokale Sprachprofile,
optionale StoryScope-Extraktion, direkte Vergleiche, feste Baselines, Kapitelanalysen
und eine verständliche Qualitätsübersicht mit 51 lokalen Kennzahlen unter Details.

## Installation

Das App-Paket enthält Python, Analysebibliotheken, Taxonomie, öffentliche Referenzdaten
und den unveränderten StoryScope-Code. Für lokale Analysen sind kein Projektordner,
Node, Python oder Terminal erforderlich. Private Bücher werden nicht mitgeliefert.

- **macOS:** getrennte DMG-Dateien für Apple Silicon (`arm64`) und Intel (`x64`).
  DMG öffnen, Bookalyzer nach Programme ziehen, starten. Ziel: **macOS 14 Sonoma+**.
  Electron 44 benötigt mindestens macOS 13; wissenschaftliche Bibliotheken können
  macOS-14-Wheels enthalten, deshalb ist die Paketgrenze bewusst 14.
- **Windows:** `Bookalyzer-0.5.3-win-x64.exe` ist der Installer ohne Administratorpflicht.
  Alternativ den vollständigen Ordner `release/win-unpacked` verwenden und darin
  `Bookalyzer.exe` starten; die EXE allein reicht nicht.

**Stand:** Windows-Laufzeit und native App wurden aus einem leeren Arbeitsordner
ohne Python-Projekt gestartet. Echte macOS-Builds, Starttests und Apple-Notarisierung
müssen auf einem Mac bzw. im bereitgestellten Workflow laufen. Derzeit liegt kein
auf macOS verifiziertes DMG vor. Private Builds sind ad hoc signiert und nicht notarisiert.
Für einen macOS-Build ohne Developer-ID-Zertifikat: **[Mac-Anleitung](MAC_INSTALL.md)**.
Das Baupaket enthält ein Doppelklick-Skript; ein Apple-Developer-Konto ist dafür nicht nötig.

Bereits lokal analysierte Texte lassen sich in der **Textbibliothek** über
**StoryScope mit Codex ergänzen** erweitern. Die Vorschau zeigt die vorhandenen
Segmente und die Anzahl der Dimensionsaufrufe. Modell, Reasoning-Level, Parallelität
und Vergleichsraum sind für diesen Start wählbar. Nach der Freigabe bleibt das lokale
Textprofil während der Extraktion nutzbar. Bei einer Unterbrechung setzt
**StoryScope fortsetzen** dieselbe Analyse mit gespeicherten Antworten fort.
**StoryScope-Diagramme ansehen** öffnet anschließend die narrativen Signale;
**Sprachliches Profil** und das **Qualitätslabor** bleiben beim selben Dokument
verfügbar. Eine erneute Dateiübertragung in die Bibliothek ist nicht nötig.

Der umgekehrte Weg ist über **Lokale Analyse erweitern** möglich: Qualitätsbereiche,
Textprofil und Satzlängenziele werden auf dem vorhandenen Text lokal neu berechnet.
Auch nach einer unterbrochenen externen Analyse lässt sich so das lokale Profil
erstellen. Vorhandene StoryScope-Merkmale bleiben erhalten.

StoryScope-Extraktionen benötigen zusätzlich eine angemeldete Codex CLI. Das lokale
Textprofil funktioniert sofort offline. Vor neuen externen Analysen werden die
Segmentvorschau und die Übertragung der gewählten Texte ausdrücklich bestätigt.

**Modell und Reasoning:** Die Dropdowns stehen in den Standardeinstellungen, beim
Upload und beim nachträglichen Ergänzen von StoryScope zur Verfügung. Die Modellliste
kommt aus dem installierten Codex; je Modell erscheinen dessen unterstützte
Reasoning-Stufen. „Modellstandard“ übernimmt den von Codex gemeldeten Standard.
Modell und Stufe werden beim Start fest gespeichert und beim Fortsetzen beibehalten.
Mehr Reasoning kann die Laufzeit und den Kontingentverbrauch erhöhen. Wenn die
Liste nicht verfügbar ist, bleibt eine manuelle Modell-ID möglich.

Technisch startet Electron einen mitgelieferten lokalen Python-Dienst über Pipes.
Für die Modellliste startet dieser kurz einen eigenen `codex app-server` über
stdio und ruft nur `model/list` auf; dabei wird kein Dokument übertragen und kein
Analyseauftrag gestartet. StoryScope selbst verwendet weiterhin `codex exec`,
mit zehn Dimensionsaufrufen je Segment und den gewählten Einstellungen. Codex
verwendet seine vorhandene Anmeldung; Bookalyzer benötigt keinen separaten API-Key.
Es läuft kein zusätzlicher HTTP-Server. Protokoll:
[Codex App-Server](https://learn.chatgpt.com/docs/app-server#list-models-modellist).

## Vergleiche

Unter **Texte vergleichen** gibt es drei Ansichten:

| Ansicht | Funktion | Maßstab |
| --- | --- | --- |
| Direkt vergleichen | Bis zu sechs Texte: Profile, Verläufe, Violinplots und Distanzmatrix | Gemeinsamer Raum der aktuellen Auswahl; Werte können sich mit der Auswahl ändern |
| Gegen Baseline | Fertige Analyse als benannten Referenzstand speichern; andere Texte dagegen vergleichen | Feste Kopie von Merkmalen, Segmenten, Kennzahlen, Taxonomie und Feature-Set-Konfiguration |
| Kapitel vergleichen | Kapitelkurve, vollständige Liste und bis zu sechs Kapitel nebeneinander | Optional jedes Kapitel gegen dieselbe Baseline; alternativ Kapitel untereinander |

Mehrere Baselines sind möglich. Sie bleiben nach dem Ausblenden des Originaluploads
erhalten. Neue Zieltexte verändern weder Encoder noch Standardisierung der Baseline.
Hashes erkennen Änderungen an Artefakten; ID und Zeitpunkt dokumentieren den Stand.

**Kapitel erkennen und getrennt analysieren** ist als Standard und je Upload
einstellbar, standardmäßig aus. Aktiviert überschreitet kein Segment eine Kapitelgrenze.
Lange Kapitel werden geteilt, kurze bleiben erhalten und werden markiert. Die Vorschau
zeigt erkannte Überschriften vor dem Start.

Erkennung: DOCX-Überschriften, deutlich formatierte Überschriften oder Kapitelzeilen;
EPUB-Überschriften und Spine-Abschnitte; Zeilen wie „Kapitel 1 – Ankunft“ bzw.
„Chapter One“ in TXT/PDF. Mehrere Kapitel in einem EPUB-Abschnitt werden getrennt.
Unterüberschriften können eigene Abschnitte erzeugen; die Vorschau ist maßgeblich.
Beliebige literarische Überschriften ohne Struktur werden nicht erraten.

Die Kapitelansicht lässt sich nachträglich ein-/ausschalten. Bei älteren Analysen
sind lokale Kapitelwerte verfügbar; narrative Kapitelwerte gibt es nur, wenn alle
zugehörigen Segmente vollständig im Kapitel liegen. Andernfalls mit aktiviertem
Kapitelschalter erneut importieren und analysieren. Kurvenpunkte und Titel öffnen
den Kapiteltext. Ausgewählte Kapitel teilen Diagrammachsen und eine Distanzmatrix.

## Berechnung

### Textqualität (ab 0.5)

Die Startansicht zeigt vier verständliche Karten: Lesefluss, Wortwahl, Wiederholungen
und Konsistenz. Grün steht für das eingehaltene Schreibziel, Orange für Prüfhilfen,
Blau für Beobachtungen, Grau für zu wenig Grundlage. Es gibt keine Gesamtnote.
Das erste Diagramm ist direkt sichtbar; bis zu drei unterschiedliche nächste Schritte
führen zu Fundstellen im Lesefenster. Beispiele lassen sich als beabsichtigt markieren
und unter Details wieder berücksichtigen. Eine Kapitelmatrix zeigt alle Kapitel
mit denselben vier Kriterien; ein Klick öffnet das jeweilige Kapitel.

Erzähltext, Sachtext und Fachtext schlagen anpassbare Satzlängenziele vor. Der
Standard für Erzähltexte lautet: höchstens 10 % der Sätze haben mehr als 30 Wörter.
Die Ziele gelten als persönliche Vorgaben, nicht als wissenschaftliche Qualitätsnorm.
Unter 300 Wörtern bleibt die Einordnung zurückhaltend. **Details** öffnet alle
51 Kennzahlen in sechs auswählbaren Bereichen:

| Bereich | Beispiele |
| --- | --- |
| Lesbarkeit | LIX, RIX, Flesch–Amstad, englischer Flesch und Flesch–Kincaid, Wiener Sachtextformel |
| Wortschatz | MATTR-100, HD-D-42, MTLD, Entropie, Simpson-Vielfalt, Yule's K, Hapaxanteil |
| Rhythmus | Satzlängenvariation, 90. Perzentil, kurze/lange Sätze, Nachbarwechsel, Autokorrelation, Absatzvariation |
| Wiederholungen | Dreierphrasen, identische Sätze und Absätze, Satzanfänge, nahe Wortwiederholungen |
| Zusammenhang | Lexikalischer Absatzanschluss, geringe Überlappung, Konnektoren, Ich-/Wir-Marker |
| Stilhinweise | Zitate, Fragen, Interpunktion, Füllwort-, Abschwächungs-, Verstärker-, Passiv- und Wortendungskandidaten, Sinnes- und Denkmarker |

Alle sechs Bereiche sind standardmäßig aktiv und lassen sich in den Defaults und je
Upload abwählen. Die Grenze für lange Sätze ist einstellbar (Standard: über 30 Wörter).
Silbenbasierte Indizes sind ausdrücklich Näherungen; Wortlisten und Regeln stehen
vollständig in der Oberfläche und im JSON-Export. Kein Download oder zusätzlicher
Dienst ist nötig.

**Diagramme:** gemeinsame Messwertachse, Merkmalsmatrix mit festen Farbskalen, Segment- oder
Kapitelverlauf, Rhythmus-Fingerabdruck mit Minimum/Maximum je Gruppe. Eine vollständige
Kapitelliste zeigt Messwert und Baseline-Delta für jedes Kapitel. Bis zu sechs Kapitel
lassen sich zusätzlich nebeneinander anzeigen. Dunklere Zellen bedeuten höhere Werte
bzw. größere Abweichungen, niemals bessere oder schlechtere Qualität. Bei Deltas
stehen Blau und Violett für niedrigere bzw. höhere Werte, Null bleibt neutral.
Die Farbstärke bleibt beim Wechsel der Textauswahl gleich.

Fundstellen sind vollständig durchblätterbar und nach Regel sowie Bearbeitungsstatus
filterbar. Der Überblick zeigt offene Beispiele mit Originalkontext; nach einer
Markierung als beabsichtigt rücken die nächsten nach. Markierungen lassen sich
unter Details wieder zurücknehmen, auch nach einem Neustart.
Kurze Texte, deaktivierte Bereiche und unpassende Sprachen erhalten fehlende Werte mit
Begründung statt Null. Deutsch/Englisch-spezifische Regeln werden für unbekannte Sprachen
unterdrückt. Baseline-Deltas benötigen dieselbe Sprache und Methodenversion; unterschiedliche
Schwellen für lange Sätze sperren nur dieses eine Delta. Prozentdeltas sind Prozentpunkte.

Die Qualitätsmethoden werden auch auf ältere Analysen und Baselines lokal angewandt.
Baseline-Text und Artefakte bleiben unverändert; abgeleitete Ergebnisse liegen getrennt
in `quality-cache`. Methodenversion, Text-Hash, Einstellungen und Referenz-ID stehen im
JSON-Bericht. Gesamttexte und Kapitel verwenden die ursprünglichen eingeschlossenen
Abschnittstexte mit erhaltenen Absätzen. Segmentgrenzen ändern die Gesamtanalyse
nicht. Satzlänge, Redeanteil und Wortvielfalt verwenden in allen Ansichten dieselbe
Berechnung. Bei alten Baselines ohne Originalstruktur entfallen Absatzdeltas.

Baseline-Vergleiche verwenden den Median von bis zu neun gleich langen, nicht
überlappenden Referenzausschnitten. Ab drei Ausschnitten zeigt ein Band ihre
mittleren 50 %. Bei einer kürzeren Baseline bleiben längenabhängige Deltas leer.
Ohne externe Baseline vergleichen sich Kapitel mit mindestens vier weiteren
Kapiteln ab 300 Wörtern. Stilabweichungen sind Suchhilfen, keine Qualitätsurteile.
Ein Baseline-Wechsel behält die gewählten Kapitel und das Kapitel im Fokus bei.

**Kurzbericht** exportiert standardmäßig eine kompakte Zusammenfassung mit vier
Karten, Satzlängendiagramm und nächsten Schritten; ein vollständiger Methodenanhang
ist optional. Kapitelberichte ergänzen eine Liste aller Kapitel. CSV und JSON
enthalten weiterhin alle 51 Kennzahlen samt passender Referenz und Quartilband.

Die Kennzahlen sind weder ein KI-Detektor noch eine literarische Gesamtnote. Es gibt
keine Grammatik-, Fakten-, Sentiment- oder semantische Kohärenzprüfung. Wortbasierte
Heuristiken können gewollte Stilmittel und Eigennamen treffen; Fundstellen sind zum
Nachlesen gedacht. Formeln und Grenzen: [QUALITY_METHODS.md](QUALITY_METHODS.md).

### StoryScope und bisheriges Textprofil

- Lokale Werte: Satzlänge, relative Satzlängenstreuung, Wortvielfalt in vollständigen
  gleitenden 100-Wort-Fenstern (MATTR), heuristischer Redeanteil. Differenzen stehen in ihren Einheiten;
  Redeanteile in Prozentpunkten, nicht relativen Prozent.
- Baseline: Encoder und StandardScaler werden ausschließlich auf der gespeicherten
  Referenz gefittet. Pro Zielsegment mittlere euklidische Distanz zu
  `min(25, Baseline-Segmentzahl)` Nachbarn, danach ungewichtetes Segmentmittel.
  Konstante Referenzspalten haben Skalierung 1. Kleine Baselines sind gekennzeichnet.
- Interne Distanz: gemeinsame Standardisierung, Selbsttreffer ausgeschlossen,
  `k = min(25, Segmentzahl − 1)`. Kapitelmatrix: Abstand mittlerer Segmentvektoren
  im Raum des ganzen Buchs, unabhängig von den angehakten Kapiteln.
- Narrative Baseline-Distanzen setzen gleiche Sprache, Modell, Reasoning-Level, Taxonomie und
  Feature-Set voraus. Eigenvergleiche und identische Wiederimporte erhalten keine
  narrative Distanz. Unterschiedliche Segmentgrößen erzeugen einen Hinweis.
- Fehlende Werte sind „–“, nicht Null. Kapitelübergreifende Merkmale werden keinem
  Kapitel zugeschrieben. Höhere Werte bedeuten keine bessere Qualität.

Die App liefert keine kalibrierte Mensch-/KI-Wahrscheinlichkeit. Die externe
multivariate Referenzprüfung bleibt wegen inkonsistenter öffentlicher Werte gesperrt.
Eigene Baselines sind keine externe Kalibrierung. Öffentliche Mensch-/KI-Bänder
beschreiben lediglich gültige Einzelmerkmale mit bekanntem Nenner.

## Berichte und Daten

Bis zu zwölf Dateien pro Import, maximal 30 MB pro Datei. Standards werden je
Upload kopiert; spätere Änderungen verändern vorhandene Analysen nicht. Lokale
Analysen übertragen keine Texte. Unterbrochene StoryScope-Extraktionen lassen sich
mit ihren gespeicherten Antworten fortsetzen.

Direkte Berichte enthalten ausgewählte Texte. Baseline- und Kapitelansicht haben
einen eigenen **Vergleich exportieren**-Knopf: HTML mit SVG, PDF in Electron,
CSV mit allen Werten, JSON mit Referenznachweisen. Berichte benötigen keine App.

Installierte Apps speichern unter Electron `userData/library`, auf macOS typischerweise
`~/Library/Application Support/Bookalyzer/library`. Der echte Pfad steht unter
„Methode & Studie“. Eine Bibliothek der früheren Version wird am bisherigen Ort
weiterverwendet. Quellcode-Starts verwenden `.bookanalyzer/` und können vorhandene
Projektanalysen übernehmen. `BOOKANALYZER_DATA` kann eine bestehende Bibliothek wählen.
Bibliotheken enthalten Originaltexte; als Ganzes sichern. Ausblenden löscht keine
Dateien. Zwei Prozesse dürfen nicht gleichzeitig dieselbe Bibliothek öffnen.

Unter **Werkzeuge → Datenbestand sichern & laden** lässt sich die vollständige
Bibliothek als **ZIP sichern**: Originaldateien (auch ausgeblendete Texte), Analysen,
gespeicherte StoryScope-Antworten, Baselines, Einstellungen und Markierungen.
Die ZIP kann auf einem anderen Rechner mit Bookalyzer geladen werden. Berichte
und Einzeltext-Uploads verwenden weiterhin ihre eigenen Export-/Importfunktionen.

**ZIP zum Laden wählen** prüft Formatversion, sichere Dateipfade, Prüfsummen und
Bibliotheksdaten und zeigt die Anzahl der Texte, Baselines und Dateien. Erst
**Datenbestand ersetzen** stellt die gesamte Sicherung wieder her und ersetzt
die aktuelle Bibliothek. Vorher wird der bisherige Stand automatisch als ZIP im
benachbarten Ordner `<Bibliotheksname>-backups` gesichert; der genaue Pfad erscheint
nach dem Laden. Diese ZIP lässt sich auf demselben Weg wieder laden. Fehlerhafte
Archive verändern die Bibliothek nicht; scheitert der Austausch der Ordner, wird
der vorherige Ordner zurückgestellt. Unterbrochene Analysen starten beim Laden
nicht automatisch. Während laufender Analysen sind Sichern und Laden gesperrt.

Das Format enthält `manifest.json` mit Version und SHA-256-Prüfsummen und die
Dateien unter `library/`. Grenzen: 1 GB ZIP, 4 GB entpackt, 100.000 Dateien.
Die Desktop-App arbeitet direkt mit Dateien; die lokale Entwicklungsvorschau
überträgt ZIPs über eigene Dateirouten ohne Base64-Konvertierung.

Zusätzliche Import-/Exporttests: `node desktop/test-library-transfer.cjs` sowie
`node scripts/python.cjs -m pytest -q tests/test_desktop_archive.py`.

## Entwicklung und Builds

Python 3.11 und Node 22.12+ sind nur auf dem Build-/Entwicklungsrechner nötig.
StoryScope-Commit: `642e746804e1ee4138ffdcf13b7412eb3dc2a70b`, unverändert.

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock -r requirements-build.txt
npm ci
npm start
```

Unter Windows `.venv/Scripts/python.exe` verwenden; `Start-Bookalyzer.ps1`
startet die Entwicklungsinstallation. Vorschau: `npm run dev`, 127.0.0.1:5173.
Bei parallel laufender App dafür eine andere `BOOKANALYZER_DATA` setzen.

```sh
npm test
npm run test:comparisons
npm run test:pdf
npm run test:desktop
npm run package:mac       # auf Mac: private, ad-hoc signierte DMG
npm run package:mac:source # plattformunabhängiges Baupaket mit Anleitung
npm run package:win       # auf Windows: eigenständiger Installer
npm run test:runtime      # eingefrorene Laufzeit, vier Formate, 304 Merkmale
npm run test:packaged     # native App mit leerem Arbeits- und Datenordner
```

Tests prüfen Referenzstabilität, Kapitelgrenzen, kurze Kapitel, Textverlust,
Neustart, Hashprüfung, Modellkompatibilität und Exporte. Die Laufzeitprüfung nutzt
synthetische Fixtures. Kein Test überträgt Texte an einen Modellanbieter.

`.github/workflows/macos.yml` baut auf `macos-15` (arm64) und `macos-15-intel` (x64),
prüft Analyse, Laufzeit und native App und speichert DMG/ZIP als Artefakte. Manuell
auslösen; der Workflow veröffentlicht keinen Release.

Für private Weitergabe genügt `Mac-DMG-erstellen.command` bzw. `package:mac`.
Für spätere öffentlich verteilte, notarisierte Mac-Releases `signed_release`
aktivieren. Repository-Secrets:
`MAC_CSC_LINK`, `MAC_CSC_KEY_PASSWORD` für Developer ID Application und
`APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID` für Notarisierung.
Lokal: `npm run package:mac:release`, mit `CSC_LINK`/`CSC_KEY_PASSWORD` und Apple-
Variablen; alternativ Apple-API-Key-Authentifizierung. Ohne Signaturdaten bricht
der Release-Build ab. Release-Prüfungen: Codesign, angeheftetes Ticket, Gatekeeper.

`BOOKANALYZER_PYTHON` überschreibt die Entwicklerlaufzeit, `BOOKANALYZER_CODEX`
optional den CLI-Pfad. macOS: Homebrew-/lokale CLI-Pfade, native Menüs, Cmd-Kürzel
und Wiederöffnen über das Dock. Renderer: isolierter Preload, kein Node-Zugriff.
PDF: eigener skriptloser Kontext ohne Netzwerkzugriff.

Grundlagen: [Electron 44](https://www.electronjs.org/blog/electron-44-0),
[PyInstaller](https://www.pyinstaller.org/en/stable/usage.html),
[electron-builder 26](https://www.electron.build/v26/docs/mac/),
[GitHub-Runner](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
