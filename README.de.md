# 🎬 Movie Player Lite

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh-CN.md) | [Español](README.es.md) | [Português](README.pt-BR.md) | **Deutsch**

Ein kostenloser Videoplayer für Windows, mit dem du **genau den benötigten Abschnitt sofort und ohne Qualitätsverlust herausschneiden** kannst.

---

## ⬇️ Herunterladen und installieren

### 👉 [Installationsprogramm für Movie Player Lite herunterladen (Windows 10 / 11)](https://github.com/iseohyun/movie-player-lite/releases/latest/download/MoviePlayerLite-Setup.exe)

1. **Klicke auf den Link oben.** Die Datei `MoviePlayerLite-Setup.exe` wird heruntergeladen.
2. **Doppelklicke auf die heruntergeladene Datei.** Sie liegt normalerweise im Ordner `Downloads`.
3. Falls ein blaues Fenster **„Der Computer wurde durch Windows geschützt“** erscheint, klicke auf **Weitere Informationen** → **Trotzdem ausführen**.
   Windows zeigt das bei Programmen von Privatpersonen an; es bedeutet nicht, dass mit dem Programm etwas nicht stimmt.
4. Wähle deine Sprache und klicke dich mit **Weiter** durch. Die Optionen kannst du so lassen, wie sie sind.

   | Option | Was sie bewirkt |
   | :--- | :--- |
   | Installationsordner | So lassen, außer du brauchst einen anderen Ort. |
   | Desktopverknüpfung erstellen | Ankreuzen, wenn du ein Symbol auf dem Desktop möchtest. |
   | Standardmäßig abzuspielende Dateitypen | Angekreuzte Typen (z. B. `.mp4`) öffnen sich per Doppelklick in diesem Programm. |
   | Neuestes FFmpeg herunterladen | **Angekreuzt lassen.** Lädt die Komponente, die zum Schneiden und zum Speichern von YouTube-Videos nötig ist. Ist sie schon vorhanden, erscheint diese Option nicht. |

5. Klicke auf **Installieren**, warte und klicke dann auf **Fertigstellen**. Das Programm startet.

- Es sind keine Administratorrechte nötig. Läuft unter 64-Bit-Windows 10 / 11.
- **Zum Entfernen** öffne in Windows `Einstellungen` → `Apps` → `Installierte Apps`, suche **Movie Player Lite** und klicke auf `Deinstallieren`.

---

## 🎞️ Was du damit tun kannst

- **Extrem schnelles Schneiden ohne Qualitätsverlust** — es wird nichts neu kodiert, daher dauern selbst lange Videos nur Sekunden.
- **Bild drehen oder spiegeln und speichern**, **aktuelles Bild als Bildschirmfoto speichern**
- **Auf dem Video zeichnen** — Striche verschwinden nach einem Moment; praktisch beim Erklären.
- **Wiedergabe über eine YouTube-Adresse** — beim ersten Mal wird sofort gestreamt, danach wird die gespeicherte Datei abgespielt.
- **Wiedergabegeschwindigkeit, Zoomen und Verschieben, bildweises Springen, Wiedergabeliste**
- **Sechs Sprachen** — 한국어, English, 简体中文, Español, Português, Deutsch

---

## 🚀 Erste Schritte

**Ein Video öffnen**
Ziehe eine Videodatei in das Programmfenster. Oder klicke mit der rechten Maustaste auf das Bild und wähle `Datei` → `Öffnen`.

**Den gewünschten Abschnitt schneiden**
1. Drücke `E`, um das Bearbeitungsfenster zu öffnen.
2. Ziehe die **beiden grünen Linien** in der Zeitleiste unten, um Anfang und Ende festzulegen.
3. Klicke auf **Schneiden**. Das Original bleibt unverändert, es wird eine neue Datei erstellt.

**Ein YouTube-Video ansehen**
Drücke `Strg + U` und füge die YouTube-Adresse ein. Nutze das nur für Videos, die du ansehen darfst.

**Das Menü anzeigen**
Drücke `Alt` oder klicke mit der rechten Maustaste auf das Bild. Die Tastenkürzel stehen rechts neben den Menüeinträgen.

---

## ⌨️ Häufig genutzte Tastenkürzel

