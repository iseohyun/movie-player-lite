# 🎬 Movie Player Lite

**English** | [한국어](README.ko.md) | [简体中文](README.zh-CN.md) | [Español](README.es.md) | [Português](README.pt-BR.md) | [Deutsch](README.de.md)

## 📌 Overview and Purpose
- **Movie Player Lite** is an ultra-fast lossless video player & splitter that avoids the time and quality loss caused by timeline re-encoding when editing large, high-quality videos.
- Its **FFmpeg-based lossless (stream copy) cutting** extracts just the range you need in an instant, with no quality loss.

---

## 🔥 Key Features and Usage

### 1. Built-in Video Player & Timeline Slider
- **Built-in video player**: powered by QMediaPlayer; play/pause/fullscreen by click, double-click, or the mouse overlay
- **Thumbnail timeline with 10 asynchronously extracted scenes**: a filmstrip timeline bar that shows the flow of the whole video at a glance
- **1px vertical smart markers**: cut start/end (1px green lines) and the current playback position (1px red line) are always drawn on top
- **Smart pause**: grabbing or dragging the seek bar during playback pauses automatically for precise control

### 2. Options, History and Playlist Sidebars
- **Left options panel (`[`)**: mute, copy capture properties, auto numbering, and a choice of same / output / custom save path
- **Custom shortcut panel (`⌨`)**: change and save primary and secondary shortcuts yourself (`hotkeys.json`)
- **Right playlist panel (`]`)**: manage recent videos, add files or drag & drop, remove items with Delete or clear everything, and automatically prune missing files (`playlist_history.json`)
- **Smooth slide animation**: optimized sidebar open/close sliding when a shortcut is pressed

---

## ⌨️ Default Shortcuts

| Function | Primary | Secondary |
| :--- | :---: | :---: |
| **Toggle options panel** | `[` | - |
| **Toggle playlist** | `]` | - |
| **Play / Pause** | `Space` | `K` |
| **Back / forward 1 second** | `Left` / `Right` | `J` / `L` |
| **Back / forward 5 seconds** | `Shift + Left` / `Shift + Right` | - |
| **Back / forward 1 frame** | `Ctrl + Left` / `Ctrl + Right` | - |
| **Toggle / exit fullscreen** | `F` (or `F11`) | `Esc` |
| **Show video details** | `?` (Shift + `/`) | - |
| **Remove playlist item** | `Delete` | - |

---

## 🌐 Language
- Use **Settings → Language** to choose `System language` (the default) or any installed language. The change is applied **after you restart the program**.
- Bundled languages: 한국어, English, 简体中文, Español, Português (Brasil), Deutsch. If there is no translation for the system language, English is used.
- **Adding a language**: copy `locales/en-US.json` to `locales/<language-code>.json` (for example `fr-FR.json`), translate the values, put the display name in `_meta.name`, and keep the `locales` folder next to the executable. It appears in the menu automatically.

---

## 📁 Project Structure

```
mp4-trim
├ src/
│  ├ core/                  # Core logic (FFmpeg cutting, metadata/property extraction, custom shortcuts, i18n)
│  ├ ui/                    # UI components & dialogs
│  │  ├ widgets/            # Custom timeline, video player, time input widgets
│  │  ├ dialogs/            # Shortcut assignment dialog
│  │  └ main_window.py      # VideoCutterApp main window layout and event wiring
│  └ utils/                 # Exception logging popup and time format utilities
├ locales/              : Translation files per language (ko-KR.json, en-US.json, ...)
├ icon.ico              : Main program icon
├ MP4-Trim image.png    : README screenshot
├ build.bat             : Stand-alone build script (light / full package)
├ mp4-trim.py           : Main entry point
├ README.md             : User guide and project information
└ .gitignore            : Git ignore rules
```

---

## 🛠️ Preparing FFmpeg (Required)
1. **Download FFmpeg**: [Gyan.dev official site](https://www.gyan.dev/ffmpeg/builds/)
2. Extract `ffmpeg-release-essentials.zip`, then copy `bin/ffmpeg.exe` into this project folder or add it to the system **PATH**.

---

## 📜 Version History

- **v1.0.5**
  - Timeline markers guaranteed on top of the Z order (1px green cut points / 1px red playhead line)
  - Automatic pause while operating the seek bar
  - Custom shortcut system (primary / secondary) backed by `hotkeys.json`
  - `Ctrl + ← / →` single-frame stepping
  - `?` key shows detailed video properties
  - Fixed a C++ memory release error in the sidebar animation
- **v1.0.4**
  - Exception logging popup for PyInstaller builds (`sys.excepthook`)
  - Sidebar sliding animation (`[` / `]`)
  - Automatic pruning of deleted/missing playlist history items
- **v1.0.3**
  - Built-in video player (QMediaPlayer) and hover overlay controls
  - Thumbnail filmstrip timeline bar (10 scenes extracted asynchronously with FFmpeg)
  - Sidebar playlist (shortcut `]`) with history management
- **v1.0.2**
  - Enter in the output file name box runs the cut; duplicate names are highlighted with a border
- **v1.0.1**
  - Fixed task history and path normalization bugs
- **v1.0.0**
  - First release (basic ultra-fast lossless video splitter)
