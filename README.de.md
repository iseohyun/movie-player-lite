# 🎬 Movie Player Lite

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh-CN.md) | [Español](README.es.md) | [Português](README.pt-BR.md) | **Deutsch**

## 📌 Überblick und Zweck
- **Movie Player Lite** ist ein extrem schneller, verlustfreier Videoplayer und -splitter, der den Zeit- und Qualitätsverlust vermeidet, der beim Bearbeiten großer, hochwertiger Videos durch das Neukodieren der Timeline entsteht.
- Der **FFmpeg-basierte verlustfreie Schnitt (Stream Copy)** extrahiert in kürzester Zeit genau den benötigten Bereich – ohne Qualitätsverlust.

---

## 🔥 Hauptfunktionen und Bedienung

### 1. Integrierter Videoplayer & Timeline-Schieberegler
- **Integrierter Videoplayer**: basiert auf QMediaPlayer; Wiedergabe/Pause/Vollbild per Klick, Doppelklick oder Maus-Overlay
- **Vorschau-Timeline mit 10 asynchron extrahierten Szenen**: eine Filmstreifen-Leiste, die den Verlauf des gesamten Videos auf einen Blick zeigt
- **Intelligente 1px-Markierungslinien**: Schnittanfang/-ende (1px grüne Linien) und die aktuelle Wiedergabeposition (1px rote Linie) werden immer zuoberst gezeichnet
- **Intelligente Pause**: Beim Greifen oder Ziehen der Suchleiste während der Wiedergabe wird automatisch pausiert, um präzise arbeiten zu können

### 2. Seitenleisten für Optionen, Verlauf und Wiedergabeliste
- **Linkes Optionsfeld (`[`)**: Stummschalten, Aufnahmeeigenschaften kopieren, automatische Nummerierung sowie Auswahl des Speicherpfads (gleicher Ordner / output / benutzerdefiniert)
- **Feld für eigene Tastenkürzel (`⌨`)**: primäre und sekundäre Tastenkürzel selbst ändern und speichern (`hotkeys.json`)
- **Rechtes Wiedergabelistenfeld (`]`)**: zuletzt verwendete Videos verwalten, Dateien hinzufügen oder per Drag & Drop ablegen, Einträge mit Delete entfernen oder alles leeren, fehlende Dateien werden automatisch bereinigt (`playlist_history.json`)
- **Sanfte Gleitanimation**: optimiertes Ein- und Ausfahren der Seitenleisten beim Drücken eines Tastenkürzels

---

## ⌨️ Standard-Tastenkürzel

| Funktion | Primär (Primary) | Sekundär (Secondary) |
| :--- | :---: | :---: |
| **Optionsfeld umschalten** | `[` | - |
| **Wiedergabeliste umschalten** | `]` | - |
| **Wiedergabe / Pause** | `Space` | `K` |
| **1 Sekunde zurück / vor** | `Left` / `Right` | `J` / `L` |
| **5 Sekunden zurück / vor** | `Shift + Left` / `Shift + Right` | - |
| **1 Bild zurück / vor** | `Ctrl + Left` / `Ctrl + Right` | - |
| **Vollbild umschalten / beenden** | `F` (oder `F11`) | `Esc` |
| **Videodetails anzeigen** | `?` (Shift + `/`) | - |
| **Listeneintrag entfernen** | `Delete` | - |

---

## 🌐 Sprache
- Unter **Einstellungen → Sprache** wählst du `Systemsprache` (Standard) oder eine beliebige installierte Sprache. Die Änderung wird **nach einem Neustart des Programms** wirksam.
- Mitgelieferte Sprachen: 한국어, English, 简体中文, Español, Português (Brasil), Deutsch. Gibt es für die Systemsprache keine Übersetzung, wird Englisch verwendet.
- **Sprache hinzufügen**: `locales/en-US.json` nach `locales/<Sprachcode>.json` kopieren (z. B. `fr-FR.json`), die Werte übersetzen, den Anzeigenamen in `_meta.name` eintragen und den Ordner `locales` neben der ausführbaren Datei ablegen. Die Sprache erscheint dann automatisch im Menü.

---

## 📁 Projektstruktur

```
mp4-trim
├ src/
│  ├ core/                  # Kernlogik (FFmpeg-Schnitt, Metadaten-/Eigenschaftsextraktion, eigene Tastenkürzel, i18n)
│  ├ ui/                    # UI-Komponenten & Dialoge
│  │  ├ widgets/            # Eigene Timeline-, Videoplayer- und Zeiteingabe-Widgets
│  │  ├ dialogs/            # Dialog zum Zuweisen von Tastenkürzeln
│  │  └ main_window.py      # Layout des Hauptfensters VideoCutterApp und Ereignisverknüpfung
│  └ utils/                 # Popup für Ausnahmeprotokolle und Hilfsfunktionen für Zeitformate
├ locales/              : Übersetzungsdateien je Sprache (ko-KR.json, en-US.json, ...)
├ icon.ico              : Hauptsymbol des Programms
├ MP4-Trim image.png    : README-Screenshot
├ build.bat             : Build-Skript für die eigenständige Version (Light / Vollpaket)
├ mp4-trim.py           : Einstiegspunkt (Main Entry Point)
├ README.md             : Benutzerhandbuch und Projektinformationen
└ .gitignore            : Git-Ausschlussregeln
```

---

## 🛠️ FFmpeg vorbereiten (erforderlich)
1. **FFmpeg herunterladen**: [offizielle Website von Gyan.dev](https://www.gyan.dev/ffmpeg/builds/)
2. `ffmpeg-release-essentials.zip` entpacken und `bin/ffmpeg.exe` in diesen Projektordner kopieren oder zum System-**PATH** hinzufügen.

---

## 📜 Versionsverlauf

- **v1.0.5**
  - Timeline-Markierungen garantiert zuoberst in der Z-Reihenfolge (1px grüne Schnittpunkte / 1px rote Abspielkopf-Linie)
  - Automatische Pause beim Bedienen der Suchleiste
  - System für eigene Tastenkürzel (Primary / Secondary) mit `hotkeys.json`
  - Bildgenaues Springen mit `Ctrl + ← / →`
  - Taste `?` zeigt detaillierte Videoeigenschaften
  - Fehler bei der C++-Speicherfreigabe in der Seitenleistenanimation behoben
- **v1.0.4**
  - Popup für Ausnahmeprotokolle in PyInstaller-Builds (`sys.excepthook`)
  - Gleitanimation der Seitenleisten (`[` / `]`)
  - Automatische Bereinigung gelöschter/fehlender Einträge im Wiedergabelistenverlauf
- **v1.0.3**
  - Integrierter Videoplayer (QMediaPlayer) und Hover-Overlay-Steuerung
  - Vorschau-Filmstreifen-Timeline (10 Szenen asynchron mit FFmpeg extrahiert)
  - Wiedergabeliste in der Seitenleiste (Tastenkürzel `]`) mit Verlaufsverwaltung
- **v1.0.2**
  - Enter im Feld für den Ausgabedateinamen startet den Schnitt; doppelte Namen werden mit einem Rahmen hervorgehoben
- **v1.0.1**
  - Fehler im Aufgabenverlauf und bei der Pfadnormalisierung behoben
- **v1.0.0**
  - Erstveröffentlichung (Grundfunktionen des extrem schnellen verlustfreien Videosplitters)
