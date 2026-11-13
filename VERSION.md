# Movie Player Lite Version History

## [v1.7.1] - 2026-11-13 (CJK Text Rendering Fix, Japanese Language)
### Fixed
- **Broken Chinese/Japanese Characters (□)**:
  - On Windows setups where the Chinese or Japanese fonts are present but not registered (e.g. Korean Windows), characters missing from the system UI font were drawn as empty boxes.
  - The app now loads those font files directly and puts the font of the current UI language first, with the other languages' fonts as fallbacks. No Windows language pack is needed.

### Added
- **Japanese (日本語)**: UI translation (`locales/ja-JP.json`), installer wizard language, and `README.ja.md`.
- **Per-Language Fonts**: each locale file can name its fonts in `_meta.fonts`.

---

## [v1.7.0] - 2026-11-13 (Multi-Language UI, YouTube Playback, Installer, Hotkey Search & Menu Shortcut Hints)
### Added
- **Multi-Language UI (6 languages)**:
  - All UI strings moved to `locales/*.json` (한국어, English, 简体中文, Español, Português, Deutsch).
  - `Settings > Language`: follows the system language by default; any installed locale can be selected and the app restarts to apply it.
  - New languages can be added by dropping a `locales/<code>.json` file next to the app.
- **YouTube URL Playback (`Ctrl+U`)**:
  - First play streams up to 1080p immediately while saving an mp4 in the background.
  - Later plays of the same video use the saved offline file, so cutting and thumbnails work.
- **Windows Installer (`MoviePlayerLite-Setup.exe`)**:
  - Per-user install wizard: install folder, desktop shortcut, default file types per extension.
  - Detects FFmpeg during setup and downloads the latest release when it is missing or outdated.
- **Hotkey Search**: search the shortcut list by function name or by key.
- **About Dialog (`F1`)**: lists the open-source components with version and license.
- **Dev Script**: `run-dev.bat` stops the running app, rebuilds, and launches it.

### Changed
- **Menu Shortcut Display**: item names are left-aligned and the current shortcut is shown right-aligned in a dimmed color (reflects user changes).
- **Default Hotkeys**: playlist `L` / `F12`, rotate right `]`, rotate left `[`. The `[` / `]` secondary keys for previous/next video were removed (`PgUp` / `PgDown` remain).
  - Saved custom hotkeys are reset to the new defaults once on first launch.
- **FFmpeg Lookup Order**: the copy next to the exe is used first, then `PATH`, then the bundled one.
- **README**: rewritten for first-time users in all six languages, with a direct installer download link.

---

## [v1.6.1] - 2026-09-06 (FFmpeg Cutting Fix, Playlist Duplicate Prevention, Missing File Removal on F2, Transform Save Fix)
### Fixed / Enhanced
- **FFmpeg Lossless Video Cutting Fix**:
  - Reordered FFmpeg parameters (`-ss` and `-t` after `-i`) and added `-avoid_negative_ts make_zero` to prevent 1KB corrupted file output during lossless MP4 trimming.
  - Added duration validation (min 0.1s) to prevent invalid cutting calls.
- **Playlist Duplicate Entry Prevention**:
  - Normalized all file paths (`os.path.abspath(os.path.normpath)`) with case-insensitive check to prevent duplicate entries in the playlist.
- **Auto-Removal of Missing Files on F2**:
  - Pressing `F2` on a non-existent/deleted file automatically removes it from the playlist with an informative toast notice.
- **Transform Video Save Fix (`Ctrl+S`)**:
  - Fixed a method indentation bug that prevented rotated or flipped videos from being saved via `Ctrl+S`.

---

## [v1.6.0] - 2026-07-27 (Cut Button Auto-Reset, Timeline Cut Region Interactions, Playlist Extended Multi-Selection)
### Added / Enhanced
- **Cut Button State Auto-Reset**:
  - Automatically resets button text from "재생" back to "컷팅" as soon as the user adjusts trimming markers or modifies inputs.
