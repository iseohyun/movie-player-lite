"""다국어(i18n) 지원 모듈.

- 번역 파일: locales/<언어코드>.json (예: ko-KR.json, en-US.json)
- 탐색 위치: 번들 내부(locales/) + 실행 파일 옆(locales/) → 파일만 추가하면 언어가 늘어난다.
- 언어 결정 순서: 환경변수(MOVIE_PLAYER_LITE_LANG) → 사용자 설정(settings.json) → 시스템 언어 → 영어
- 언어 변경은 저장만 하고, 실제 적용은 프로그램 재시작 시점에 이뤄진다.
"""
import os
import sys
import json
import logging

SYSTEM_LANGUAGE = "system"
FALLBACK_LANGUAGE = "en-US"
LANGUAGE_ENV_VAR = "MOVIE_PLAYER_LITE_LANG"
SETTINGS_FILE_NAME = "settings.json"
LOCALES_DIR_NAME = "locales"
META_KEY = "_meta"

if getattr(sys, "frozen", False):
    _APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    _APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_catalogs = None          # {언어코드: {키: 문자열}}
_active_language = None   # 이번 실행에서 실제 사용 중인 언어코드


def _locale_dirs():
    """번들 내부 → 실행 파일 옆 순서. 뒤쪽이 같은 언어 파일을 덮어쓴다."""
    dirs = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        dirs.append(os.path.join(meipass, LOCALES_DIR_NAME))
    dirs.append(os.path.join(_APP_DIR, LOCALES_DIR_NAME))
    return dirs


def _settings_paths():
    paths = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        paths.append(os.path.join(appdata, "MP4-Trim", SETTINGS_FILE_NAME))
    paths.append(os.path.join(_APP_DIR, SETTINGS_FILE_NAME))
    return paths


def _load_catalogs():
    global _catalogs
    if _catalogs is not None:
        return _catalogs
    catalogs = {}
    for dir_path in _locale_dirs():
        if not os.path.isdir(dir_path):
            continue
        for file_name in sorted(os.listdir(dir_path)):
            if not file_name.lower().endswith(".json"):
                continue
            code = os.path.splitext(file_name)[0]
            try:
                with open(os.path.join(dir_path, file_name), "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    catalogs[code] = data
            except Exception as e:
                logging.error(f"Failed to load locale file {file_name}: {e}")
    _catalogs = catalogs
    return _catalogs


def available_languages():
    """설치된(번역 파일이 존재하는) 언어 목록: [(언어코드, 표시 이름), ...]"""
    result = []
    for code, data in _load_catalogs().items():
        meta = data.get(META_KEY)
        name = meta.get("name") if isinstance(meta, dict) else None
        result.append((code, name or code))
    return sorted(result, key=lambda item: item[1].lower())


def language_display_name(code: str) -> str:
    for lang_code, name in available_languages():
        if lang_code == code:
            return name
    return code


def language_fonts(code: str = None) -> list:
    """해당 언어 글자를 온전히 표시하는 글꼴 이름 목록 (번역 파일의 _meta.fonts, 없으면 빈 목록)."""
    meta = _load_catalogs().get(code or current_language(), {}).get(META_KEY)
    fonts = meta.get("fonts") if isinstance(meta, dict) else None
    return [f for f in fonts if isinstance(f, str)] if isinstance(fonts, list) else []


def _match_language(candidate: str):
    """'ko_KR', 'zh-Hans-CN', 'es-MX' 같은 표기를 설치된 언어코드로 대응시킨다."""
    if not candidate:
        return None
    codes = list(_load_catalogs().keys())
    wanted = candidate.replace("_", "-").lower()
    for code in codes:
        if code.lower() == wanted:
            return code
    wanted_base = wanted.split("-")[0]
    for code in sorted(codes):
        if code.lower().split("-")[0] == wanted_base:
            return code
    return None


def _system_ui_languages():
    candidates = []
    try:
        from PyQt6.QtCore import QLocale
        locale = QLocale.system()
        candidates.extend(locale.uiLanguages())
        candidates.append(locale.name())
    except Exception as e:
        logging.warning(f"Failed to query system UI languages: {e}")
    return candidates


def system_language() -> str:
    """시스템 표시 언어에 대응하는 설치된 언어코드 (없으면 영어)."""
    for candidate in _system_ui_languages():
        matched = _match_language(candidate)
        if matched:
            return matched
    return FALLBACK_LANGUAGE


def get_language_setting() -> str:
    """사용자가 저장한 값: 'system' 또는 언어코드."""
    for path in _settings_paths():
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            value = data.get("language") if isinstance(data, dict) else None
            if isinstance(value, str) and value:
                return value
        except Exception as e:
            logging.error(f"Failed to read settings from {path}: {e}")
    return SYSTEM_LANGUAGE


def set_language_setting(code: str):
    """언어 선택을 저장한다. 다른 설정 키는 보존하며, 재시작 후 적용된다."""
    for path in _settings_paths():
        try:
            data = {}
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
            data["language"] = code
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Failed to save settings to {path}: {e}")


def current_language() -> str:
    """이번 실행에서 실제 적용 중인 언어코드 (최초 호출 시 1회 결정)."""
    global _active_language
    if _active_language is None:
        override = _match_language(os.environ.get(LANGUAGE_ENV_VAR, ""))
        if override:
            _active_language = override
        else:
            setting = get_language_setting()
            matched = None if setting == SYSTEM_LANGUAGE else _match_language(setting)
            _active_language = matched or system_language()
        logging.info(f"UI language: {_active_language}")
    return _active_language


def tr(key: str, **kwargs) -> str:
    """번역 키를 현재 언어 문자열로 바꾼다. 없으면 영어, 그것도 없으면 키 자체를 반환."""
    catalogs = _load_catalogs()
    text = None
    for code in (current_language(), FALLBACK_LANGUAGE):
        value = catalogs.get(code, {}).get(key)
        if isinstance(value, str):
            text = value
            break
    if text is None:
        logging.warning(f"Missing translation key: {key}")
        return key
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception as e:
            logging.warning(f"Failed to format translation '{key}': {e}")
    return text
