# Das Beispiel in der README

Die Screenshots zeigen die tatsächliche lokale Analyse von **Die Verwandlung**
von **Franz Kafka** in der deutschen Originalsprache. Die drei ursprünglichen
Teile bleiben erhalten. Es werden keine Modellantworten oder erfundenen
Analysewerte verwendet.

Der Demolauf umfasst **19.148 Wörter**, **drei Teile**, **sechs Analysesegmente**
und **51 lokale Kennzahlen**. Die Kapitel enthalten 6.104, 6.663 und 6.381 Wörter.

## Quelle und Gemeinfreiheit

- Text: [Project Gutenberg, eBook 22367](https://www.gutenberg.org/ebooks/22367).
- Download: [deutsche UTF-8-Ausgabe](https://www.gutenberg.org/cache/epub/22367/pg22367.txt).
- Digitalisierung: Jana Srna, Alexander Bauer und das [Online Distributed Proofreading Team](https://www.pgdp.net/), laut Quellenangabe der Ausgabe.
- Kafka starb 1924. Das deutsche Original ist nach der Schutzfrist von 70 Jahren gemäß [§ 64 UrhG](https://www.gesetze-im-internet.de/urhg/__64.html) in Deutschland gemeinfrei. Project Gutenberg kennzeichnet die Ausgabe als gemeinfrei in den USA.

Das Skript bewahrt den vollständigen Gutenberg-Download einschließlich Lizenzhinweisen
lokal auf. Für die Analyse entfernt es den Gutenberg-Vor- und Nachspann und die
Titelseiten, benennt `I.`, `II.`, `III.` in `Teil I`, `Teil II`, `Teil III` um und
verbindet die druckbreiten Zeilen innerhalb der vorhandenen Absätze. Der Erzähltext
wird nicht gekürzt oder umgeschrieben.

## Analyse nachstellen

Nach der Einrichtung aus der README:

```sh
npm run demo:readme
```

Das lädt den Text herunter und führt mit der echten Desktop-Analyse eine **lokale**
Auswertung durch. Kein Text wird an einen Modellanbieter übertragen. Import,
Textgrundlage, Kennzahlen und die Demo-Bibliothek liegen unter `outputs/readme-demo/`,
das durch `.gitignore` ausgeschlossen ist. Vorhandene persönliche Bibliotheken und
Projektanalysen werden nicht übernommen.

Einstellungen: Deutsch, erzählender Text, alle lokalen Kennzahlen, Kapitelgrenzen
berücksichtigen, Zielgröße 3.000 Wörter je Segment, mindestens 1.500 und höchstens
4.500 Wörter. Als lange Sätze gelten Sätze mit mehr als 30 Wörtern; das voreingestellte
Schreibziel erlaubt einen Anteil von 10 %. Hinweise auf Abweichungen beziehen sich
auf diese Einstellungen und sind kein Urteil über Kafka.

Die Demo in der Desktop-App öffnen, unter Windows / PowerShell:

```powershell
$env:BOOKANALYZER_DATA = (Resolve-Path outputs/readme-demo/library).Path
npm start
```

Unter macOS / Linux:

```sh
BOOKANALYZER_DATA="$PWD/outputs/readme-demo/library" npm start
```

Für einen eigenen neuen Demolauf kann ein anderer Ausgabeordner gewählt werden:

```sh
npm run demo:readme -- --destination outputs/readme-demo-new
```

Die maschinenlesbaren [Beispielergebnisse](demo-analysis.json) enthalten ausschließlich
öffentliche Buchangaben, Quell-Hashes, Einstellungen und berechnete Kennzahlen.
Die Screenshots wurden aus der laufenden Windows-App mit dieser separaten Bibliothek
aufgenommen.

## Screenshots aktualisieren

```sh
npm run build
npm run screenshots:readme
```

Die interne Electron-Aufnahme erfasst den tatsächlich gerenderten App-Inhalt.
Sie prüft vorher den Demo-Text gegen den dokumentierten Hash und nimmt Übersicht,
Kapitelmatrix und den Detailvergleich der drei Teile auf. Andere Fenster,
Desktop-Inhalte und Mauszeiger werden nicht aufgenommen. Die PNG-Dateien liegen
unter `docs/screenshots/` und sind für die README versioniert.