- **Timeline Cut Region Interactions**:
  - Click on pastel yellow cut regions on filmstrip timeline to select and load cut boundaries/name.
  - Press `F2` to rename selected cut region history item.
  - Press `Del` / `Backspace` to delete selected cut region history item.
- **Playlist Extended Multi-Selection (`ExtendedSelection`)**:
  - Support `Ctrl + Click` to toggle individual item selections.
  - Support `Shift + Click` to select contiguous ranges of items.
  - Extended multi-deletion for playlist items (`Delete` and `Ctrl + Delete`).

---

## [v1.5.0] - 2026-07-23 (Full Visual Transform & DWM Screen Integration)
### Added / Enhanced
- **Win32 DWM Screen Integration**:
  - Disabled Windows 11 DWM rounded corners (`DWMWCP_DONOTROUND`) in frameless fullscreen mode.
  - Expanded frameless window to physical screen geometry (`screen.geometry()`) with `WindowStaysOnTopHint`, completely covering the Windows Taskbar and removing 1px edge gaps.
- **4-Stage Fullscreen Cycle (`F` / `F11` / Double-Click)**:
  - **Stage 0**: Standard Windowed Mode.
  - **Stage 1**: Standard Fullscreen (with UI controls & sidebars).
  - **Stage 2**: Frameless Video-Only Fullscreen (Aspect Fit, solid black background).
  - **Stage 3**: Frameless Video-Only Fullscreen (100% Stretched edge-to-edge fill).
  - Synchronized video screen double-click event to cycle through all 4 fullscreen stages.
- **Real-Time Visual Transform Renderer (`QGraphicsVideoItem`)**:
  - Replaced `QVideoWidget` with high-performance `QGraphicsScene` / `QGraphicsVideoItem`.
  - Applied unified `QTransform` matrix for simultaneous real-time visual rotation (90°/180°/270°) and horizontal/vertical flips (`H`, `V`).
  - Implemented aspect ratio auto-fit scaling on rotation (`R`, `L`).
- **Timestamp Overlay (`T` Key Toggle)**:
  - Floating translucent dark badge overlay over the bottom-left corner of the video screen.
  - Added `T` key shortcut toggle (ON/OFF).
- **Auto-Numbering & Filename Presets**:
  - Loaded videos automatically default output filename field to source file base name (without `.mp4`).
  - Automatic collision numbering (`(2)`, `(3)`...) when saving files with existing names.

### Fixed
- Resolved `AttributeError` tracebacks on overlay and play button handlers.
- Restored `T` key shortcut handler in keypress routing.

---

## [v1.4.0] - 2026-07-22 (Transform Hotkeys & Frame Screenshot)
### Added
- Shortcut transforms: `H` (Horizontal Flip), `V` (Vertical Flip), `R` (Rotate Right 90°), `L` (Rotate Left 90°).
- Live 4px red container border indicator on transform state modification.
- `Ctrl+S` smart behavior: Saves transformed video losslessly when modified; captures current frame PNG screenshot when unmodified.
- Playlist item `F2` inline rename with collision auto-numbering.

---

## [v1.3.0] - 2026-07-21 (Trimming Engine & Playlist History UI)
### Added
- FFmpeg timestamp normalization (`-ss` before `-i`, `-t` duration parameter) for zero-loss fast cutting.
- Pastel yellow background highlight gradient (1 cut, 2 cuts, 3+ cuts) for playlist items.
- Compact 22px item height and custom `PlaylistDelegate` painter.
- AppData path persistence (`playlist_history.json`, `task_history.json`).

---

## [v1.2.0] - 2026-07-20 (Focus Control Flow & Filmstrip Ruler Ticks)
### Added
- 8-Event focus routing to prevent accidental hotkey triggers during text editing.
- Filmstrip timeline ruler tick marks (1s/5s/10s intervals).
- `test_requirements_trace.py` automated traceability test suite.

---

## [v1.0.0] - 2026-07-19 (Initial Release)
- Core PySide6/PyQt6 video player, FFmpeg lossless trimming, custom hotkey manager, and playlist sidebar.
