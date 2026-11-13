import sys
import os
import ctypes
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from src.utils.logger import setup_logging, APP_DIR
from src.ui.main_window import VideoCutterApp, send_to_running_instance
from src.core.lock_resolver import terminate_zombie_same_name_processes
from src.core import i18n
from src.ui.fonts import apply_ui_font

setup_logging()

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(APP_DIR, relative_path)

def install_qt_translator(app):
    """Qt 표준 대화상자(예/아니오, 색상 선택 등)의 버튼 문구를 현재 UI 언어에 맞춘다."""
    try:
        from PyQt6.QtCore import QTranslator, QLibraryInfo
        lang = i18n.current_language().replace("-", "_")
        translator = QTranslator(app)
        tr_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        if translator.load(f"qtbase_{lang}", tr_dir) or translator.load(f"qtbase_{lang.split('_')[0]}", tr_dir):
            app.installTranslator(translator)
    except Exception as e:
        logging.warning(f"Failed to install Qt translator: {e}")

def main():
    try:
        try:
            myappid = "iseohyun.mp4trim.cutter.1.6"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            logging.warning(f"Failed to set AppUserModelID: {e}")

        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(True)
        install_qt_translator(app)
        apply_ui_font(app)

        if send_to_running_instance(sys.argv[1:]):
            sys.exit(0)

        terminate_zombie_same_name_processes()
        
        icon_path = get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))

        ex = VideoCutterApp()
        if os.path.exists(icon_path):
            ex.setWindowIcon(QIcon(icon_path))

        ex.show()
        sys.exit(app.exec())
    except Exception as e:
        logging.critical("Fatal crash in main execution block!", exc_info=True)
        raise

if __name__ == "__main__":
    main()
