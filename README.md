# 🎬 Movie Player Lite

**English** | [한국어](README.ko.md) | [简体中文](README.zh-CN.md) | [Español](README.es.md) | [Português](README.pt-BR.md) | [Deutsch](README.de.md)

A free video player for Windows that lets you **cut out just the part you need, instantly and with no loss of quality**.

---

## ⬇️ Download and install

### 👉 [Download the Movie Player Lite installer (Windows 10 / 11)](https://github.com/iseohyun/movie-player-lite/releases/latest/download/MoviePlayerLite-Setup.exe)

1. **Click the link above.** A file named `MoviePlayerLite-Setup.exe` is downloaded.
2. **Double-click the downloaded file.** It is usually in your `Downloads` folder.
3. If a blue **"Windows protected your PC"** window appears, click **More info** → **Run anyway**.
   Windows shows this for programs made by individuals; it does not mean something is wrong with the program.
4. Choose your language and keep clicking **Next**. You can leave the options as they are.

   | Option | What it does |
   | :--- | :--- |
   | Install folder | Leave it unless you need a different place. |
   | Create a desktop shortcut | Tick it if you want an icon on the desktop. |
   | File types to play by default | Ticked types (such as `.mp4`) open in this program when you double-click them. |
   | Download the latest FFmpeg | **Leave it ticked.** It fetches the part needed for cutting and for saving YouTube videos. If you already have it, this option is not shown. |

5. Click **Install**, wait, then click **Finish**. The program starts.

- No administrator rights are needed. Works on 64-bit Windows 10 / 11.
- **To remove it**, open Windows `Settings` → `Apps` → `Installed apps`, find **Movie Player Lite**, and click `Uninstall`.

---

## 🎞️ What you can do

- **Ultra-fast cutting with no quality loss** — nothing is re-encoded, so even long videos take seconds.
- **Rotate or flip the picture and save it**, **save the current frame as a screenshot**
- **Draw on the video** — pen marks fade after a moment, handy while explaining something.
- **Play from a YouTube address** — streams right away the first time, then plays the saved file afterwards.
- **Playback speed, zoom and pan, frame-by-frame stepping, playlist**
- **Six languages** — 한국어, English, 简体中文, Español, Português, Deutsch

---

## 🚀 First steps

**Open a video**
Drag a video file onto the program window. Or right-click the picture and choose `File` → `Open`.

**Cut the part you want**
1. Press `E` to open the edit window.
2. Drag the **two green lines** on the timeline at the bottom to set the start and the end.
3. Click **Cut**. The original stays untouched and a new file is created.

**Watch a YouTube video**
Press `Ctrl + U` and paste the YouTube address. Use it only for videos you have the right to watch.

**Show the menu**
Press `Alt` or right-click the picture. Shortcuts are shown on the right side of each menu item.

---

## ⌨️ Common shortcuts

| Function | Shortcut |
| :--- | :---: |
| Play / Pause | `Space` |
| Back / forward 1 second | `←` / `→` |
| Back / forward 5 seconds | `Shift + ←` / `Shift + →` |
| Back / forward one frame | `<` / `>` |
| Volume up / down | `↑` / `↓` |
| Mute | `M` |
| Faster / slower / normal speed | `+` / `-` / `0` |
| Fullscreen / exit | `F` / `Esc` |
| Edit (cut) window | `E` |
| Playlist | `L` |
| Open a YouTube address | `Ctrl + U` |
| Rotate (right / left) | `]` / `[` |
| Zoom in / out / reset | `Ctrl + +` / `Ctrl + -` / `Ctrl + 0` |
| Save rotated video · screenshot | `Ctrl + S` |
| Drawing on/off / clear all | `D` / `C` |
| Previous / next video | `PgUp` / `PgDown` |
| About | `F1` |

Every shortcut can be searched and changed in `Settings` → `Shortcuts`.

---

## 🌐 Changing the language

Choose it in `Settings` → `Language`. The program restarts and applies it right away. At first it follows your Windows language.

---

## ❓ Questions and answers

**A "Windows protected your PC" window appears.**
Windows shows this for programs that are not signed with a paid certificate. Click **More info** → **Run anyway** to install.

**What is FFmpeg? Do I need it?**
It is a free tool that cuts and joins video. Without it you can still play videos, but cutting and saving YouTube videos will not work. Leave the option ticked during setup and it is fetched for you.

**A YouTube video will not open.**
This can happen for a while when YouTube changes its site. Download the latest installer from the link above and install it again.

**Where are saved YouTube videos kept?**
In the folder `%APPDATA%\MP4-Trim\youtube_cache`. Paste that into the File Explorer address bar to open it. Delete files there if it grows too large.

**If I uninstall the program, are my videos deleted?**
No. Only the program is removed; your video files and the clips you cut stay where they are.

---

## 🛠️ For developers

<details>
<summary>Run and build from source</summary>

You need: Python 3.12, `pip install PyQt6 yt-dlp pyinstaller`, and FFmpeg on PATH

```
python movie-player-lite.py      run from source
.\run-dev.bat                    stop the running app -> rebuild -> launch
.\build-installer.bat            build the installer (requires Inno Setup 6)
```

- The installer is written to `installer_output\MoviePlayerLite-Setup.exe`. Upload it to a GitHub release under that same name and the download link in this document points to the newest version.
- The version shown by the installer is read from the top entry of `VERSION.md`.
- **Adding a language**: copy `locales/en-US.json` to `locales/<language-code>.json`, translate it, put the display name in `_meta.name`, and it appears in the menu automatically.

```
src/core/       core logic (cutting and metadata, shortcuts, i18n, YouTube)
src/ui/         user interface (main window, player and timeline widgets, dialogs)
locales/        translation files per language
installer.iss   installer script
```

</details>

---

## 📜 License and history

- License: [GPL v3](LICENSE). Press `F1` in the program to see the open-source software it uses.
- Change history: [VERSION.md](VERSION.md)
