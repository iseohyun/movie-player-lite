import re
import platform
import logging
import subprocess

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView
)
from PyQt6.QtCore import Qt, qVersion, PYQT_VERSION_STR

from src.core.metadata import get_ffmpeg_path
from src.core.i18n import tr

APP_NAME = "Movie Player Lite"
FFMPEG_QUERY_TIMEOUT_SEC = 3
UNKNOWN_VERSION = "-"


def _package_version(dist_name: str) -> str:
    try:
        from importlib.metadata import version
        return version(dist_name)
    except Exception:
        return UNKNOWN_VERSION


def _ffmpeg_version_and_license():
    """실제로 사용 중인 ffmpeg 실행 파일에서 버전과 빌드 라이선스(LGPL/GPL)를 읽는다."""
    try:
        res = subprocess.run(
            [get_ffmpeg_path(), "-version"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace",
            timeout=FFMPEG_QUERY_TIMEOUT_SEC, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        output = res.stdout or ""
    except Exception as e:
        logging.info(f"ffmpeg version query failed: {e}")
        return tr("about.not_found"), "LGPL v2.1+ / GPL v2+"

    match = re.search(r"ffmpeg version (\S+)", output)
    version = match.group(1) if match else UNKNOWN_VERSION
    is_gpl = "--enable-gpl" in output
    is_v3 = "--enable-version3" in output
    if is_gpl:
        license_name = "GPL v3+" if is_v3 else "GPL v2+"
    else:
        license_name = "LGPL v3+" if is_v3 else "LGPL v2.1+"
    return version, license_name


def collect_open_source_components():
    """이 프로그램이 사용하는 오픈소스 목록: [(이름, 버전, 라이선스), ...]"""
    ffmpeg_version, ffmpeg_license = _ffmpeg_version_and_license()
    return [
        ("Python", platform.python_version(), "PSF License 2.0"),
        ("Qt", qVersion(), "LGPL v3"),
        ("PyQt6", PYQT_VERSION_STR, "GPL v3"),
        ("PyQt6-sip", _package_version("PyQt6-sip"), "BSD 2-Clause"),
        ("FFmpeg", ffmpeg_version, ffmpeg_license),
        ("PyInstaller", _package_version("pyinstaller"), "GPL v2+ (bootloader exception)"),
    ]


class AboutDialog(QDialog):
    """프로그램 정보: 사용한 오픈소스의 이름·버전·라이선스를 나열한다."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("about.title"))
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.resize(520, 360)
        self.setStyleSheet("""
            QDialog { background-color: #252526; color: #ffffff; }
            QLabel { color: #ffffff; }
            QTableWidget { background-color: #1e1e1e; color: #dcdcdc; border: 1px solid #3e3e42; gridline-color: #3e3e42; font-size: 12px; }
            QHeaderView::section { background-color: #333333; color: #ffffff; border: none; padding: 4px; font-weight: bold; }
            QPushButton { background-color: #383838; color: white; border-radius: 4px; padding: 5px 16px; font-weight: bold; }
            QPushButton:hover { background-color: #0078d7; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(8)

        name_label = QLabel(APP_NAME)
        name_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2d89ef;")
        layout.addWidget(name_label)

        desc_label = QLabel(tr("about.description"))
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 12px; color: #c8c8c8;")
        layout.addWidget(desc_label)

        heading = QLabel(tr("about.oss_heading"))
        heading.setStyleSheet("font-size: 12px; font-weight: bold; margin-top: 6px;")
        layout.addWidget(heading)

        components = collect_open_source_components()
        self.table = QTableWidget(len(components), 3)
        self.table.setHorizontalHeaderLabels([tr("about.col_name"), tr("about.col_version"), tr("about.col_license")])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.verticalHeader().setDefaultSectionSize(26)
        for row, values in enumerate(components):
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton(tr("btn.close"))
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
