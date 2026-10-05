# Änderungen

## Noch nicht veröffentlicht

- Der vollständige Datenbestand lässt sich unter „Datenbestand sichern & laden“
  als ZIP exportieren und wiederherstellen, einschließlich Originaldateien,
  Analysen, Baselines, Einstellungen und Markierungen. Der Import prüft Dateien
  und Prüfsummen, zeigt eine Vorschau und sichert den vorherigen Stand automatisch.

## Bookalyzer 0.5.3

- Modell und Reasoning-Level sind in den Standardeinstellungen, beim Upload und
  beim nachträglichen Start von StoryScope auswählbar. Codex liefert die aktuelle
  Modellliste und die unterstützten Stufen über einen lokalen App-Server.
- Die Extraktion verwendet weiterhin `codex exec` mit gespeichertem Modell und
  Reasoning-Level. Fortsetzen behält beide Werte. Narrative Distanzen mit
  unterschiedlichen Reasoning-Stufen werden gesperrt.
- Veraltete Windows-Verknüpfungen zur früheren Plugin-Laufzeit werden durch die
  vorhandene aktuelle Codex-Desktop-Laufzeit ersetzt. Eine explizit eingestellte
  CLI bleibt maßgeblich.

## Bookalyzer 0.5.2

- StoryScope lässt sich für vorhandene lokale Analysen nachträglich ergänzen,
  direkt aus der Textbibliothek, dem Bericht und dem leeren narrativen Diagramm.
  Segmentvorschau, Codex-Einstellungen und Übertragungsfreigabe gelten für diesen
  Start. Eine weitere Dokumentkopie ist nicht nötig.
- Das lokale Profil bleibt bei laufender oder unterbrochener StoryScope-Analyse
  verfügbar. Gespeicherte Antworten können fortgesetzt werden; nach Abschluss
  führt ein eigener Knopf zu den StoryScope-Diagrammen.
- Lokale Qualitätsbereiche und Zielprofile können auch nach einer StoryScope-
  Analyse erweitert werden. Bei einer fehlgeschlagenen externen Analyse lässt
  sich das lokale Profil unabhängig davon erstellen.

## Bookalyzer 0.5.1

- Alle Fundstellen bleiben zugänglich. Offene Beispiele rücken nach, wenn andere
  als beabsichtigt markiert werden. Details bieten Seiten sowie Filter für Regel
  und Bearbeitungsstatus. Markierungen lassen sich auch nach einem Neustart
  zurücknehmen. Messwerte ändern sich dadurch nicht.
- Stilabweichungen erklären Richtung und Kennzahl, nennen Messwert und
  Vergleichsbereich und zeigen ein Diagramm mit Median und Quartilband.
  Referenztext und andere Kapitel werden klar unterschieden. Kurzberichte
  enthalten dieselben Erklärungen und konkrete Hinweise zum Nachlesen.
- Das Produkt heißt Bookalyzer. App, Berichte, Installationsdateien und
  Anleitungen verwenden den neuen Namen. Vorhandene Bibliotheken der früheren
  Version werden weiterverwendet.
- Methodenversion 2.1.0 erneuert die abgeleiteten Qualitäts-Caches. Gespeicherte
  Baselines und Entscheidungen bleiben erhalten.

Der native macOS-Build und die Installation auf einem echten Mac stehen
weiterhin aus. Das Mac-Baupaket enthält dafür das Doppelklick-Skript und die
Anleitung; es ist selbst keine fertige DMG.
