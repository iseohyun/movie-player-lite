from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent, QKeySequence

from src.core.i18n import tr

DEFAULT_HOTKEYS = {
    "toggle_option": {"primary": "E", "secondary": ""},
    "toggle_playlist": {"primary": "L", "secondary": "F12"},
    "play_pause": {"primary": "Space", "secondary": "K"},
    "step_1s_prev": {"primary": "Left", "secondary": ""},
    "step_1s_next": {"primary": "Right", "secondary": ""},
    "step_5s_prev": {"primary": "Shift+Left", "secondary": ""},
    "step_5s_next": {"primary": "Shift+Right", "secondary": ""},
    "step_frame_prev": {"primary": "<", "secondary": ","},
    "step_frame_next": {"primary": ">", "secondary": "."},
    "speed_up": {"primary": "+", "secondary": "="},
    "speed_down": {"primary": "-", "secondary": "_"},
    "speed_reset": {"primary": "0", "secondary": ""},
    "prev_video": {"primary": "PgUp", "secondary": ""},
    "next_video": {"primary": "PgDown", "secondary": ""},
    "volume_up": {"primary": "Up", "secondary": ""},
    "volume_down": {"primary": "Down", "secondary": ""},
    "toggle_mute": {"primary": "M", "secondary": ""},
    "zoom_in": {"primary": "Ctrl++", "secondary": "Ctrl+="},
    "zoom_out": {"primary": "Ctrl+-", "secondary": "Ctrl+_"},
    "zoom_reset": {"primary": "Ctrl+0", "secondary": ""},
    "pan_up": {"primary": "Ctrl+Up", "secondary": ""},
    "pan_down": {"primary": "Ctrl+Down", "secondary": ""},
    "pan_left": {"primary": "Ctrl+Left", "secondary": ""},
    "pan_right": {"primary": "Ctrl+Right", "secondary": ""},
    "rotate_right": {"primary": "]", "secondary": ""},
    "rotate_left": {"primary": "[", "secondary": ""},
    "flip_h": {"primary": "H", "secondary": ""},
    "flip_v": {"primary": "V", "secondary": ""},
    "save_transform": {"primary": "Ctrl+S", "secondary": ""},
    "toggle_fullscreen": {"primary": "F", "secondary": "F11"},
    "exit_fullscreen": {"primary": "Esc", "secondary": ""},
    "toggle_time_label": {"primary": "T", "secondary": ""},
    "toggle_hud": {"primary": "`", "secondary": "~"},
    "show_properties": {"primary": "?", "secondary": ""},
    "delete_playlist_item": {"primary": "Delete", "secondary": ""},
    "rename_playlist_item": {"primary": "F2", "secondary": ""},
    "toggle_draw_mode": {"primary": "D", "secondary": ""},
    "toggle_draw_modal": {"primary": "Shift+D", "secondary": ""},
    "clear_drawings": {"primary": "C", "secondary": ""},
    "undo_drawing": {"primary": "Ctrl+Z", "secondary": ""},
    "show_about": {"primary": "F1", "secondary": ""},
}

# 표시 이름은 번역 파일(locales/*.json)의 hotkey.<action_id> 키에서 가져온다.
for _action_id, _info in DEFAULT_HOTKEYS.items():
    _info["name"] = tr(f"hotkey.{_action_id}")


def event_to_key_str(event: QKeyEvent) -> str:
    key = event.key()
    if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
        return ""
    mods = event.modifiers()
    parts = []
    if mods & Qt.KeyboardModifier.ControlModifier:
        parts.append("Ctrl")
    if mods & Qt.KeyboardModifier.ShiftModifier:
        parts.append("Shift")
    if mods & Qt.KeyboardModifier.AltModifier:
        parts.append("Alt")

    shift_implied_keys = {"?", "<", ">", "+", "_", "~"}

    if key == Qt.Key.Key_Left:
        k = "Left"
    elif key == Qt.Key.Key_Right:
        k = "Right"
    elif key == Qt.Key.Key_Up:
        k = "Up"
    elif key == Qt.Key.Key_Down:
        k = "Down"
    elif key == Qt.Key.Key_Space:
        k = "Space"
    elif key == Qt.Key.Key_PageUp:
        k = "PgUp"
    elif key == Qt.Key.Key_PageDown:
        k = "PgDown"
    elif key == Qt.Key.Key_BracketLeft:
        k = "["
    elif key == Qt.Key.Key_BracketRight:
        k = "]"
    elif key == Qt.Key.Key_Question or (key == Qt.Key.Key_Slash and (mods & Qt.KeyboardModifier.ShiftModifier)):
        k = "?"
    elif key == Qt.Key.Key_Less or (key == Qt.Key.Key_Comma and (mods & Qt.KeyboardModifier.ShiftModifier)):
        k = "<"
    elif key == Qt.Key.Key_Comma:
        k = ","
    elif key == Qt.Key.Key_Greater or (key == Qt.Key.Key_Period and (mods & Qt.KeyboardModifier.ShiftModifier)):
        k = ">"
    elif key == Qt.Key.Key_Period:
        k = "."
    elif key == Qt.Key.Key_Plus or (key == Qt.Key.Key_Equal and (mods & Qt.KeyboardModifier.ShiftModifier)):
        k = "+"
    elif key == Qt.Key.Key_Equal:
        k = "="
    elif key == Qt.Key.Key_Underscore or (key == Qt.Key.Key_Minus and (mods & Qt.KeyboardModifier.ShiftModifier)):
        k = "_"
    elif key == Qt.Key.Key_Minus:
        k = "-"
    elif key == Qt.Key.Key_AsciiTilde or (key == Qt.Key.Key_QuoteLeft and (mods & Qt.KeyboardModifier.ShiftModifier)):
        k = "~"
    elif key == Qt.Key.Key_QuoteLeft:
        k = "`"
    elif key == Qt.Key.Key_Delete:
        k = "Delete"
    elif key == Qt.Key.Key_Escape:
        k = "Esc"
    elif key == Qt.Key.Key_F2:
        k = "F2"
    else:
        k = QKeySequence(key).toString().upper()

    if k in shift_implied_keys and "Shift" in parts:
        parts.remove("Shift")

    parts.append(k)
    return "+".join(parts)

