# Bookalyzer auf macOS bauen und installieren

Eine DMG enthält die App und ihre Analyse-Laufzeit. Sie wird auf einem Mac gebaut;
anschließend lässt sich die App in den Programme-Ordner ziehen.
Ein Apple-Developer-Konto ist für diesen ad hoc signierten Build nicht nötig.

## DMG auf einem Mac erstellen

1. **Baupaket entpacken.** `Bookalyzer-0.5.3-Mac-Baupaket.zip` vollständig in
   einen lokalen Ordner entpacken. Benötigt werden **macOS 14 Sonoma oder neuer**,
   Internet und etwa 8 GB freier Platz. Keine Windows-Laufzeitordner mitkopieren.
   Alternativ kannst du den Projektordner aus dem
   [GitHub-Repository](https://github.com/PaulFreund/Bookalyzer) herunterladen
   (Code → Download ZIP) und entpacken. Das Skript lädt den festgelegten
   StoryScope-Code bei Bedarf selbst nach.
2. **Homebrew einrichten**, falls noch nicht vorhanden. Auf [brew.sh](https://brew.sh/)
   gibt es einen `.pkg`-Installer sowie die Terminal-Anleitung. Den dortigen
   Installationsanweisungen folgen. Apples Command Line Tools werden ebenfalls
   benötigt; fehlen sie, öffnet das Bauskript den Installationsdialog und erklärt
   den nächsten Schritt. Danach das Skript erneut starten.
3. **`Mac-DMG-erstellen.command` doppelklicken.** Ein Terminalfenster zeigt den
   Fortschritt. Das Skript installiert Node 22 und Python 3.11 über Homebrew,
   richtet die Projektabhängigkeiten ein und lädt den festgelegten unveränderten
   StoryScope-Commit sowie zwei öffentliche Referenzdateien mit Hashprüfung.
   Es prüft Analysen und Exporte, baut App und DMG und testet die enthaltene Laufzeit.
   Auf Intel richtet es zusätzlich Rust und OpenSSL ein, weil die festgelegte
   Cryptography-Version dort aus dem Quellcode gebaut wird. Diese Werkzeuge bleiben
   auf dem Build-Mac; OpenSSL wird nach der [offiziellen Anleitung statisch
   eingebunden](https://cryptography.io/en/latest/installation/#building-cryptography-on-macos).
4. **DMG weitergeben.** Nach erfolgreichem Abschluss öffnet Finder den Ordner
   `release`. Nur die passende `.dmg` an den anderen Mac weitergeben. Die daneben
   liegende `.sha256` kann zur Kontrolle der Übertragung mitgegeben werden.

Die erste Einrichtung kann je nach Internet und Mac einige Zeit dauern. Bei einem
Fehler stoppt das Skript; der betreffende Schritt und die Fehlermeldung stehen
im Fenster und in `build/mac-build.log`. Erneutes Starten verwendet bereits
geladene Abhängigkeiten und ersetzt keine persönliche Bibliothek.

Falls Finder das Skript nicht startet: Terminal öffnen, `bash ` einschließlich
Leerzeichen eingeben, `Mac-DMG-erstellen.command` aus Finder ins Terminal ziehen
und Enter drücken. Das funktioniert auch, wenn ein Entpacker die Ausführungsrechte
nicht erhalten hat. Den gesamten Ordner vorher entpacken.

## Welche Datei passt zu welchem Mac?

| MacBook beim Erstellen | Ergebnis | Empfänger |
| --- | --- | --- |
| Apple Silicon, z. B. M1/M2/M3 | `Bookalyzer-0.5.3-mac-arm64.dmg` | Apple Silicon, macOS 14+ |
| Intel | `Bookalyzer-0.5.3-mac-x64.dmg` | Intel, macOS 14+ |

Den Prozessor zeigt **Apple-Menü → Über diesen Mac**. Electron und die eingebaute
Python-Laufzeit werden beide für die Architektur des Build-Macs erstellt.
Für gemischte Intel-/Apple-Silicon-Rechner werden zwei Builds benötigt. Das Skript
erzeugt keine Universal-App und bricht bei einem Rosetta-Terminal ab. Auf Apple
Silicon im Finder bei „Terminal → Informationen“ die Option „Mit Rosetta öffnen“
deaktivieren, falls sie aktiv ist.

## Auf jedem Empfänger-Mac: App installieren

1. DMG öffnen.
2. **Bookalyzer auf Programme ziehen.** Bei einem Update die bisherige App
   vorher schließen und ersetzen.
3. Bookalyzer **aus Programme** starten; die DMG danach auswerfen.

Python, Node, Homebrew und ein Projektordner sind auf dem Empfänger-Mac unnötig.
Eine kurze Installationsanleitung liegt auch direkt in der DMG.

Die so erstellte App ist **ad hoc signiert, nicht mit Developer ID signiert und nicht
notarisiert**. Beanstandet macOS beim ersten Start den unbekannten Entwickler,
öffne danach **Systemeinstellungen → Datenschutz & Sicherheit → Dennoch öffnen**
und bestätige das Öffnen von Bookalyzer. Die Ausnahme gilt für diese App.
Auf verwalteten Macs können solche Ausnahmen gesperrt sein. Diesen Ablauf
beschreibt [Apple](https://support.apple.com/de-de/102445).

Bei einer Meldung über Beschädigung oder schädlichen Inhalt stattdessen die
Übertragung und den Build prüfen. Das Skript prüft Signaturintegrität und DMG,
aber ohne Notarisierung gibt es keine bestätigte Gatekeeper-Freigabe.

## Loslegen und Daten behalten

**Texte hinzufügen** → Datei und Schreibziel wählen → bei Bedarf **Kapitel erkennen**
einschalten → Vorschau prüfen → lokale Analyse starten. Unter **Textqualität**
stehen die vier Zusammenfassungen und die nächsten Überarbeitungsschritte.
**Details** öffnet alle 51 Kennzahlen. Unter **Texte und Kapitel auswählen**
einen Referenztext speichern oder ganze Texte und Kapitel nebeneinander auswählen.

Lokale Qualitätsanalysen funktionieren offline. Die optionale StoryScope-
Extraktion braucht zusätzlich eine angemeldete Codex CLI und eine ausdrückliche
Bestätigung der Textübertragung in der App; sie ist für die lokalen Diagramme
nicht erforderlich.

Die Bibliothek liegt normalerweise unter
`~/Library/Application Support/Bookalyzer/library`. Eine vorhandene Bibliothek
der früheren BookAnalyzer-Version wird am bisherigen Ort weiterverwendet.
Den tatsächlichen Pfad
zeigt **Methode & Studie**. Diesen Ordner bei geschlossener App sichern. Ein
App-Update verändert ihn nicht. Das Baupaket und die DMG enthalten keine eigenen
Bücher, Baselines oder Analyseergebnisse.

## Prüfstand und alternative Builds

Das Baupaket wird auf Windows auf Vollständigkeit, Shell-Syntax, Dateirechte im ZIP
und ausgeschlossene private Daten geprüft. **Eine fertige, auf macOS geprüfte DMG
liegt hier noch nicht vor.** Das Doppelklick-Skript führt die nativen Prüfungen auf
deinem Mac aus, einschließlich Start aus einem leeren Arbeits- und Datenordner.
Danach vor der Weitergabe selbst eine Testdatei importieren und einen Kurzbericht
öffnen; das bestätigt auch Finder-Installation und Anzeige auf deinem Mac.

Für Entwickler: `npm run package:mac` erzeugt denselben ad hoc signierten Build.
Der optionale GitHub-Workflow `.github/workflows/macos.yml` kann beide Architekturen
bauen. `package:mac:release` mit Apple-Zertifikat und Notarisierung bleibt für
eine öffentliche Verteilung verfügbar; lokale ad hoc signierte Builds benötigen
diese Zugangsdaten nicht.
