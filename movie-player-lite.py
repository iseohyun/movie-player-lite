import sys
import os
import ctypes
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from src.utils.logger import setup_logging, APP_DIR
from src.ui.main_window import VideoCutterApp, send_to_running_instance
from src.core.lock_resolver import terminate_zombie_same_name_processes

setup_logging()

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(APP_DIR, relative_path)

def main():
    try:
        try:
            myappid = "iseohyun.movieplayerlite.1.6"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            logging.warning(f"Failed to set AppUserModelID: {e}")

        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(True)

        # 이미 실행 중인 프로세스가 있으면 파일 경로 전달 후 즉시 종료
        if send_to_running_instance(sys.argv[1:]):
            sys.exit(0)

        # IPC 서버가 응답하지 않는데 남아있는 동일 이름(이전 버전/유령) 프로세스가 있다면 정리
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
