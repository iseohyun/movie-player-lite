from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent, QKeySequence

DEFAULT_HOTKEYS = {
    "toggle_option": {"name": "편집 모달 호출", "primary": "E", "secondary": ""},
    "toggle_playlist": {"name": "리스트 보기", "primary": "P", "secondary": ""},
    "play_pause": {"name": "멈춤 / 재생", "primary": "Space", "secondary": "K"},
    "step_1s_prev": {"name": "1초 전 이동", "primary": "Left", "secondary": ""},
    "step_1s_next": {"name": "1초 후 이동", "primary": "Right", "secondary": ""},
    "step_5s_prev": {"name": "5초 전 이동", "primary": "Shift+Left", "secondary": ""},
    "step_5s_next": {"name": "5초 후 이동", "primary": "Shift+Right", "secondary": ""},
    "step_frame_prev": {"name": "1프레임 전 이동", "primary": "<", "secondary": ","},
    "step_frame_next": {"name": "1프레임 후 이동", "primary": ">", "secondary": "."},
    "speed_up": {"name": "+0.25배속", "primary": "+", "secondary": "="},
    "speed_down": {"name": "-0.25배속", "primary": "-", "secondary": "_"},
    "speed_reset": {"name": "기본배속(1.0x)으로", "primary": "0", "secondary": ""},
    "prev_video": {"name": "이전 동영상", "primary": "PgUp", "secondary": "["},
    "next_video": {"name": "다음 동영상", "primary": "PgDown", "secondary": "]"},
    "volume_up": {"name": "볼륨 올리기", "primary": "Up", "secondary": ""},
    "volume_down": {"name": "볼륨 내리기", "primary": "Down", "secondary": ""},
    "toggle_mute": {"name": "음소거 토글", "primary": "M", "secondary": ""},
    "zoom_in": {"name": "화면 확대", "primary": "Ctrl++", "secondary": "Ctrl+="},
    "zoom_out": {"name": "화면 축소", "primary": "Ctrl+-", "secondary": "Ctrl+_"},
    "zoom_reset": {"name": "확대/이동 초기화", "primary": "Ctrl+0", "secondary": ""},
    "pan_up": {"name": "확대 시 위로 이동", "primary": "Ctrl+Up", "secondary": ""},
    "pan_down": {"name": "확대 시 아래로 이동", "primary": "Ctrl+Down", "secondary": ""},
    "pan_left": {"name": "확대 시 왼쪽 이동", "primary": "Ctrl+Left", "secondary": ""},
    "pan_right": {"name": "확대 시 오른쪽 이동", "primary": "Ctrl+Right", "secondary": ""},
    "rotate_right": {"name": "화면 오른쪽 90도 회전", "primary": "R", "secondary": ""},
    "rotate_left": {"name": "화면 왼쪽 90도 회전", "primary": "L", "secondary": ""},
    "flip_h": {"name": "화면 좌우반전", "primary": "H", "secondary": ""},
    "flip_v": {"name": "화면 상하반전", "primary": "V", "secondary": ""},
    "save_transform": {"name": "변형 상태 저장 / 캡처", "primary": "Ctrl+S", "secondary": ""},
    "toggle_fullscreen": {"name": "전체화면 토글", "primary": "F", "secondary": "F11"},
    "exit_fullscreen": {"name": "기본화면(전체화면 해제)", "primary": "Esc", "secondary": ""},
    "toggle_time_label": {"name": "시간/상태 정보 표시 토글", "primary": "T", "secondary": ""},
    "toggle_hud": {"name": "상세 설정 정보 HUD 토글", "primary": "`", "secondary": "~"},
    "show_properties": {"name": "동영상 정보 모달 보기", "primary": "?", "secondary": ""},
    "delete_playlist_item": {"name": "재생목록 항목 삭제", "primary": "Delete", "secondary": ""},
    "rename_playlist_item": {"name": "재생목록 파일 이름 변경", "primary": "F2", "secondary": ""},
}


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

