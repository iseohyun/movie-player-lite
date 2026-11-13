"""UI 글꼴 설정.

Windows는 표시 언어에 따라 일부 글꼴을 등록하지 않는다. 예를 들어 한국어 Windows에서는 중국어·일본어 글꼴 파일이
C:\\Windows\\Fonts 에 있어도 시스템 글꼴 목록에는 나오지 않아, 맑은 고딕에 없는 간체자가 네모(□)로 깨져 보인다.
언어 팩을 설치하지 않아도 되도록 다음 두 가지를 한다.

1. 목록에 없는 글꼴은 Windows 글꼴 폴더의 파일을 이 프로그램에서만 직접 불러온다.
2. 현재 UI 언어의 글꼴을 맨 앞에 두고, 나머지 언어 글꼴을 대체 글꼴로 이어 붙인다.
"""
import os
import logging

from PyQt6.QtGui import QFont, QFontDatabase

from src.core import i18n

# 어떤 UI 언어에서도 다른 언어 글자(예: 언어 메뉴의 "简体中文", "日本語")가 보이도록 하는 공통 대체 글꼴
COMMON_FALLBACK_FONTS = ["Segoe UI", "Malgun Gothic", "Microsoft YaHei UI", "Yu Gothic UI"]
# 글꼴 이름 → Windows 글꼴 폴더의 파일 (보통 굵기, 굵게). 시스템 목록에 없을 때만 직접 불러온다.
FONT_FILES = {
    "Malgun Gothic": ["malgun.ttf", "malgunbd.ttf"],
    "Microsoft YaHei UI": ["msyh.ttc", "msyhbd.ttc"],
    "Yu Gothic UI": ["YuGothR.ttc", "YuGothB.ttc"],
    "Microsoft JhengHei UI": ["msjh.ttc", "msjhbd.ttc"],
}
# 스타일시트에서 고정폭으로 지정한 글꼴: 한글·한자·가나가 없으므로 같은 대체 글꼴을 연결한다
MONOSPACE_FONTS = ["Consolas"]


def _windows_fonts_dir() -> str:
    return os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


def _ensure_font_available(family: str) -> bool:
    """시스템 목록에 없는 글꼴이면 글꼴 파일을 직접 불러온다. 사용할 수 있게 되면 True."""
    if family in QFontDatabase.families():
        return True
    loaded = False
    for file_name in FONT_FILES.get(family, []):
        path = os.path.join(_windows_fonts_dir(), file_name)
        if os.path.isfile(path) and QFontDatabase.addApplicationFont(path) != -1:
            loaded = True
    if not loaded:
        logging.warning(f"UI font not available: {family}")
    return loaded


def build_font_families() -> list:
    """현재 언어의 글꼴(번역 파일 _meta.fonts)을 앞에, 공통 대체 글꼴을 뒤에 둔, 실제로 쓸 수 있는 글꼴 목록."""
    families = []
    for name in i18n.language_fonts() + COMMON_FALLBACK_FONTS:
        if name not in families and _ensure_font_available(name):
            families.append(name)
    return families


def apply_ui_font(app):
    try:
        families = build_font_families()
        if not families:
            return
        font = QFont(app.font())
        font.setFamilies(families)
        app.setFont(font)
        for mono in MONOSPACE_FONTS:
            QFont.insertSubstitutions(mono, families)
        logging.info(f"UI font families: {families}")
    except Exception as e:
        logging.warning(f"Failed to apply UI font: {e}")