| Funktion | Tastenkürzel |
| :--- | :---: |
| Wiedergabe / Pause | `Leertaste` |
| 1 Sekunde zurück / vor | `←` / `→` |
| 5 Sekunden zurück / vor | `Umschalt + ←` / `Umschalt + →` |
| Ein Bild zurück / vor | `<` / `>` |
| Lauter / leiser | `↑` / `↓` |
| Stumm | `M` |
| Schneller / langsamer / normale Geschwindigkeit | `+` / `-` / `0` |
| Vollbild / beenden | `F` / `Esc` |
| Bearbeitungsfenster (Schneiden) | `E` |
| Wiedergabeliste | `L` |
| YouTube-Adresse öffnen | `Strg + U` |
| Drehen (rechts / links) | `]` / `[` |
| Vergrößern / verkleinern / zurücksetzen | `Strg + +` / `Strg + -` / `Strg + 0` |
| Gedrehtes Video speichern · Bildschirmfoto | `Strg + S` |
| Zeichnen ein/aus / alles löschen | `D` / `C` |
| Vorheriges / nächstes Video | `Bild↑` / `Bild↓` |
| Über das Programm | `F1` |

Alle Tastenkürzel lassen sich unter `Einstellungen` → `Tastenkürzel` durchsuchen und ändern.

---

## 🌐 Sprache ändern

Wähle sie unter `Einstellungen` → `Sprache`. Das Programm startet neu und übernimmt sie sofort. Anfangs richtet es sich nach der Windows-Sprache.

---

## ❓ Fragen und Antworten

**Es erscheint das Fenster „Der Computer wurde durch Windows geschützt“.**
Windows zeigt das bei Programmen an, die nicht mit einem kostenpflichtigen Zertifikat signiert sind. Klicke auf **Weitere Informationen** → **Trotzdem ausführen**, um zu installieren.

**Was ist FFmpeg? Brauche ich das?**
Ein kostenloses Werkzeug zum Schneiden und Zusammenfügen von Videos. Ohne es kannst du Videos weiterhin abspielen, aber das Schneiden und das Speichern von YouTube-Videos funktionieren nicht. Lass die Option bei der Installation angekreuzt, dann wird es automatisch geladen.

**Ein YouTube-Video lässt sich nicht öffnen.**
Das kann vorübergehend passieren, wenn YouTube seine Website ändert. Lade über den Link oben das neueste Installationsprogramm herunter und installiere es erneut.

**Wo liegen die gespeicherten YouTube-Videos?**
Im Ordner `%APPDATA%\MP4-Trim\youtube_cache`. Füge diesen Pfad in die Adressleiste des Datei-Explorers ein, um ihn zu öffnen. Lösche dort Dateien, wenn der Ordner zu groß wird.

**Werden meine Videos gelöscht, wenn ich das Programm deinstalliere?**
Nein. Nur das Programm wird entfernt; deine Videodateien und die geschnittenen Clips bleiben, wo sie sind.

---

## 🛠️ Für Entwickler

<details>
<summary>Aus dem Quellcode ausführen und bauen</summary>

Benötigt: Python 3.12, `pip install PyQt6 yt-dlp pyinstaller` und FFmpeg im PATH

```
python movie-player-lite.py      aus dem Quellcode starten
.\run-dev.bat                    laufende App beenden -> neu bauen -> starten
.\build-installer.bat            Installationsprogramm erstellen (benötigt Inno Setup 6)
```

- Das Installationsprogramm wird nach `installer_output\MoviePlayerLite-Setup.exe` geschrieben. Lade es unter genau diesem Namen in ein GitHub-Release hoch, dann zeigt der Download-Link in diesem Dokument auf die neueste Version.
- Die im Installationsprogramm angezeigte Version wird aus dem obersten Eintrag von `VERSION.md` gelesen.
- **Sprache hinzufügen**: `locales/en-US.json` nach `locales/<Sprachcode>.json` kopieren, übersetzen, den Anzeigenamen in `_meta.name` eintragen – sie erscheint automatisch im Menü.

```
src/core/       Kernlogik (Schnitt und Metadaten, Tastenkürzel, i18n, YouTube)
src/ui/         Oberfläche (Hauptfenster, Player- und Zeitleisten-Widgets, Dialoge)
locales/        Übersetzungsdateien je Sprache
installer.iss   Skript des Installationsprogramms
```

</details>

---

## 📜 Lizenz und Verlauf

- Lizenz: [GPL v3](LICENSE). Drücke im Programm `F1`, um die verwendete Open-Source-Software zu sehen.
- Änderungsverlauf: [VERSION.md](VERSION.md)
