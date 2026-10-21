import sys
import os
import json
import subprocess
import copy
import logging
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QRadioButton, QButtonGroup, QComboBox, QFrame, QStackedWidget,
    QListWidget, QListWidgetItem, QMenu, QMenuBar, QDialog, QFileDialog, QMessageBox,
    QInputDialog, QScrollArea, QApplication, QStyledItemDelegate, QStyle, QAbstractItemView
)
from PyQt6.QtCore import Qt, QStandardPaths, QTimer, QPropertyAnimation, QEasingCurve, QObject, QEvent, QSize, QPoint
from PyQt6.QtGui import QIcon, QKeySequence, QKeyEvent, QAction, QColor, QPen, QPixmap, QPainter
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from src.utils.logger import APP_DIR
from src.utils.time_utils import ms_to_time_str
from src.core.metadata import (
    get_ffmpeg_path, get_unique_filename, show_file_properties,
    open_source_file_dir, get_media_creation_time_and_duration
)
from src.core.hotkeys import DEFAULT_HOTKEYS, event_to_key_str
from src.core.lock_resolver import (
    norm_path_key,
    release_file_locks,
    safe_rename_with_unlock,
    safe_remove_with_unlock,
)
from src.ui.widgets.line_edit import ArrowKeyLineEdit
from src.ui.widgets.player import EmbeddedVideoPlayer
from src.ui.dialogs.key_capture import KeyCaptureDialog

SINGLE_INSTANCE_SERVER_NAME = "MoviePlayerLite_SingleInstance_IPC_v1"
HOTKEYS_SCHEMA_VERSION = 2


def create_blue_check_icon(checked: bool) -> QIcon:
    """ON/OFF 상태에 따라 메뉴 항목 왼쪽에 표시할 파란색 체크 아이콘 생성"""
    pm = QPixmap(16, 16)
    pm.fill(Qt.GlobalColor.transparent)
    if checked:
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#0078d7"))
        painter.setPen(QPen(QColor("#2d89ef"), 1))
        painter.drawRoundedRect(1, 1, 14, 14, 3, 3)
        pen = QPen(QColor("#ffffff"), 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(4, 8, 7, 11)
        painter.drawLine(7, 11, 12, 5)
        painter.end()
    return QIcon(pm)


def send_to_running_instance(file_args: list) -> bool:
    """이미 실행 중인 Movie Player Lite 프로세스가 있으면 파일 경로를 전달하고 True를 반환합니다."""
    socket = QLocalSocket()
    socket.connectToServer(SINGLE_INSTANCE_SERVER_NAME)
    if socket.waitForConnected(500):
        clean_files = []
        for f in file_args:
            cleaned = f.strip('"\'')
            if cleaned and os.path.isfile(cleaned):
                clean_files.append(os.path.abspath(os.path.normpath(cleaned)).replace('\\', '/'))
        payload = json.dumps({"files": clean_files}, ensure_ascii=False).encode("utf-8")
        socket.write(payload)
        socket.flush()
        socket.waitForBytesWritten(1000)
        socket.waitForReadyRead(1500)
        socket.disconnectFromServer()
        return True
    return False


def get_user_data_path(file_name: str) -> str:
    appdata = os.environ.get('APPDATA')
    if appdata:
        dir_path = os.path.join(appdata, "MP4-Trim")
        os.makedirs(dir_path, exist_ok=True)
        return os.path.join(dir_path, file_name)
    return os.path.join(APP_DIR, file_name)


def save_app_data_json(file_name: str, data):
    paths = [get_user_data_path(file_name), os.path.join(APP_DIR, file_name)]
    for p in paths:
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Failed to save JSON to {p}: {e}")


def load_app_data_json(file_name: str):
    paths = [get_user_data_path(file_name), os.path.join(APP_DIR, file_name)]
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Failed to load JSON from {p}: {e}")
    return None


class FocusOutFilter(QObject):
    def __init__(self, target_widget, parent=None):
        super().__init__(parent)
        self.target_widget = target_widget

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.FocusOut:
            QTimer.singleShot(50, self.check_focus)
        return super().eventFilter(obj, event)

    def check_focus(self):
        from PyQt6.QtWidgets import QLineEdit, QComboBox, QListWidget, QTableWidget
        focus_w = QApplication.focusWidget()
        if focus_w is None or (not isinstance(focus_w, (QLineEdit, QComboBox, QListWidget, QTableWidget))
                               and not focus_w.inherits("QLineEdit")
                               and not focus_w.inherits("QComboBox")
                               and not focus_w.inherits("QListWidget")
                               and not focus_w.inherits("QTableWidget")):
            if self.target_widget:
                self.target_widget.setFocus()


class PlaylistDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        rect = option.rect

        bg_brush = index.data(Qt.ItemDataRole.BackgroundRole)
        fg_brush = index.data(Qt.ItemDataRole.ForegroundRole)
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)

        if is_selected:
            painter.fillRect(rect, QColor('#0078d7'))
            painter.setPen(QColor('#ffffff'))
        elif bg_brush:
            painter.fillRect(rect, bg_brush.color())
            painter.setPen(fg_brush.color() if fg_brush else QColor('#ffffff'))
        else:
            painter.fillRect(rect, QColor('#1e1e1e'))
            painter.setPen(QColor('#ffffff'))

        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        text_rect = rect.adjusted(8, 0, -8, 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)

        painter.setPen(QPen(QColor('#282828'), 1))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        painter.restore()


class CustomPlaylistListWidget(QListWidget):
    def __init__(self, main_app=None, parent=None):
        super().__init__(parent)
        self.main_app = main_app

    def keyPressEvent(self, event: QKeyEvent):
        main_win = self.main_app or self.window()
        if event.key() == Qt.Key.Key_F2:
            if hasattr(main_win, 'rename_selected_playlist_file'):
                main_win.rename_selected_playlist_file()
                return
        elif event.key() == Qt.Key.Key_Delete:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                if hasattr(main_win, 'delete_selected_playlist_file_permanently'):
                    main_win.delete_selected_playlist_file_permanently()
                    return
            else:
                if hasattr(main_win, 'remove_selected_playlist_item'):
                    main_win.remove_selected_playlist_item()
                    return
        super().keyPressEvent(event)


class FloatingModalDialog(QDialog):
    """비모달 플로팅 창 (편집 모달 / 리스트 모달용): Z축 계층 우선순위 및 단축키 전달 지원"""
    def __init__(self, main_app, title: str, z_priority: int = 1, parent=None):
        super().__init__(parent or main_app)
        self.main_app = main_app
        self.z_order_priority = z_priority
        self.setWindowTitle(title)
        flags = (
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )
        if z_priority >= 2:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self.main_app, 'on_modal_visibility_changed'):
            self.main_app.on_modal_visibility_changed()

    def hideEvent(self, event):
        super().hideEvent(event)
        if hasattr(self.main_app, 'on_modal_visibility_changed'):
            self.main_app.on_modal_visibility_changed()

    def closeEvent(self, event):
        super().closeEvent(event)
        if hasattr(self.main_app, 'on_modal_visibility_changed'):
            QTimer.singleShot(0, self.main_app.on_modal_visibility_changed)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            if hasattr(self.main_app, 'ensure_modal_z_order'):
                QTimer.singleShot(10, self.main_app.ensure_modal_z_order)

    def keyPressEvent(self, event: QKeyEvent):
        focus_w = QApplication.focusWidget()
        if not isinstance(focus_w, QLineEdit) and hasattr(self.main_app, 'keyPressEvent'):
            self.main_app.keyPressEvent(event)
            return
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)


def set_win32_window_rounding(win_id: int, enable_rounding: bool = False):
    try:
        import ctypes
        from ctypes import c_int, byref
        preference = c_int(2 if enable_rounding else 1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            c_int(win_id),
            c_int(33),
            byref(preference),
            ctypes.sizeof(preference)
        )
    except Exception:
        pass


class VideoCutterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.task_histories = []
        self.create_history_flag = True
        self.is_loading_history = False
        self.is_loading_file = False
        self.last_enter_name = ""
        self.original_duration_cs = 35999999
        self.original_creation_dt = None
        self._auto_play_next_load = False
        self.playlist_file_ids = {}
        self.local_server = None
        self.fullscreen_stage = 0

        self.default_dir = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.MoviesLocation
        )
        if not self.default_dir:
            self.default_dir = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.HomeLocation
            )

        self.load_hotkeys()
        self.initUI()
        self.load_history()
        self.load_task_history()
        self.load_playlist_history()
        self.init_single_instance_server()
        self.init_external_file_watcher()

        if len(sys.argv) > 1:
            valid_args = [a.strip('"\'') for a in sys.argv[1:] if os.path.isfile(a.strip('"\''))]
            if valid_args:
                for extra_file in valid_args[1:]:
                    self.add_file_to_playlist(extra_file, load_immediately=False, save_history=True)
                self.open_and_play_external_file(valid_args[0])

    def load_hotkeys(self):
        self.hotkeys_file = os.path.join(APP_DIR, "hotkeys.json")
        self.hotkeys = copy.deepcopy(DEFAULT_HOTKEYS)
        if os.path.exists(self.hotkeys_file):
            try:
                with open(self.hotkeys_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        if data.get("_schema_version") == HOTKEYS_SCHEMA_VERSION:
                            for k, v in data.items():
                                if k in self.hotkeys and isinstance(v, dict):
                                    self.hotkeys[k]["primary"] = v.get("primary", self.hotkeys[k]["primary"])
                                    self.hotkeys[k]["secondary"] = v.get("secondary", self.hotkeys[k]["secondary"])
                        else:
                            self.save_hotkeys()
            except Exception as e:
                logging.error(f"Failed to load hotkeys: {e}")

    def save_hotkeys(self):
        try:
            payload = {"_schema_version": HOTKEYS_SCHEMA_VERSION}
            payload.update(self.hotkeys)
            with open(self.hotkeys_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Failed to save hotkeys: {e}")

    def initUI(self):
        icon_path = os.path.join(APP_DIR, "dist", "icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(APP_DIR, "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setWindowTitle("Movie Player Lite")
        self.setAcceptDrops(True)

        screen = QApplication.primaryScreen()
        if screen:
            rect = screen.availableGeometry()
            w = max(850, rect.width() // 2)
            h = max(600, rect.height() // 2)
            x = rect.x() + (rect.width() - w) // 2
            y = rect.y() + (rect.height() - h) // 2
            self.setGeometry(x, y, w, h)
        else:
            self.resize(850, 600)
        self.setMinimumSize(640, 420)
        self.setStyleSheet("VideoCutterApp { background-color: #000000; }")

        # 최소한의 베젤(여백 0px)로 메인 플레이어 100% 배치
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.player_widget = EmbeddedVideoPlayer(self)
        root_layout.addWidget(self.player_widget, 1)

        # 상단 오버레이 메뉴바 (기본 숨김, Alt 키 및 마우스 감지 시 표시)
        self.build_top_menu_bar()

        # -------------------------------------------------------------
        # 1. 편집 모달 (기본 모달, Z-Priority = 1, 열려 있을 때 재생바 고정 표시)
        # -------------------------------------------------------------
        self.edit_modal = FloatingModalDialog(self, "편집 및 저장 설정 (단축키: E)", z_priority=1, parent=self)
        self.edit_modal.resize(310, 440)
        self.edit_modal.setStyleSheet("""
            QDialog { background-color: #252526; color: white; }
            QLabel { color: white; font-weight: bold; }
            QLineEdit { background-color: #1e1e1e; color: white; border: 1px solid #333; border-radius: 4px; padding: 4px; }
            QComboBox { background-color: #1e1e1e; color: white; border: 1px solid #333; border-radius: 4px; padding: 4px; }
            QCheckBox, QRadioButton { color: #dcdcdc; }
            QPushButton { background-color: #3e3e42; color: white; border-radius: 4px; padding: 4px 8px; }
            QPushButton:hover { background-color: #0078d7; }
        """)
        self.option_sidebar = self.edit_modal  # 하위 호환성 별칭

        opt_layout = QVBoxLayout(self.edit_modal)
        opt_layout.setContentsMargins(10, 10, 10, 10)
        opt_layout.setSpacing(8)

        opt_header = QHBoxLayout()
        opt_title = QLabel("컷팅 & 편집 설정 (단축키: E)")
        opt_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #2d89ef;")
        self.hotkey_btn = QPushButton("⌨")
        self.hotkey_btn.setToolTip("단축키 설정 열기")
        self.hotkey_btn.setFixedSize(26, 26)
        self.hotkey_btn.clicked.connect(self.open_hotkey_modal)
        opt_header.addWidget(opt_title, 1)
        opt_header.addWidget(self.hotkey_btn, 0)
        opt_layout.addLayout(opt_header)

        # 시작/종료 시각 입력 필드
        self.fileInput = QLineEdit()
        self.fileInput.textChanged.connect(self.on_file_changed)
        self.startInput = ArrowKeyLineEdit("00:00:00.00")
        self.endInput = ArrowKeyLineEdit("00:00:00.00")

        time_range_box = QHBoxLayout()
        time_range_box.addWidget(QLabel("구간:"))
        time_range_box.addWidget(self.startInput, 1)
        time_range_box.addWidget(QLabel("~"))
        time_range_box.addWidget(self.endInput, 1)
        opt_layout.addLayout(time_range_box)

        # 저장 파일명 (.mp4 생략 표시) + 컷팅 버튼
        name_box = QHBoxLayout()
        self.nameInput = QLineEdit("output")
        self.nameInput.textChanged.connect(self.on_input_modified)
        self.nameInput.returnPressed.connect(self.on_name_input_enter)
        self.nameInput.textChanged.connect(self.update_name_input_style)
        self.playOutBtn = QPushButton("컷팅")
        self.playOutBtn.setToolTip("무손실 컷팅 실행 / 저장 영상 재생")
        self.playOutBtn.clicked.connect(self.on_cut_or_play_clicked)
        name_box.addWidget(self.nameInput, 1)
        name_box.addWidget(self.playOutBtn, 0)

        opt_layout.addWidget(QLabel("저장 파일명"))
        opt_layout.addLayout(name_box)

        # 저장 옵션
        self.muteCheck = QCheckBox("음소거 (영상만 가져오기)")
        self.copyMetaCheck = QCheckBox("속성 복사")
        self.copyMetaCheck.setChecked(True)
        self.autoNumberCheck = QCheckBox("자동 넘버링")
        self.autoNumberCheck.setChecked(False)
        self.hudCheck = QCheckBox("동영상 상세 정보 HUD 표시 (`)")
        self.hudCheck.toggled.connect(self.on_hud_check_toggled)
        opt_layout.addWidget(self.muteCheck)
        opt_layout.addWidget(self.copyMetaCheck)
        opt_layout.addWidget(self.autoNumberCheck)
        opt_layout.addWidget(self.hudCheck)

        # 저장 위치
        opt_layout.addWidget(QLabel("저장 위치"))
        self.radioSame = QRadioButton("동일 경로 (../)")
        self.radioOutput = QRadioButton("output 폴더 (../output/)")
        self.radioCustom = QRadioButton("사용자 지정 (custom)")
        self.radioGroup = QButtonGroup(self)
        self.radioGroup.addButton(self.radioSame)
        self.radioGroup.addButton(self.radioOutput)
        self.radioGroup.addButton(self.radioCustom)
        opt_layout.addWidget(self.radioSame)
        opt_layout.addWidget(self.radioOutput)
        opt_layout.addWidget(self.radioCustom)

        dir_box = QHBoxLayout()
        self.dirInput = QLineEdit()
        self.dirInput.textChanged.connect(self.on_input_modified)
        self.dirBtn = QPushButton("선택")
        self.dirBtn.clicked.connect(self.openDirDialog)
        dir_box.addWidget(self.dirInput, 1)
        dir_box.addWidget(self.dirBtn, 0)
        opt_layout.addWidget(QLabel("저장 경로"))
        opt_layout.addLayout(dir_box)

        combo_style = """
            QComboBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 4px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e1e1e;
                color: #ffffff;
                selection-background-color: #0078d7;
                selection-color: white;
            }
        """

        opt_layout.addWidget(QLabel("작업 히스토리"))
        self.taskHistoryCombo = QComboBox()
        self.taskHistoryCombo.setStyleSheet(combo_style)
        self.taskHistoryCombo.currentIndexChanged.connect(self.on_task_history_selected)
        opt_layout.addWidget(self.taskHistoryCombo)

        opt_layout.addWidget(QLabel("최근 작업 폴더"))
        hist_box = QHBoxLayout()
        self.historyCombo = QComboBox()
        self.historyCombo.setStyleSheet(combo_style)
        self.historyCombo.currentIndexChanged.connect(self.on_history_combo_changed)
        self.openDirBtn = QPushButton("열기")
        self.openDirBtn.clicked.connect(self.open_current_directory)
        hist_box.addWidget(self.historyCombo, 1)
        hist_box.addWidget(self.openDirBtn, 0)
        opt_layout.addLayout(hist_box)
        opt_layout.addStretch()

        self.player_widget.trimming_slider.start_changed.connect(self.on_trim_start_changed)
        self.player_widget.trimming_slider.end_changed.connect(self.on_trim_end_changed)
        self.player_widget.trimming_slider.region_selected.connect(self.on_timeline_region_selected)
        self.player_widget.trimming_slider.region_rename_requested.connect(self.on_timeline_region_rename)
        self.player_widget.trimming_slider.region_delete_requested.connect(self.on_timeline_region_delete)
        self.startInput.textChanged.connect(self.on_start_input_text_changed)
        self.endInput.textChanged.connect(self.on_end_input_text_changed)

        # -------------------------------------------------------------
        # 2. 리스트 모달 (기본 모달보다 Z축 상위에 출력, Z-Priority = 2)
        # -------------------------------------------------------------
        self.playlist_files = []
        self.playlist_modal = FloatingModalDialog(self, "재생 목록 (단축키: P)", z_priority=2, parent=self)
        self.playlist_modal.resize(280, 420)
        self.playlist_modal.setStyleSheet("""
            QDialog { background-color: #252526; color: white; }
            QLabel { color: white; font-weight: bold; }
            QListWidget { background-color: #1e1e1e; color: #dcdcdc; border: 1px solid #333; border-radius: 4px; outline: none; }
            QListWidget::item { padding: 3px 5px; margin: 0px; border-bottom: 1px solid #2a2a2a; font-size: 12px; }
            QListWidget::item:hover { background-color: #2a2d32; }
            QListWidget::item:selected { background-color: #0078d7; color: white; }
        """)
        self.playlist_sidebar = self.playlist_modal  # 하위 호환성 별칭

        sidebar_layout = QVBoxLayout(self.playlist_modal)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)

        sb_header = QHBoxLayout()
        sb_title = QLabel("재생 목록 (단축키: P)")
        self.add_file_btn = QPushButton("+ 추가")
        self.add_file_btn.setStyleSheet("background-color: #2d89ef; color: white; padding: 4px 8px; font-weight: bold; border-radius: 4px;")
        self.add_file_btn.clicked.connect(self.openFileDialog)
        sb_header.addWidget(sb_title)
        sb_header.addStretch()
        sb_header.addWidget(self.add_file_btn)
        sidebar_layout.addLayout(sb_header)

        self.playlist_widget = CustomPlaylistListWidget(main_app=self, parent=self.playlist_modal)
        self.playlist_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.playlist_widget.setItemDelegate(PlaylistDelegate(self.playlist_widget))
        self.playlist_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.playlist_widget.customContextMenuRequested.connect(self.on_playlist_context_menu)
        self.playlist_widget.itemDoubleClicked.connect(self.on_playlist_item_double_clicked)
        sidebar_layout.addWidget(self.playlist_widget, 1)

        # -------------------------------------------------------------
        # 3. 단축키 설정 모달
        # -------------------------------------------------------------
        self.hotkey_modal = QDialog(self)
        self.hotkey_modal.setWindowTitle("단축키 설정")
        self.hotkey_modal.resize(360, 480)
        self.hotkey_modal.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        hk_modal_layout = QVBoxLayout(self.hotkey_modal)
        hk_modal_layout.setContentsMargins(0, 0, 0, 0)
        hk_modal_layout.addWidget(self.build_hotkey_settings_page())

        # Radio buttons connections
        self.radioSame.toggled.connect(self.on_radio_changed)
        self.radioOutput.toggled.connect(self.on_radio_changed)
        self.radioCustom.toggled.connect(self.on_radio_changed)
        self.radioOutput.setChecked(True)

        self.fileInput.textChanged.connect(self.on_input_modified)
        self.startInput.textChanged.connect(self.on_input_modified)
        self.endInput.textChanged.connect(self.on_input_modified)
        self.nameInput.textChanged.connect(self.on_input_modified)
        self.dirInput.textChanged.connect(self.on_input_modified)
        self.muteCheck.stateChanged.connect(self.on_input_modified)
        self.copyMetaCheck.stateChanged.connect(self.on_input_modified)
        self.autoNumberCheck.stateChanged.connect(self.on_input_modified)
        self.radioSame.toggled.connect(self.on_input_modified)
        self.radioOutput.toggled.connect(self.on_input_modified)
        self.radioCustom.toggled.connect(self.on_input_modified)

        # 포커스 아웃 필터 등록
        self.focus_filter = FocusOutFilter(self.player_widget.trimming_slider, self)
        self.nameInput.installEventFilter(self.focus_filter)
        self.dirInput.installEventFilter(self.focus_filter)
        self.startInput.installEventFilter(self.focus_filter)
        self.endInput.installEventFilter(self.focus_filter)
        self.taskHistoryCombo.installEventFilter(self.focus_filter)
        self.historyCombo.installEventFilter(self.focus_filter)

        self.sync_menu_check_states()
        self.player_widget.apply_auto_hide_settings()

    def build_top_menu_bar(self):
        """상단 오버레이 메뉴바 (파일 / 재생 / 화면 / 설정 / 조작) 구성"""
        self.top_menu_bar = QMenuBar(self.player_widget)
        self.top_menu_bar.setFixedHeight(28)
        self.top_menu_bar.setStyleSheet("""
            QMenuBar {
                background-color: rgba(25, 25, 28, 0.92);
                color: #ffffff;
                border-bottom: 1px solid rgba(255, 255, 255, 0.12);
                font-size: 12px;
                padding: 2px 6px;
            }
            QMenuBar::item {
                background: transparent;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background-color: #0078d7;
                color: #ffffff;
            }
            QMenu {
                background-color: #252526;
                color: #ffffff;
                border: 1px solid #444444;
                padding: 4px;
                font-size: 12px;
            }
            QMenu::item {
                padding: 5px 24px 5px 10px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #0078d7;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background: #3e3e42;
                margin: 4px 6px;
            }
        """)

        # 1. 파일 메뉴
        self.file_menu = self.top_menu_bar.addMenu("파일(&F)")
        self.act_open_file = QAction("열기", self)
        self.act_open_file.triggered.connect(self.openFileDialog)
        self.act_show_playlist = QAction("리스트 보기 (P)", self)
        self.act_show_playlist.triggered.connect(lambda: self.toggle_playlist_modal())
        self.file_menu.addAction(self.act_open_file)
        self.file_menu.addAction(self.act_show_playlist)

        # 2. 재생 메뉴
        self.play_menu = self.top_menu_bar.addMenu("재생(&P)")
        self.speed_menu = self.play_menu.addMenu("배속")
        self.speed_actions = {}
        for spd in (0.5, 1.0, 1.25, 1.50, 1.75, 2.00, 3.00):
            label = f"{spd:.2f}배" if spd not in (0.5, 1.0) else f"{spd:g}배"
            act = QAction(label, self)
            act.triggered.connect(lambda _, r=spd: self.player_widget.set_playback_rate(r))
            self.speed_menu.addAction(act)
            self.speed_actions[spd] = act

        self.act_speed_up = QAction("+0.25배속 (+)", self)
        self.act_speed_up.triggered.connect(lambda: self.player_widget.change_playback_rate(0.25))
        self.act_speed_down = QAction("-0.25배속 (-)", self)
        self.act_speed_down.triggered.connect(lambda: self.player_widget.change_playback_rate(-0.25))
        self.act_speed_reset = QAction("기본배속으로 (0)", self)
        self.act_speed_reset.triggered.connect(self.player_widget.reset_playback_rate)

        self.play_menu.addAction(self.act_speed_up)
        self.play_menu.addAction(self.act_speed_down)
        self.play_menu.addAction(self.act_speed_reset)
        self.play_menu.addSeparator()

        self.act_play_pause = QAction("멈춤/재생 (Space)", self)
        self.act_play_pause.triggered.connect(self.player_widget.toggle_play)
        self.act_step_1s_prev = QAction("1초 전 (←)", self)
        self.act_step_1s_prev.triggered.connect(lambda: self.player_widget.step_time(-1000))
        self.act_step_1s_next = QAction("1초 후 (→)", self)
        self.act_step_1s_next.triggered.connect(lambda: self.player_widget.step_time(1000))
        self.act_step_5s_prev = QAction("5초 전 (Shift+←)", self)
        self.act_step_5s_prev.triggered.connect(lambda: self.player_widget.step_time(-5000))
        self.act_step_5s_next = QAction("5초 후 (Shift+→)", self)
        self.act_step_5s_next.triggered.connect(lambda: self.player_widget.step_time(5000))
        self.act_frame_prev = QAction("1프레임 전 (<)", self)
        self.act_frame_prev.triggered.connect(lambda: self.player_widget.step_frame(forward=False))
        self.act_frame_next = QAction("1프레임 후 (>)", self)
        self.act_frame_next.triggered.connect(lambda: self.player_widget.step_frame(forward=True))

        self.play_menu.addAction(self.act_play_pause)
        self.play_menu.addAction(self.act_step_1s_prev)
        self.play_menu.addAction(self.act_step_1s_next)
        self.play_menu.addAction(self.act_step_5s_prev)
        self.play_menu.addAction(self.act_step_5s_next)
        self.play_menu.addAction(self.act_frame_prev)
        self.play_menu.addAction(self.act_frame_next)
        self.play_menu.addSeparator()

        self.act_prev_video = QAction("이전 동영상 (PgUp / [)", self)
        self.act_prev_video.triggered.connect(self.play_prev_video)
        self.act_next_video = QAction("다음 동영상 (PgDown / ])", self)
        self.act_next_video.triggered.connect(self.play_next_video)
        self.play_menu.addAction(self.act_prev_video)
        self.play_menu.addAction(self.act_next_video)
        self.play_menu.addSeparator()

        self.act_vol_up = QAction("볼륨 올리기 (↑)", self)
        self.act_vol_up.triggered.connect(lambda: self.player_widget.change_volume(0.05))
        self.act_vol_down = QAction("볼륨 내리기 (↓)", self)
        self.act_vol_down.triggered.connect(lambda: self.player_widget.change_volume(-0.05))
        self.act_toggle_mute = QAction("음소거 (M)", self)
        self.act_toggle_mute.triggered.connect(self.player_widget.toggle_mute)
        self.play_menu.addAction(self.act_vol_up)
        self.play_menu.addAction(self.act_vol_down)
        self.play_menu.addAction(self.act_toggle_mute)

        # 3. 화면 메뉴
        self.view_menu = self.top_menu_bar.addMenu("화면(&V)")
        self.act_zoom_in = QAction("확대 (Ctrl++)", self)
        self.act_zoom_in.triggered.connect(lambda: self.player_widget.zoom_in())
        self.act_zoom_out = QAction("축소 (Ctrl+-)", self)
        self.act_zoom_out.triggered.connect(lambda: self.player_widget.zoom_out())

        self.pan_menu = self.view_menu.addMenu("확대시 이동 (Ctrl+방향키)")
        act_pan_up = QAction("위로 이동 (Ctrl+↑)", self)
        act_pan_up.triggered.connect(lambda: self.player_widget.pan_view(0, -20))
        act_pan_down = QAction("아래로 이동 (Ctrl+↓)", self)
        act_pan_down.triggered.connect(lambda: self.player_widget.pan_view(0, 20))
        act_pan_left = QAction("왼쪽 이동 (Ctrl+←)", self)
        act_pan_left.triggered.connect(lambda: self.player_widget.pan_view(-20, 0))
        act_pan_right = QAction("오른쪽 이동 (Ctrl+→)", self)
        act_pan_right.triggered.connect(lambda: self.player_widget.pan_view(20, 0))
        act_zoom_reset = QAction("확대/위치 초기화 (Ctrl+0)", self)
        act_zoom_reset.triggered.connect(self.player_widget.reset_zoom_pan)
        self.pan_menu.addAction(act_pan_up)
        self.pan_menu.addAction(act_pan_down)
        self.pan_menu.addAction(act_pan_left)
        self.pan_menu.addAction(act_pan_right)
        self.pan_menu.addSeparator()
        self.pan_menu.addAction(act_zoom_reset)

        self.view_menu.addAction(self.act_zoom_in)
        self.view_menu.addAction(self.act_zoom_out)
        self.view_menu.addMenu(self.pan_menu)
        self.view_menu.addSeparator()

        self.act_rot_right = QAction("화면 오른쪽 회전 (R)", self)
        self.act_rot_right.triggered.connect(self.player_widget.rotate_right)
        self.act_rot_left = QAction("화면 왼쪽 회전 (L)", self)
        self.act_rot_left.triggered.connect(self.player_widget.rotate_left)
        self.act_flip_h = QAction("화면 좌우반전 (H)", self)
        self.act_flip_h.triggered.connect(self.player_widget.flip_horizontal)
        self.act_flip_v = QAction("화면 상하반전 (V)", self)
        self.act_flip_v.triggered.connect(self.player_widget.flip_vertical)

        self.view_menu.addAction(self.act_rot_right)
        self.view_menu.addAction(self.act_rot_left)
        self.view_menu.addAction(self.act_flip_h)
        self.view_menu.addAction(self.act_flip_v)
        self.view_menu.addSeparator()

        self.act_screen_normal = QAction("기본화면 (Esc)", self)
        self.act_screen_normal.triggered.connect(lambda: self.set_screen_mode(0))
        self.act_screen_full = QAction("전체화면 (F)", self)
        self.act_screen_full.triggered.connect(lambda: self.set_screen_mode(2))
        self.act_screen_stretch = QAction("꽉찬화면", self)
        self.act_screen_stretch.triggered.connect(lambda: self.set_screen_mode(3))

        self.view_menu.addAction(self.act_screen_normal)
        self.view_menu.addAction(self.act_screen_full)
        self.view_menu.addAction(self.act_screen_stretch)
        self.view_menu.addSeparator()

        self.act_toggle_time = QAction("시간/상태 정보 표시 (T)", self)
        self.act_toggle_time.triggered.connect(self.player_widget.toggle_time_label)
        self.act_toggle_hud = QAction("상세 설정 정보 표시 (`)", self)
        self.act_toggle_hud.triggered.connect(self.player_widget.toggle_hud_overlay)
        self.act_show_props = QAction("동영상 속성 모달 보기 (?)", self)
        self.act_show_props.triggered.connect(self.view_source_properties)

        self.view_menu.addAction(self.act_toggle_time)
        self.view_menu.addAction(self.act_toggle_hud)
        self.view_menu.addAction(self.act_show_props)

        # 4. 설정 메뉴
        self.settings_menu = self.top_menu_bar.addMenu("설정(&S)")
        self.act_open_hotkeys = QAction("단축키", self)
        self.act_open_hotkeys.triggered.connect(self.open_hotkey_modal)
        self.act_auto_hide_timeline = QAction("재생바 기본숨김", self)
        self.act_auto_hide_timeline.triggered.connect(self.toggle_auto_hide_timeline)
        self.act_auto_hide_menubar = QAction("메뉴바 기본숨김", self)
        self.act_auto_hide_menubar.triggered.connect(self.toggle_auto_hide_menubar)

        self.settings_menu.addAction(self.act_open_hotkeys)
        self.settings_menu.addAction(self.act_auto_hide_timeline)
        self.settings_menu.addAction(self.act_auto_hide_menubar)

        # 5. 조작 메뉴
        self.action_menu = self.top_menu_bar.addMenu("조작(&E)")
        self.act_open_edit_modal = QAction("편집 모달 호출 (E)", self)
        self.act_open_edit_modal.triggered.connect(lambda: self.toggle_edit_modal())
        self.action_menu.addAction(self.act_open_edit_modal)

        self.top_menu_bar.hide()

    def layout_top_menu_bar(self):
        if hasattr(self, 'top_menu_bar') and self.top_menu_bar and hasattr(self, 'player_widget'):
            self.top_menu_bar.setGeometry(0, 0, self.player_widget.width(), 28)
            self.top_menu_bar.raise_()

    def sync_menu_check_states(self):
        """ON/OFF 토글 항목들의 파란색 체크 아이콘 동기화"""
        if not hasattr(self, 'act_auto_hide_timeline'):
            return
        self.act_auto_hide_timeline.setIcon(create_blue_check_icon(self.player_widget.auto_hide_timeline))
        self.act_auto_hide_menubar.setIcon(create_blue_check_icon(self.player_widget.auto_hide_menubar))
        self.act_toggle_time.setIcon(create_blue_check_icon(self.player_widget.show_time_label))
        self.act_toggle_hud.setIcon(create_blue_check_icon(self.player_widget.force_hud_visible))
        self.act_toggle_mute.setIcon(create_blue_check_icon(self.player_widget.audio_output.isMuted()))
        for spd, act in self.speed_actions.items():
            act.setIcon(create_blue_check_icon(abs(self.player_widget.playback_rate - spd) < 1e-3))

        stage = getattr(self, 'fullscreen_stage', 0)
        self.act_screen_normal.setIcon(create_blue_check_icon(stage == 0))
        self.act_screen_full.setIcon(create_blue_check_icon(stage in (1, 2)))
        self.act_screen_stretch.setIcon(create_blue_check_icon(stage == 3))

    def toggle_auto_hide_timeline(self):
        self.player_widget.auto_hide_timeline = not self.player_widget.auto_hide_timeline
        self.sync_menu_check_states()
        self.player_widget.apply_auto_hide_settings()
        self.show_toast("재생바 기본숨김 ON" if self.player_widget.auto_hide_timeline else "재생바 기본숨김 OFF (항상 표시)")

    def toggle_auto_hide_menubar(self):
        self.player_widget.auto_hide_menubar = not self.player_widget.auto_hide_menubar
        self.sync_menu_check_states()
        self.player_widget.apply_auto_hide_settings()
        self.show_toast("메뉴바 기본숨김 ON" if self.player_widget.auto_hide_menubar else "메뉴바 기본숨김 OFF (항상 표시)")

    def show_player_context_menu(self, global_pos: QPoint):
        ctx = QMenu(self)
        ctx.setStyleSheet(self.top_menu_bar.styleSheet())
        ctx.addMenu(self.file_menu)
        ctx.addMenu(self.play_menu)
        ctx.addMenu(self.view_menu)
        ctx.addMenu(self.settings_menu)
        ctx.addMenu(self.action_menu)
        ctx.exec(global_pos)

    def ensure_modal_z_order(self):
        """리스트 모달(Z=2)이 편집 모달(Z=1)보다 항상 Z축 상위에 출력되도록 보장"""
        if hasattr(self, 'playlist_modal') and self.playlist_modal and self.playlist_modal.isVisible():
            self.playlist_modal.raise_()
            if os.name == "nt":
                try:
                    import ctypes
                    SWP_NOSIZE = 0x0001
                    SWP_NOMOVE = 0x0002
                    SWP_NOACTIVATE = 0x0010
                    HWND_TOPMOST = -1
                    ctypes.windll.user32.SetWindowPos(
                        int(self.playlist_modal.winId()),
                        HWND_TOPMOST,
                        0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
                    )
                except Exception:
                    pass

    def on_modal_visibility_changed(self):
        if hasattr(self, 'player_widget') and self.player_widget:
            self.player_widget.edit_modal_pinned = bool(hasattr(self, 'edit_modal') and self.edit_modal.isVisible())
            self.player_widget.apply_auto_hide_settings()
        self.ensure_modal_z_order()

    def toggle_edit_modal(self, force_open: bool = None):
        should_open = (not self.edit_modal.isVisible()) if force_open is None else bool(force_open)
        if not should_open:
            self.edit_modal.hide()
        else:
            g = self.geometry()
            self.edit_modal.move(max(10, g.left() + 20), max(40, g.top() + 50))
            self.edit_modal.show()
            self.edit_modal.raise_()
            self.ensure_modal_z_order()
        self.on_modal_visibility_changed()

    def toggle_playlist_modal(self, force_open: bool = None):
        should_open = (not self.playlist_modal.isVisible()) if force_open is None else bool(force_open)
        if not should_open:
            self.playlist_modal.hide()
        else:
            g = self.geometry()
            self.playlist_modal.move(max(10, g.right() - self.playlist_modal.width() - 20), max(40, g.top() + 50))
            self.playlist_modal.show()
            self.playlist_modal.raise_()
            self.ensure_modal_z_order()

    def open_hotkey_modal(self):
        self.refresh_hotkey_table()
        self.hotkey_modal.exec()

    def play_prev_video(self):
        cnt = self.playlist_widget.count()
        if cnt <= 0:
            return
        cur_row = self.playlist_widget.currentRow()
        target_row = (cur_row - 1) % cnt if cur_row >= 0 else 0
        it = self.playlist_widget.item(target_row)
        if it:
            path = it.data(Qt.ItemDataRole.UserRole)
            if path and os.path.isfile(path):
                self.open_and_play_external_file(path)

    def play_next_video(self):
        cnt = self.playlist_widget.count()
        if cnt <= 0:
            return
        cur_row = self.playlist_widget.currentRow()
        target_row = (cur_row + 1) % cnt if cur_row >= 0 else 0
        it = self.playlist_widget.item(target_row)
        if it:
            path = it.data(Qt.ItemDataRole.UserRole)
            if path and os.path.isfile(path):
                self.open_and_play_external_file(path)

    def build_hotkey_settings_page(self):
        opt_hotkey_page = QWidget()
        opt_hotkey_page.setStyleSheet("QWidget { background-color: #252526; color: white; }")
        hk_layout = QVBoxLayout(opt_hotkey_page)
        hk_layout.setContentsMargins(10, 10, 10, 10)
        hk_layout.setSpacing(6)

        hk_header = QHBoxLayout()
        self.hk_back_btn = QPushButton("닫기")
        self.hk_back_btn.setStyleSheet("""
            QPushButton { background-color: #383838; color: white; border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: bold; }
            QPushButton:hover { background-color: #0078d7; }
        """)
        self.hk_back_btn.clicked.connect(lambda: self.hotkey_modal.close() if hasattr(self, 'hotkey_modal') else None)

        hk_title = QLabel("단축키 설정")
        hk_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #2d89ef;")

        self.hk_reset_btn = QPushButton("초기화")
        self.hk_reset_btn.setStyleSheet("""
            QPushButton { background-color: #552222; color: white; border-radius: 4px; padding: 3px 6px; font-size: 11px; }
            QPushButton:hover { background-color: #d13438; }
        """)
        self.hk_reset_btn.clicked.connect(self.reset_hotkeys_to_default)

        hk_header.addWidget(self.hk_back_btn, 0)
        hk_header.addStretch()
        hk_header.addWidget(hk_title, 0)
        hk_header.addStretch()
        hk_header.addWidget(self.hk_reset_btn, 0)
        hk_layout.addLayout(hk_header)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #252526; }")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("QWidget { background-color: #252526; color: white; }")
        self.hotkey_list_layout = QVBoxLayout(scroll_content)
        self.hotkey_list_layout.setContentsMargins(0, 0, 0, 0)
        self.hotkey_list_layout.setSpacing(4)

        scroll_area.setWidget(scroll_content)
        hk_layout.addWidget(scroll_area, 1)

        self.refresh_hotkey_table()
        return opt_hotkey_page

    def refresh_hotkey_table(self):
        while self.hotkey_list_layout.count():
            child = self.hotkey_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for action_id, info in self.hotkeys.items():
            row_frame = QFrame()
            row_frame.setStyleSheet("QFrame { background-color: #1e1e1e; border-radius: 4px; }")
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(6, 4, 6, 4)
            row_layout.setSpacing(4)

            name_lbl = QLabel(info['name'])
            name_lbl.setStyleSheet("font-size: 11px; color: #dcdcdc; font-weight: normal;")
            row_layout.addWidget(name_lbl, 1)

            btn_p = QPushButton(info['primary'] if info['primary'] else "None")
            btn_p.setFixedWidth(65)
            btn_p.setToolTip("기본 단축키 변경")
            btn_p.setStyleSheet("""
                QPushButton { background-color: #333; color: #2d89ef; border: 1px solid #444; border-radius: 3px; font-size: 10px; font-weight: bold; padding: 2px; }
                QPushButton:hover { background-color: #0078d7; color: white; }
            """)
            btn_p.clicked.connect(lambda _, a=action_id, t='primary': self.change_hotkey(a, t))

            btn_s = QPushButton(info['secondary'] if info['secondary'] else "None")
            btn_s.setFixedWidth(65)
            btn_s.setToolTip("보조 단축키 변경")
            btn_s.setStyleSheet("""
                QPushButton { background-color: #333; color: #888; border: 1px solid #444; border-radius: 3px; font-size: 10px; padding: 2px; }
                QPushButton:hover { background-color: #0078d7; color: white; }
            """)
            btn_s.clicked.connect(lambda _, a=action_id, t='secondary': self.change_hotkey(a, t))

            row_layout.addWidget(btn_p, 0)
            row_layout.addWidget(btn_s, 0)

            self.hotkey_list_layout.addWidget(row_frame)

        self.hotkey_list_layout.addStretch()

    def change_hotkey(self, action_id: str, key_type: str):
        action_name = self.hotkeys[action_id]['name']
        type_str = "기본" if key_type == "primary" else "보조"
        dlg = KeyCaptureDialog(action_name, type_str, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.captured_key_str is not None:
            self.hotkeys[action_id][key_type] = dlg.captured_key_str
            self.save_hotkeys()
            self.refresh_hotkey_table()

    def reset_hotkeys_to_default(self):
        res = QMessageBox.question(
            self, "확인", "모든 단축키를 초기 설정으로 복원하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res == QMessageBox.StandardButton.Yes:
            self.hotkeys = copy.deepcopy(DEFAULT_HOTKEYS)
            self.save_hotkeys()
            self.refresh_hotkey_table()

    def get_active_working_dir(self):
        if self.historyCombo.currentIndex() >= 0:
            current_path = self.historyCombo.currentText()
            if os.path.exists(current_path):
                return current_path
        return self.default_dir

    def reset_cut_button_state(self):
        if hasattr(self, 'playOutBtn') and self.playOutBtn:
            if self.playOutBtn.text() == "재생":
                self.playOutBtn.setText("컷팅")
                self.playOutBtn.setStyleSheet("")
                self.update_output_play_btn_state()

    def on_trim_start_changed(self, ms: int):
        new_str = ms_to_time_str(ms)
        if self.startInput.displayText() != new_str:
            self.startInput.blockSignals(True)
            self.startInput.setText(new_str)
            self.startInput.blockSignals(False)
        self.reset_cut_button_state()

    def on_trim_end_changed(self, ms: int):
        new_str = ms_to_time_str(ms)
        if self.endInput.displayText() != new_str:
            self.endInput.blockSignals(True)
            self.endInput.setText(new_str)
            self.endInput.blockSignals(False)
        self.reset_cut_button_state()

    def on_start_input_text_changed(self, txt: str):
        ms = self.startInput.time_to_centiseconds(txt) * 10
        if self.player_widget.trimming_slider.start_ms != ms:
            self.player_widget.trimming_slider.set_start_ms(ms)
        self.reset_cut_button_state()

    def on_end_input_text_changed(self, txt: str):
        ms = self.endInput.time_to_centiseconds(txt) * 10
        if self.player_widget.trimming_slider.end_ms != ms:
            self.player_widget.trimming_slider.set_end_ms(ms)
        self.reset_cut_button_state()

    def on_timeline_region_selected(self, region: dict):
        if not region:
            return
        name = region.get('name', '')
        if name:
            self.nameInput.setText(name)
        self.reset_cut_button_state()

    def on_timeline_region_rename(self, index: int, region: dict):
        if not region:
            return
        old_name = region.get('name', '')
        new_name, ok = QInputDialog.getText(
            self, "편집 영역 이름 수정", "새 저장 파일명을 입력하세요:", text=old_name
        )
        if ok and new_name.strip():
            new_name = new_name.strip()
            video_in = self.fileInput.text().replace('\\', '/')
            saved = load_app_data_json("task_history.json")
            if saved and isinstance(saved, list):
                s_ms = region.get('start_ms', 0)
                e_ms = region.get('end_ms', 0)
                for item in saved:
                    v_path = item.get('video_in', '').replace('\\', '/')
                    if v_path == video_in and item.get('start_ms', 0) == s_ms and item.get('end_ms', 0) == e_ms:
                        item['name'] = new_name
                save_app_data_json("task_history.json", saved)
                self.load_task_history()

            self.nameInput.setText(new_name)
            self.refresh_playlist_colors()
            self.update_timeline_cut_highlights()
            self.show_toast(f"편집 영역 이름이 '{new_name}'(으)로 수정되었습니다.")

    def on_timeline_region_delete(self, index: int, region: dict):
        if not region:
            return
        r_name = region.get('name', '')
        res = QMessageBox.question(
            self, "편집 영역 삭제", f"'{r_name}' 편집 영역 히스토리를 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if res != QMessageBox.StandardButton.Yes:
            return

        video_in = self.fileInput.text().replace('\\', '/')
        saved = load_app_data_json("task_history.json")
        if saved and isinstance(saved, list):
            s_ms = region.get('start_ms', 0)
            e_ms = region.get('end_ms', 0)
            new_saved = []
            for item in saved:
                v_path = item.get('video_in', '').replace('\\', '/')
                if v_path == video_in and item.get('start_ms', 0) == s_ms and item.get('end_ms', 0) == e_ms:
                    continue
                new_saved.append(item)
            save_app_data_json("task_history.json", new_saved)
            self.load_task_history()

        self.refresh_playlist_colors()
        self.update_timeline_cut_highlights()
        self.show_toast("편집 영역 히스토리가 삭제되었습니다.")

    def animate_sidebar(self, widget: QFrame, target_width: int):
        if hasattr(widget, '_anim') and widget._anim:
            try:
                if widget._anim.state() == QPropertyAnimation.State.Running:
                    widget._anim.stop()
            except RuntimeError:
                pass
            widget._anim = None

        is_closing = widget.isVisible() and widget.width() > 10

        anim = QPropertyAnimation(widget, b"maximumWidth", self)
        widget._anim = anim
        anim.setDuration(220)

        if is_closing:
            anim.setStartValue(widget.width())
            anim.setEndValue(0)
            anim.setEasingCurve(QEasingCurve.Type.InQuad)
            def on_closed():
                widget.setVisible(False)
                widget.setMaximumWidth(target_width)
                widget._anim = None
            anim.finished.connect(on_closed)
        else:
            widget.setVisible(True)
            anim.setStartValue(widget.width() if widget.width() < target_width else 0)
            anim.setEndValue(target_width)
            anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            def on_opened():
                widget.setMaximumWidth(target_width)
                widget._anim = None
            anim.finished.connect(on_opened)

        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def toggle_option_sidebar(self):
        self.toggle_edit_modal()

    def toggle_playlist_sidebar(self):
        self.toggle_playlist_modal()

    def update_window_title_for_file(self, file_path: str = ""):
        """상단 타이틀바에 현재 재생 중인 파일명만 깔끔하게 출력 (미로드 시 Movie Player Lite)"""
        if file_path and os.path.basename(file_path):
            self.setWindowTitle(os.path.basename(file_path))
        else:
            self.setWindowTitle("Movie Player Lite")

    def load_playlist_history(self):
        saved_paths = load_app_data_json("playlist_history.json")
        if saved_paths and isinstance(saved_paths, list):
            self.playlist_files = []
            self.playlist_widget.clear()
            for path in saved_paths:
                if isinstance(path, str):
                    norm_p = path.replace('\\', '/')
                    if os.path.isfile(norm_p):
                        self.add_file_to_playlist(norm_p, load_immediately=False, save_history=False)
            self.save_playlist_history()

    def save_playlist_history(self):
        save_app_data_json("playlist_history.json", self.playlist_files)

    def _record_playlist_file_id(self, norm_path: str):
        try:
            st = os.stat(norm_path)
            if st.st_ino:
                self.playlist_file_ids[norm_path.lower()] = st.st_ino
        except Exception:
            pass

    def add_file_to_playlist(self, file_path: str, load_immediately=True, save_history=True):
        if not file_path:
            return
        norm_path = os.path.abspath(os.path.normpath(file_path)).replace('\\', '/')
        if os.path.isfile(norm_path):
            existing_norm_list = [os.path.abspath(os.path.normpath(p)).replace('\\', '/').lower() for p in self.playlist_files]
            if norm_path.lower() not in existing_norm_list:
                self.playlist_files.append(norm_path)
                item = QListWidgetItem(os.path.basename(norm_path))
                item.setToolTip(norm_path)
                item.setData(Qt.ItemDataRole.UserRole, norm_path)
                item.setSizeHint(QSize(0, 22))
                self.playlist_widget.addItem(item)
            self._record_playlist_file_id(norm_path)
            
            for i in range(self.playlist_widget.count()):
                it = self.playlist_widget.item(i)
                user_data = it.data(Qt.ItemDataRole.UserRole)
                if user_data and os.path.abspath(os.path.normpath(user_data)).replace('\\', '/').lower() == norm_path.lower():
                    if load_immediately:
                        self.playlist_widget.clearSelection()
                    self.playlist_widget.setCurrentItem(it)
                    if load_immediately:
                        it.setSelected(True)
                    break

            if save_history:
                self.save_playlist_history()

            self.refresh_playlist_colors()

            if load_immediately:
                self.fileInput.setText(norm_path)

    def open_and_play_external_file(self, file_path: str):
        """외부(또는 명령줄/IPC)에서 영상을 열 때: 목록 추가(중복 제외) + 해당 목록 선택 + 즉시 재생"""
        if not file_path:
            return
        norm_path = os.path.abspath(os.path.normpath(file_path)).replace('\\', '/')
        if not os.path.isfile(norm_path):
            return
        self.add_file_to_playlist(norm_path, load_immediately=False, save_history=True)
        for i in range(self.playlist_widget.count()):
            it = self.playlist_widget.item(i)
            user_data = it.data(Qt.ItemDataRole.UserRole)
            if user_data and os.path.abspath(os.path.normpath(user_data)).replace('\\', '/').lower() == norm_path.lower():
                self.playlist_widget.clearSelection()
                self.playlist_widget.setCurrentItem(it)
                it.setSelected(True)
                self.playlist_widget.scrollToItem(it)
                break
        self._auto_play_next_load = True
        cur_input = os.path.abspath(os.path.normpath(self.fileInput.text())).replace('\\', '/') if self.fileInput.text().strip() else ""
        if cur_input.lower() == norm_path.lower():
            self.on_file_changed(norm_path)
        else:
            self.fileInput.setText(norm_path)

    def remove_selected_playlist_item(self):
        items = self.playlist_widget.selectedItems()
        if not items:
            cur = self.playlist_widget.currentItem()
            if cur:
                items = [cur]
        if not items:
            return

        for item in items:
            file_path = item.data(Qt.ItemDataRole.UserRole)
            fk = norm_path_key(file_path)
            if fk and (
                norm_path_key(self.player_widget.video_path_cached) == fk
                or norm_path_key(self.fileInput.text()) == fk
            ):
                self.player_widget.unload_video()
                self.fileInput.setText("")
                self.update_window_title_for_file("")
            
            row = self.playlist_widget.row(item)
            self.playlist_widget.takeItem(row)
            self.playlist_files = [p for p in self.playlist_files if norm_path_key(p) != fk]

        self.save_playlist_history()
        self.refresh_playlist_colors()

    def delete_selected_playlist_file_permanently(self):
        items = self.playlist_widget.selectedItems()
        if not items:
            cur = self.playlist_widget.currentItem()
            if cur:
                items = [cur]
        if not items:
            return

        file_paths = [it.data(Qt.ItemDataRole.UserRole) for it in items if it.data(Qt.ItemDataRole.UserRole)]
        if not file_paths:
            return

        if len(file_paths) == 1:
            file_name = os.path.basename(file_paths[0])
            msg = f"'{file_name}' 파일을 디스크에서 완전히 삭제하시겠습니까?\n\n경로: {file_paths[0]}"
        else:
            msg = f"선택한 {len(file_paths)}개 파일을 디스크에서 완전히 삭제하시겠습니까?"

        res = QMessageBox.question(
            self,
            "파일 물리 삭제 확인",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if res != QMessageBox.StandardButton.Yes:
            return

        deleted_count = 0
        for item in items:
            file_path = item.data(Qt.ItemDataRole.UserRole)
            if not file_path:
                continue

            fk = norm_path_key(file_path)
            if fk and (
                norm_path_key(self.player_widget.video_path_cached) == fk
                or norm_path_key(self.fileInput.text()) == fk
            ):
                self.player_widget.unload_video()
                self.fileInput.setText("")
                self.update_window_title_for_file("")

            row = self.playlist_widget.row(item)
            self.playlist_widget.takeItem(row)
            self.playlist_files = [p for p in self.playlist_files if norm_path_key(p) != fk]

            if os.path.exists(file_path):
                try:
                    safe_remove_with_unlock(file_path, player_widget=self.player_widget)
                    deleted_count += 1
                except Exception as e:
                    print(f"Failed to delete {file_path}: {e}")

        self.save_playlist_history()
        self.refresh_playlist_colors()
        self.show_toast(f"{deleted_count}개 파일 삭제 완료")

    def rename_selected_playlist_file(self):
        item = self.playlist_widget.currentItem()
        if not item:
            return
        old_file_path = item.data(Qt.ItemDataRole.UserRole)
        if not old_file_path or not os.path.isfile(old_file_path):
            if item:
                row = self.playlist_widget.row(item)
                self.playlist_widget.takeItem(row)
                if old_file_path:
                    old_k = norm_path_key(old_file_path)
                    self.playlist_files = [p for p in self.playlist_files if norm_path_key(p) != old_k]
                    self.save_playlist_history()
                self.refresh_playlist_colors()
                self.show_toast("존재하지 않는 유실 파일이어서 재생목록에서 제거되었습니다.")
            return
            
        old_dir = os.path.dirname(old_file_path)
        old_file_name = os.path.basename(old_file_path)
        old_base, ext = os.path.splitext(old_file_name)
        if not ext:
            ext = ".mp4"
            
        new_base, ok = QInputDialog.getText(
            self,
            "파일 이름 변경 (F2)",
            "새 파일 이름을 입력하세요:",
            QLineEdit.EchoMode.Normal,
            old_base
        )
        if not ok or not new_base.strip():
            return
            
        new_base = new_base.strip()
        if new_base == old_base:
            return
            
        new_file_name = new_base + ext
        new_file_path = os.path.join(old_dir, new_file_name).replace('\\', '/')
        
        if os.path.exists(new_file_path) and norm_path_key(new_file_path) != norm_path_key(old_file_path):
            new_file_path = get_unique_filename(new_file_path)
            new_file_name = os.path.basename(new_file_path)
            new_base = os.path.splitext(new_file_name)[0]
            
        try:
            old_key = norm_path_key(old_file_path)
            is_active = (
                norm_path_key(self.player_widget.video_path_cached) == old_key
                or norm_path_key(self.fileInput.text()) == old_key
            )
            # 썸네일 추출 자식 프로세스(ffmpeg.exe) 즉시 중단 및 활성 영상 언로드
            self.player_widget.stop_thumbnail_thread()
            if is_active:
                self.player_widget.unload_video()
                QApplication.processEvents()

            safe_rename_with_unlock(old_file_path, new_file_path, player_widget=self.player_widget)
            
            item.setText(new_file_name)
            item.setToolTip(new_file_path)
            item.setData(Qt.ItemDataRole.UserRole, new_file_path)
            
            self.playlist_file_ids.pop(old_key, None)
            self._record_playlist_file_id(new_file_path)

            for idx, p in enumerate(self.playlist_files):
                if norm_path_key(p) == old_key:
                    self.playlist_files[idx] = new_file_path
            self.save_playlist_history()
            
            for t in self.task_histories:
                if t.get('video_in') and norm_path_key(t['video_in']) == old_key:
                    t['video_in'] = new_file_path
            save_app_data_json("task_history.json", self.task_histories)
            
            self.refresh_playlist_colors()
            
            if is_active:
                self._auto_play_next_load = True
                self.fileInput.setText(new_file_path)
                self.update_window_title_for_file(new_file_path)
                
            self.show_toast(f"'{old_base}' -> '{new_base}' (으)로 변경되었습니다.")
        except Exception as e:
            QMessageBox.critical(self, "에러", f"파일 이름 변경 실패:\n{str(e)}")

    def save_transform_video(self):
        if not self.player_widget.has_video_loaded or not self.fileInput.text().strip():
            QMessageBox.warning(self, "경고", "저장할 원본 영상이 선택되지 않았습니다.")
            return
            
        if not self.player_widget.is_transformed():
            self.capture_current_frame()
            return

        source_file = self.fileInput.text().strip()
        default_dir = self.dirInput.text().strip() or os.path.dirname(source_file)
        default_name = self.get_clean_output_name()
        
        save_name, ok = QInputDialog.getText(
            self,
            "변형 상태 저장 (Ctrl+S)",
            "저장할 파일 이름을 입력하세요 (동일 이름 시 덮어쓰기):",
            QLineEdit.EchoMode.Normal,
            default_name
        )
        if not ok or not save_name.strip():
            return
            
        save_name = save_name.strip()
        if save_name.lower().endswith(".mp4"):
            save_name = save_name[:-4]
            
        target_path = os.path.join(default_dir, save_name + ".mp4").replace('\\', '/')
        
        filters = []
        rot = self.player_widget.transform_rotation
        if rot == 90:
            filters.append("transpose=1")
        elif rot == 180:
            filters.append("transpose=1,transpose=1")
        elif rot == 270:
            filters.append("transpose=2")
            
        if self.player_widget.transform_flip_h:
            filters.append("hflip")
        if self.player_widget.transform_flip_v:
            filters.append("vflip")
            
        if not filters:
            return
            
        vf_str = ",".join(filters)
        ffmpeg_bin = get_ffmpeg_path()
        
        is_overwrite = os.path.exists(target_path)
        temp_target = target_path + ".tmp.mp4" if is_overwrite else target_path
        
        cmd = [
            ffmpeg_bin, "-y",
            "-i", source_file,
            "-vf", vf_str,
            "-c:a", "copy",
            temp_target
        ]
        
        try:
            target_key = norm_path_key(target_path)
            if is_overwrite and (
                norm_path_key(self.player_widget.video_path_cached) == target_key
                or norm_path_key(source_file) == target_key
            ):
                self.player_widget.unload_video()
                QApplication.processEvents()
                
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            if is_overwrite:
                if os.path.exists(target_path):
                    safe_remove_with_unlock(target_path, player_widget=self.player_widget)
                safe_rename_with_unlock(temp_target, target_path, player_widget=self.player_widget)
                
            self.player_widget.reset_transform()
            self.add_file_to_playlist(target_path, load_immediately=True, save_history=True)
            self.show_toast(f"'{os.path.basename(target_path)}' (으)로 변형 저장되었습니다.")
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "에러", f"변형 저장 실패:\n{e.stderr}")
        except Exception as e:
            QMessageBox.critical(self, "에러", f"변형 저장 실패:\n{str(e)}")

    def capture_current_frame(self):
        if not self.player_widget.has_video_loaded or not self.fileInput.text().strip():
            QMessageBox.warning(self, "경고", "스크린샷을 캡처할 영상이 선택되지 않았습니다.")
            return

        source_file = self.fileInput.text().strip()
        if not os.path.isfile(source_file):
            QMessageBox.warning(self, "경고", "원본 영상 파일이 존재하지 않습니다.")
            return

        pos_ms = self.player_widget.media_player.position()
        time_str = ms_to_time_str(pos_ms)
        time_tag = time_str.replace(":", "-").replace(".", "_")
        
        base_name = self.get_clean_output_name()
        default_img_name = f"{base_name}_{time_tag}.png"
        
        default_dir = self.dirInput.text().strip() or os.path.dirname(source_file)
        
        save_name, ok = QInputDialog.getText(
            self,
            "현재 프레임 스크린샷 저장 (Ctrl+S)",
            "저장할 스크린샷 이미지 파일 이름을 입력하세요:",
            QLineEdit.EchoMode.Normal,
            default_img_name
        )
        if not ok or not save_name.strip():
            return

        save_name = save_name.strip()
        if not save_name.lower().endswith((".png", ".jpg", ".jpeg")):
            save_name += ".png"

        target_img_path = os.path.join(default_dir, save_name).replace('\\', '/')
        
        ffmpeg_bin = get_ffmpeg_path()
        cmd = [
            ffmpeg_bin, "-y",
            "-ss", time_str,
            "-i", source_file,
            "-vframes", "1",
            "-q:v", "2",
            target_img_path
        ]

        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            self.show_toast(f"'{os.path.basename(target_img_path)}' 스크린샷 저장 완료!")
        except Exception as e:
            QMessageBox.critical(self, "에러", f"스크린샷 캡처 실패:\n{str(e)}")

    def clear_playlist(self):
        if self.player_widget.has_video_loaded:
            self.player_widget.unload_video()
            self.fileInput.setText("")
            self.update_window_title_for_file("")
        self.playlist_widget.clear()
        self.playlist_files.clear()
        self.save_playlist_history()

    def on_playlist_item_double_clicked(self, item):
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path and os.path.isfile(file_path):
            self.open_and_play_external_file(file_path)
            self.player_widget.setFocus()

    def on_playlist_context_menu(self, pos):
        item = self.playlist_widget.itemAt(pos)
        menu = QMenu(self)

        if item:
            file_path = item.data(Qt.ItemDataRole.UserRole)

            open_folder_act = QAction("폴더 열기", menu)
            open_folder_act.triggered.connect(lambda: open_source_file_dir(file_path))

            props_act = QAction("속성 보기 (단축키: ?)", menu)
            props_act.triggered.connect(lambda: show_file_properties(file_path))

            remove_act = QAction("목록에서 제거 (Del)", menu)
            remove_act.triggered.connect(self.remove_selected_playlist_item)

            delete_file_act = QAction("파일 물리 삭제 (Ctrl+Del)", menu)
            delete_file_act.triggered.connect(self.delete_selected_playlist_file_permanently)

            menu.addAction(open_folder_act)
            menu.addAction(props_act)
            menu.addSeparator()
            menu.addAction(remove_act)
            menu.addAction(delete_file_act)

        clear_all_act = QAction("전체 목록 비우기", menu)
        clear_all_act.triggered.connect(self.clear_playlist)
        menu.addAction(clear_all_act)

        menu.exec(self.playlist_widget.mapToGlobal(pos))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        first = None
        for u in urls:
            f = u.toLocalFile()
            if os.path.isfile(f) and f.lower().endswith(('.mp4', '.mkv', '.mov', '.avi', '.webm')):
                self.add_file_to_playlist(f, load_immediately=False)
                if not first:
                    first = f
        if first:
            self.open_and_play_external_file(first)

    def openFileDialog(self):
        start_dir = self.get_active_working_dir()
        files, _ = QFileDialog.getOpenFileNames(
            self, "비디오 파일 선택", start_dir, "Video Files (*.mp4 *.mkv *.mov *.avi *.webm)"
        )
        if files:
            for f in files:
                self.add_file_to_playlist(f, load_immediately=False)
            self.open_and_play_external_file(files[0])

    def on_file_changed(self, text):
        self.is_loading_file = True
        auto_play = getattr(self, '_auto_play_next_load', False)
        self._auto_play_next_load = False
        try:
            self.update_output_dir()
            is_exist = os.path.isfile(text)
            if is_exist:
                self.update_window_title_for_file(text)
                self.add_file_to_playlist(text, load_immediately=False)
                self.player_widget.load_video(text, auto_play=auto_play)
                self.save_history(os.path.dirname(text))
                try:
                    duration_cs, creation_dt = get_media_creation_time_and_duration(text)
                    self.original_duration_cs = duration_cs
                    self.original_creation_dt = creation_dt
                    
                    self.startInput.max_val_cs = duration_cs
                    self.endInput.max_val_cs = duration_cs
                    
                    start_cs = 0
                    end_cs = duration_cs
                    
                    self.startInput.setText(self.startInput.centiseconds_to_time(start_cs))
                    self.endInput.setText(self.endInput.centiseconds_to_time(end_cs))

                    duration_ms = duration_cs * 10
                    self.player_widget.trimming_slider.set_duration(duration_ms)
                    self.player_widget.trimming_slider.set_start_ms(0)
                    self.player_widget.trimming_slider.set_end_ms(duration_ms)

                    base_name = os.path.basename(text)
                    if base_name.lower().endswith(".mp4"):
                        base_name = base_name[:-4]
                    self.nameInput.setText(base_name)

                    self.check_target_file_exists()
                    self.update_timeline_cut_highlights()
                except Exception as e:
                    import traceback
                    error_msg = traceback.format_exc()
                    print("Error parsing media:", error_msg)
                    QMessageBox.warning(
                        self,
                        "미디어 정보 분석 실패",
                        f"동영상 정보(재생 시간)를 가져오지 못했습니다.\n기본 제한 시간(99:59:59.99)이 적용됩니다.\n\n상세 에러:\n{str(e)}"
                    )
                    self.original_duration_cs = 35999999
                    self.original_creation_dt = None
                    self.startInput.max_val_cs = 35999999
                    self.endInput.max_val_cs = 35999999
            else:
                if text:
                    base_name = os.path.splitext(os.path.basename(text))[0]
                    if base_name:
                        self.nameInput.setText(base_name)
                else:
                    self.update_window_title_for_file("")
                self.original_duration_cs = 35999999
                self.original_creation_dt = None
                self.startInput.max_val_cs = 35999999
                self.endInput.max_val_cs = 35999999
        finally:
            self.is_loading_file = False

    def openDirDialog(self):
        start_dir = self.get_active_working_dir()
        directory = QFileDialog.getExistingDirectory(self, "저장 폴더 선택", start_dir)
        if directory:
            self.dirInput.setText(directory.replace('\\', '/'))

    def open_current_directory(self):
        target_dir = self.dirInput.text()
        if not target_dir or not os.path.exists(os.path.normpath(target_dir)):
            target_dir = self.get_active_working_dir()
            
        normalized_dir = os.path.normpath(target_dir) if target_dir else ""
        if not normalized_dir or not os.path.exists(normalized_dir):
            QMessageBox.warning(
                self, "경고", "지정된 저장 위치 경로가 하드디스크에 실재하지 않습니다."
            )
            return
        try:
            os.startfile(normalized_dir)
        except Exception as e:
            QMessageBox.critical(self, "에러", f"폴더 열기 실패:\n{str(e)}")

    def adjust_time_input(self, line_edit: ArrowKeyLineEdit, delta_sec: float):
        current_cs = line_edit.time_to_centiseconds(line_edit.displayText())
        new_cs = max(0, min(line_edit.max_val_cs, current_cs + int(delta_sec * 100)))
        line_edit.setText(line_edit.centiseconds_to_time(new_cs))

    def play_source_video(self):
        video_path = self.fileInput.text()
        if video_path and os.path.isfile(video_path):
            self.player_widget.load_video(video_path, auto_play=True)
            start_cs = self.startInput.time_to_centiseconds(self.startInput.displayText())
            if start_cs > 0:
                self.player_widget.set_position(start_cs * 10)
        else:
            QMessageBox.warning(self, "경고", "올바른 원본 파일이 선택되지 않았습니다.")

    def view_source_properties(self):
        video_path = self.fileInput.text()
        if video_path and os.path.isfile(video_path):
            show_file_properties(video_path)
        else:
            QMessageBox.warning(self, "경고", "올바른 원본 파일이 선택되지 않았습니다.")

    def open_source_folder(self):
        video_path = self.fileInput.text()
        if video_path and os.path.isfile(video_path):
            open_source_file_dir(video_path)
        else:
            QMessageBox.warning(self, "경고", "올바른 원본 파일이 선택되지 않았습니다.")

    def play_output_video(self):
        self.playOutBtn.setStyleSheet("")
        output_file = self.get_full_output_path()
        if output_file and os.path.isfile(output_file):
            # 컷팅 파일 재생 시 재생목록에 자동 추가하고 현재 플레이어에서 바로 재생
            self.add_file_to_playlist(output_file, load_immediately=True, save_history=True)
            self.player_widget.load_video(output_file, auto_play=True)
            self.player_widget.setFocus()
        else:
            QMessageBox.warning(self, "경고", f"편집 영상 파일이 존재하지 않습니다.\n({output_file})")

    def update_output_play_btn_state(self):
        if self.playOutBtn.text() == "재생":
            output_file = self.get_full_output_path()
            is_exist = bool(output_file and os.path.isfile(output_file))
            self.playOutBtn.setEnabled(is_exist)
        else:
            has_input = bool(self.fileInput.text().strip() and os.path.isfile(self.fileInput.text().strip()))
            self.playOutBtn.setEnabled(has_input)

    def update_output_dir(self):
        source_file = self.fileInput.text()
        if self.radioSame.isChecked():
            if source_file:
                self.dirInput.setText(os.path.dirname(source_file).replace('\\', '/'))
            else:
                self.dirInput.setText("")
        elif self.radioOutput.isChecked():
            if source_file:
                self.dirInput.setText(os.path.join(os.path.dirname(source_file), "output").replace('\\', '/'))
            else:
                self.dirInput.setText("")
        elif self.radioCustom.isChecked():
            if not self.dirInput.text():
                self.dirInput.setText(self.get_active_working_dir().replace('\\', '/'))
        self.update_output_play_btn_state()

    def on_radio_changed(self):
        is_custom = self.radioCustom.isChecked()
        self.dirInput.setEnabled(is_custom)
        self.dirBtn.setEnabled(is_custom)
        
        if is_custom:
            self.dirInput.setText(self.get_active_working_dir().replace('\\', '/'))
        else:
            self.update_output_dir()
        self.update_output_play_btn_state()

    def on_history_combo_changed(self, index):
        if self.is_loading_file:
            return
        if self.radioCustom.isChecked() and index >= 0:
            self.dirInput.setText(self.historyCombo.currentText().replace('\\', '/'))

    def check_end_time_focus(self):
        start_cs = self.startInput.time_to_centiseconds(self.startInput.displayText())
        end_cs = self.endInput.time_to_centiseconds(self.endInput.displayText())
        if start_cs > end_cs:
            self.endInput.setText(self.startInput.displayText())

    def get_clean_output_name(self) -> str:
        txt = self.nameInput.text().strip()
        if txt.lower().endswith(".mp4"):
            txt = txt[:-4].strip()
        return txt if txt else "output"

    def get_full_output_path(self) -> str:
        out_dir = self.dirInput.text().strip()
        clean_name = self.get_clean_output_name()
        return os.path.join(out_dir, clean_name + ".mp4").replace('\\', '/')

    def check_target_file_exists(self):
        if hasattr(self, 'is_loading_history') and self.is_loading_history:
            return
        full_path = self.get_full_output_path()
        if full_path and os.path.exists(full_path):
            self.autoNumberCheck.blockSignals(True)
            self.autoNumberCheck.setChecked(True)
            self.autoNumberCheck.blockSignals(False)

    def show_toast(self, message: str):
        if not hasattr(self, 'toast_label') or self.toast_label is None:
            self.toast_label = QLabel(self)
            self.toast_label.setStyleSheet("""
                QLabel {
                    background-color: rgba(30, 100, 200, 0.95);
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 12px;
                    padding: 8px 16px;
                    border-radius: 6px;
                    border: 1px solid rgba(255, 255, 255, 0.4);
                }
            """)
            self.toast_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.toast_label.hide()
        
        self.toast_label.setText(message)
        self.toast_label.adjustSize()
        self.toast_label.move(max(10, self.width() - self.toast_label.width() - 20), 20)
        self.toast_label.show()
        self.toast_label.raise_()
        
        QTimer.singleShot(1000, lambda: self.toast_label.hide() if hasattr(self, 'toast_label') and self.toast_label else None)

    def on_cut_or_play_clicked(self):
        if self.playOutBtn.text() == "재생":
            self.play_output_video()
        else:
            self.executeCutter()

    def executeCutter(self):
        video_in = self.fileInput.text().strip()
        start_time = self.startInput.displayText()
        end_time = self.endInput.displayText()
        clean_name = self.get_clean_output_name()
        out_name = clean_name + ".mp4"
        out_dir = self.dirInput.text().strip()

        if not video_in or not out_dir:
            QMessageBox.warning(
                self, "경고", "파일 경로 및 저장 위치를 모두 지정하십시오."
            )
            return

        if not os.path.isfile(video_in):
            QMessageBox.warning(
                self, "경고", "원본 동영상 파일이 존재하지 않습니다."
            )
            return

        start_cs = self.startInput.time_to_centiseconds(start_time)
        end_cs = self.endInput.time_to_centiseconds(end_time)
        if start_cs >= end_cs or (end_cs - start_cs) < 10:
            QMessageBox.warning(
                self, "경고", "컷팅 구간이 올바르지 않습니다. (최소 0.1초 이상 지정 필요)"
            )
            return

        os.makedirs(out_dir, exist_ok=True)

        video_out = os.path.join(out_dir, out_name).replace('\\', '/')
        if self.autoNumberCheck.isChecked():
            video_out = get_unique_filename(video_out)
            final_name = os.path.basename(video_out)
            if final_name.lower().endswith(".mp4"):
                final_name = final_name[:-4]
            self.nameInput.blockSignals(True)
            self.nameInput.setText(final_name)
            self.nameInput.blockSignals(False)

        dur_cs = max(0, end_cs - start_cs)
        dur_str = self.startInput.centiseconds_to_time(dur_cs)

        norm_in = os.path.normpath(video_in)
        norm_out = os.path.normpath(video_out)

        ffmpeg_bin = get_ffmpeg_path()

        cmd = [
            ffmpeg_bin,
            "-y",
            "-ss", start_time,
            "-i", norm_in,
            "-t", dur_str,
        ]

        if self.muteCheck.isChecked():
            cmd.extend(["-c:v", "copy", "-an"])
        else:
            cmd.extend(["-c:v", "copy", "-c:a", "copy"])

        cmd.extend(["-avoid_negative_ts", "make_zero"])

        if self.copyMetaCheck.isChecked():
            cmd.extend(["-map_metadata", "0"])
            if self.original_creation_dt:
                offset_secs = start_cs / 100.0
                new_creation_dt = self.original_creation_dt + timedelta(seconds=offset_secs)
                new_creation_str = new_creation_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                cmd.extend(["-metadata", f"creation_time={new_creation_str}"])
        else:
            cmd.extend(["-map_metadata", "-1"])

        cmd.append(norm_out)

        try:
            subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            out_filename = os.path.basename(video_out)
            self.show_toast(f"'{out_filename}' (으)로 저장되었습니다.")

            self.playOutBtn.setText("재생")
            self.playOutBtn.setStyleSheet("background-color: #ff3b30; color: white; font-weight: bold;")
            self.playOutBtn.setEnabled(True)
            
            # 무손실 컷팅 성공 시 항상 작업 히스토리 저장
            self.add_task_history()

            self.refresh_playlist_colors()
            self.update_timeline_cut_highlights()
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "에러", f"FFmpeg 분할 실패:\n{e.stderr}")

    def save_history(self, path):
        path = path.replace('\\', '/')
        saved = load_app_data_json("trim_history.json")
        history = [p.replace('\\', '/') for p in saved] if saved and isinstance(saved, list) else []
        if path in history:
            history.remove(path)
        history.insert(0, path)
        history = history[:5]
        save_app_data_json("trim_history.json", history)
        self.refresh_history_combo(history)

    def load_history(self):
        saved = load_app_data_json("trim_history.json")
        history = [p.replace('\\', '/') for p in saved] if saved and isinstance(saved, list) else []
        self.refresh_history_combo(history)

    def refresh_history_combo(self, history):
        self.historyCombo.clear()
        
        history = [p.replace('\\', '/') for p in history]
        unique_history = []
        for p in history:
            if p not in unique_history:
                unique_history.append(p)
                
        self.historyCombo.addItems(unique_history)
        
        default_normalized = self.default_dir.replace('\\', '/')
        if default_normalized not in unique_history:
            self.historyCombo.addItem(default_normalized)
            
        if self.historyCombo.count() > 0:
            self.historyCombo.setCurrentIndex(0)

    def load_task_history(self):
        saved = load_app_data_json("task_history.json")
        self.task_histories = saved if saved and isinstance(saved, list) else []
        self.refresh_task_history_combo()
        self.refresh_playlist_colors()
        self.update_timeline_cut_highlights()

    def refresh_task_history_combo(self):
        self.taskHistoryCombo.blockSignals(True)
        self.taskHistoryCombo.clear()
        self.taskHistoryCombo.addItem("작업 히스토리 선택...")
        for task in self.task_histories:
            self.taskHistoryCombo.addItem(task['name'])
        self.taskHistoryCombo.blockSignals(False)

    def on_task_history_selected(self, index):
        if index <= 0:
            return
        task = self.task_histories[index - 1]
        
        self.is_loading_history = True
        
        # 1. 영상 파일 로드 및 재생바 연동
        v_in = task.get('video_in', '')
        if v_in and os.path.isfile(v_in):
            self.fileInput.setText(v_in)
            if self.player_widget.video_path_cached != v_in:
                self.player_widget.load_video(v_in, auto_play=False)

        # 2. 작업 히스토리의 시작/종료 범위로 start & end 설정
        start_str = task.get('start_time', '00:00:00.00')
        end_str = task.get('end_time', '00:00:00.00')
        self.startInput.setText(''.join(c for c in start_str if c.isdigit()))
        self.endInput.setText(''.join(c for c in end_str if c.isdigit()))
        
        # 3. 타임라인 슬라이더의 [Start, End] 마커 및 재생 헤드 위치 동기화
        start_cs = self.startInput.time_to_centiseconds(self.startInput.displayText())
        end_cs = self.endInput.time_to_centiseconds(self.endInput.displayText())
        start_ms = start_cs * 10
        end_ms = end_cs * 10
        
        def apply_trim_bounds():
            if hasattr(self.player_widget, 'trimming_slider'):
                self.player_widget.trimming_slider.set_end_ms(end_ms)
                self.player_widget.trimming_slider.set_start_ms(start_ms)
                self.player_widget.trimming_slider.set_position(start_ms)
            if hasattr(self.player_widget, 'media_player'):
                self.player_widget.media_player.setPosition(start_ms)

        apply_trim_bounds()
        QTimer.singleShot(100, apply_trim_bounds)
        QTimer.singleShot(350, apply_trim_bounds)

        raw_out_name = task.get('out_name', '')
        if raw_out_name.lower().endswith(".mp4"):
            raw_out_name = raw_out_name[:-4]
        self.nameInput.setText(raw_out_name)

        self.muteCheck.setChecked(task.get('mute', False))
        self.copyMetaCheck.setChecked(task.get('copy_meta', True))
        self.autoNumberCheck.setChecked(task.get('auto_number', False))
        
        radio_state = task.get('radio_state', 'custom')
        if radio_state == 'same':
            self.radioSame.setChecked(True)
        elif radio_state == 'output':
            self.radioOutput.setChecked(True)
        else:
            self.radioCustom.setChecked(True)
            
        self.dirInput.setText(task.get('out_dir', ''))
        
        self.create_history_flag = False
        self.is_loading_history = False
        self.update_timeline_cut_highlights()
        self.update_output_play_btn_state()
        if hasattr(self, 'player_widget') and self.player_widget:
            self.player_widget.setFocus()

    def add_task_history(self):
        video_in = self.fileInput.text().strip()
        if not video_in:
            return
        start_time = self.startInput.displayText()
        end_time = self.endInput.displayText()
        clean_name = self.get_clean_output_name()
        out_name = clean_name + ".mp4"
        out_dir = self.dirInput.text().strip()
        
        if self.radioSame.isChecked():
            radio_state = "same"
        elif self.radioOutput.isChecked():
            radio_state = "output"
        else:
            radio_state = "custom"
            
        base_video = os.path.basename(video_in)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        history_name = f"{base_video}_{start_time}_{timestamp}"
        
        task = {
            "name": history_name,
            "video_in": video_in,
            "start_time": start_time,
            "end_time": end_time,
            "out_name": out_name,
            "mute": self.muteCheck.isChecked(),
            "copy_meta": self.copyMetaCheck.isChecked(),
            "auto_number": self.autoNumberCheck.isChecked(),
            "out_dir": out_dir,
            "radio_state": radio_state
        }
        
        self.task_histories = [
            t for t in self.task_histories 
            if not (t['video_in'] == video_in and t['start_time'] == start_time and t['end_time'] == end_time and t['out_name'] == out_name and t['out_dir'] == out_dir)
        ]
        
        self.task_histories.insert(0, task)
        self.task_histories = self.task_histories[:50]
        
        save_app_data_json("task_history.json", self.task_histories)
        self.refresh_task_history_combo()
        self.refresh_playlist_colors()
        self.update_timeline_cut_highlights()

    def refresh_playlist_colors(self):
        for i in range(self.playlist_widget.count()):
            item = self.playlist_widget.item(i)
            item.setSizeHint(QSize(0, 22))  # 고밀도 세로 간격 22px 지정
            v_path = item.data(Qt.ItemDataRole.UserRole)
            if not v_path:
                continue
            
            norm_v = os.path.abspath(os.path.normpath(v_path)).lower()
            cut_count = sum(
                1 for t in self.task_histories 
                if t.get('video_in') and os.path.abspath(os.path.normpath(t.get('video_in'))).lower() == norm_v
            )
            
            # 글씨색은 언제나 기존의 흰색(#ffffff)으로 유지
            item.setForeground(QColor("#ffffff"))
            
            if cut_count >= 3:
                # 3개 이상 컷팅 이력: 선명한 파스텔톤 노란색 배경 (#c4ab14)
                item.setBackground(QColor("#c4ab14"))
            elif cut_count == 2:
                # 2개 컷팅 이력: 중간 옅은 파스텔 노란색 배경 (#99861e)
                item.setBackground(QColor("#99861e"))
            elif cut_count == 1:
                # 1개 컷팅 이력: 아주 옅은 파스텔 노란색 배경 (#695c1b)
                item.setBackground(QColor("#695c1b"))
            else:
                # 0개 컷팅 이력: 기본 어두운 배경 (#1e1e1e)
                item.setBackground(QColor("#1e1e1e"))

    def update_timeline_cut_highlights(self):
        cur_file = self.fileInput.text().strip()
        if not cur_file or not hasattr(self.player_widget, 'trimming_slider'):
            return
        
        regions = []
        for t in self.task_histories:
            if t.get('video_in') == cur_file:
                try:
                    s_cs = self.startInput.time_to_centiseconds(t.get('start_time', '00:00:00.00'))
                    e_cs = self.endInput.time_to_centiseconds(t.get('end_time', '00:00:00.00'))
                    name = t.get('out_name', '')
                    regions.append({
                        'start_ms': s_cs * 10,
                        'end_ms': e_cs * 10,
                        'name': name
                    })
                except:
                    pass
        self.player_widget.trimming_slider.set_cut_history_regions(regions)

    def on_hud_check_toggled(self, checked):
        self.player_widget.force_hud_visible = checked
        self.sync_menu_check_states()
        self.player_widget.update_hud()

    def on_input_modified(self):
        if not self.is_loading_history:
            self.create_history_flag = True
        self.playOutBtn.setText("컷팅")
        self.playOutBtn.setStyleSheet("")
        self.check_target_file_exists()
        self.update_timeline_cut_highlights()

    def on_name_input_enter(self):
        self.executeCutter()

    def update_name_input_style(self):
        current_name = self.nameInput.text()
        if self.last_enter_name and current_name == self.last_enter_name:
            self.nameInput.setStyleSheet("border: 1px solid red;")
        else:
            self.nameInput.setStyleSheet("")

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange:
            if hasattr(self, 'player_widget') and self.player_widget:
                self.player_widget.update_hud()
            if self.isActiveWindow():
                self.ensure_modal_z_order()

    def keyPressEvent(self, event: QKeyEvent):
        # Alt 키가 눌리면 상단 오버레이 메뉴바 표시
        if event.key() == Qt.Key.Key_Alt:
            if hasattr(self, 'top_menu_bar') and self.top_menu_bar:
                self.top_menu_bar.show()
                self.top_menu_bar.raise_()
                self.player_widget.update_transform_badge_position()
                self.player_widget.hide_timer.start()
            super().keyPressEvent(event)
            return

        focus_w = QApplication.focusWidget()
        is_editing_text = isinstance(focus_w, QLineEdit)

        key_str = event_to_key_str(event)
        if not key_str:
            super().keyPressEvent(event)
            return

        matched_action = None
        for action_id, info in self.hotkeys.items():
            p = info.get("primary", "")
            s = info.get("secondary", "")
            if (p and p.upper() == key_str.upper()) or (s and s.upper() == key_str.upper()):
                matched_action = action_id
                break

        if not matched_action:
            super().keyPressEvent(event)
            return

        if is_editing_text and matched_action not in ("exit_fullscreen", "toggle_fullscreen"):
            super().keyPressEvent(event)
            return

        if matched_action == "toggle_option":
            self.toggle_edit_modal()
        elif matched_action == "toggle_playlist":
            self.toggle_playlist_modal()
        elif matched_action == "play_pause":
            self.player_widget.toggle_play()
        elif matched_action == "step_1s_prev":
            self.player_widget.step_time(-1000)
        elif matched_action == "step_1s_next":
            self.player_widget.step_time(1000)
        elif matched_action == "step_5s_prev":
            self.player_widget.step_time(-5000)
        elif matched_action == "step_5s_next":
            self.player_widget.step_time(5000)
        elif matched_action == "step_frame_prev":
            self.player_widget.step_frame(forward=False)
        elif matched_action == "step_frame_next":
            self.player_widget.step_frame(forward=True)
        elif matched_action == "speed_up":
            self.player_widget.change_playback_rate(0.25)
        elif matched_action == "speed_down":
            self.player_widget.change_playback_rate(-0.25)
        elif matched_action == "speed_reset":
            self.player_widget.reset_playback_rate()
        elif matched_action == "prev_video":
            self.play_prev_video()
        elif matched_action == "next_video":
            self.play_next_video()
        elif matched_action == "volume_up":
            self.player_widget.change_volume(0.05)
        elif matched_action == "volume_down":
            self.player_widget.change_volume(-0.05)
        elif matched_action == "toggle_mute":
            self.player_widget.toggle_mute()
        elif matched_action == "zoom_in":
            self.player_widget.zoom_in()
        elif matched_action == "zoom_out":
            self.player_widget.zoom_out()
        elif matched_action == "zoom_reset":
            self.player_widget.reset_zoom_pan()
        elif matched_action == "pan_up":
            self.player_widget.pan_view(0, -20)
        elif matched_action == "pan_down":
            self.player_widget.pan_view(0, 20)
        elif matched_action == "pan_left":
            self.player_widget.pan_view(-20, 0)
        elif matched_action == "pan_right":
            self.player_widget.pan_view(20, 0)
        elif matched_action == "toggle_fullscreen":
            self.cycle_fullscreen_mode()
        elif matched_action == "exit_fullscreen":
            self.set_screen_mode(0)
        elif matched_action == "show_properties":
            self.view_source_properties()
        elif matched_action == "delete_playlist_item":
            self.remove_selected_playlist_item()
        elif matched_action == "rename_playlist_item":
            self.rename_selected_playlist_file()
        elif matched_action == "flip_h":
            self.player_widget.flip_horizontal()
        elif matched_action == "flip_v":
            self.player_widget.flip_vertical()
        elif matched_action == "rotate_right":
            self.player_widget.rotate_right()
        elif matched_action == "rotate_left":
            self.player_widget.rotate_left()
        elif matched_action == "save_transform":
            self.save_transform_video()
        elif matched_action == "toggle_time_label":
            self.player_widget.toggle_time_label()
        elif matched_action == "toggle_hud":
            self.player_widget.toggle_hud_overlay()
        else:
            super().keyPressEvent(event)

    def set_screen_mode(self, stage: int):
        """화면 모드 직접 전환: 0=기본화면, 1=표준 전체화면, 2=전체화면(비율유지), 3=꽉찬화면"""
        self.fullscreen_stage = stage % 4
        root_layout = self.layout()
        if root_layout:
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(0)

        if self.fullscreen_stage == 0:
            self.setWindowFlags(Qt.WindowType.Window)
            self.showNormal()
            set_win32_window_rounding(int(self.winId()), enable_rounding=True)
            self.player_widget.set_fullscreen_mode(is_video_only=False, stretch_fill=False)
            self.player_widget.apply_auto_hide_settings()
            self.show_toast("기본화면 모드")

        elif self.fullscreen_stage == 1:
            self.setWindowFlags(Qt.WindowType.Window)
            self.showFullScreen()
            set_win32_window_rounding(int(self.winId()), enable_rounding=True)
            self.player_widget.set_fullscreen_mode(is_video_only=False, stretch_fill=False)
            self.player_widget.apply_auto_hide_settings()
            self.show_toast("전체화면 모드 [1/3] (표준 전체화면)")

        elif self.fullscreen_stage in (2, 3):
            stretch = (self.fullscreen_stage == 3)
            self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
            set_win32_window_rounding(int(self.winId()), enable_rounding=False)
            self.player_widget.set_fullscreen_mode(is_video_only=True, stretch_fill=stretch)
            self.player_widget.apply_auto_hide_settings()
            screen = self.screen() or QApplication.primaryScreen()
            if screen:
                self.setGeometry(screen.geometry())
            self.showFullScreen()
            msg = "꽉찬화면 모드 (100% 꽉 찬 동영상 모드)" if stretch else "전체화면 모드 (비율 유지 동영상 모드)"
            self.show_toast(msg)

        self.sync_menu_check_states()
        self.raise_()
        self.activateWindow()
        self.ensure_modal_z_order()

    def cycle_fullscreen_mode(self):
        if not hasattr(self, 'fullscreen_stage'):
            self.fullscreen_stage = 0
        self.set_screen_mode((self.fullscreen_stage + 1) % 4)

    def init_single_instance_server(self):
        """단일 인스턴스 IPC 서버 초기화: 외부에서 새 동영상 실행 시 기존 창에서 받아 처리"""
        try:
            QLocalServer.removeServer(SINGLE_INSTANCE_SERVER_NAME)
            self.local_server = QLocalServer(self)
            self.local_server.newConnection.connect(self.on_new_instance_connection)
            self.local_server.listen(SINGLE_INSTANCE_SERVER_NAME)
        except Exception as e:
            logging.warning(f"Failed to start single-instance server: {e}")

    def on_new_instance_connection(self):
        """새로 실행된 프로세스로부터 전달받은 동영상 경로를 목록에 추가/선택 후 즉시 재생"""
        if not self.local_server:
            return
        while self.local_server.hasPendingConnections():
            conn = self.local_server.nextPendingConnection()
            if not conn:
                continue
            if conn.bytesAvailable() == 0:
                conn.waitForReadyRead(500)
            raw_data = bytes(conn.readAll()).decode("utf-8", errors="ignore")
            conn.write(b"OK")
            conn.flush()
            conn.waitForBytesWritten(200)
            conn.disconnectFromServer()

            if self.isMinimized():
                self.showNormal()
            self.raise_()
            self.activateWindow()

            if raw_data:
                try:
                    payload = json.loads(raw_data)
                    files = payload.get("files", [])
                    valid_files = [f for f in files if f and os.path.isfile(f)]
                    if valid_files:
                        for extra_f in valid_files[1:]:
                            self.add_file_to_playlist(extra_f, load_immediately=False, save_history=True)
                        self.open_and_play_external_file(valid_files[0])
                        self.player_widget.setFocus()
                except Exception as e:
                    logging.error(f"Failed to process IPC message: {e}")

    def init_external_file_watcher(self):
        """재생 중인 파일 및 재생목록 파일들의 외부 이름변경/삭제 실시간 감시 타이머"""
        self.fs_sync_timer = QTimer(self)
        self.fs_sync_timer.setInterval(800)
        self.fs_sync_timer.timeout.connect(self.check_external_file_changes)
        self.fs_sync_timer.start()

    def _find_renamed_file_by_id(self, old_norm_path: str):
        target_ino = self.playlist_file_ids.get(old_norm_path.lower())
        if not target_ino:
            return None
        parent_dir = os.path.dirname(old_norm_path)
        if not parent_dir or not os.path.isdir(parent_dir):
            return None
        try:
            for entry in os.scandir(parent_dir):
                if entry.is_file():
                    try:
                        if entry.stat().st_ino == target_ino:
                            return os.path.abspath(os.path.normpath(entry.path)).replace('\\', '/')
                    except OSError:
                        continue
        except Exception:
            pass
        return None

    def apply_external_file_rename(self, old_path: str, new_path: str):
        """외부(탐색기 등)에서 변경된 파일명을 재생목록, 출력 파일명(nameInput), 작업 히스토리까지 일괄 반영"""
        norm_old = os.path.abspath(os.path.normpath(old_path)).replace('\\', '/')
        norm_new = os.path.abspath(os.path.normpath(new_path)).replace('\\', '/')
        if norm_old.lower() == norm_new.lower():
            return

        old_base = os.path.splitext(os.path.basename(norm_old))[0]
        new_file_name = os.path.basename(norm_new)
        new_base = os.path.splitext(new_file_name)[0]

        self.playlist_file_ids.pop(norm_old.lower(), None)
        self._record_playlist_file_id(norm_new)

        # 1. 재생목록 내부 리스트 및 UI 위젯 갱신 (중복 방지 포함)
        new_playlist_files = []
        seen_lower = set()
        for p in self.playlist_files:
            np = os.path.abspath(os.path.normpath(p)).replace('\\', '/')
            if np.lower() == norm_old.lower():
                np = norm_new
            if np.lower() not in seen_lower:
                seen_lower.add(np.lower())
                new_playlist_files.append(np)
        self.playlist_files = new_playlist_files

        found_existing_new = False
        for i in range(self.playlist_widget.count() - 1, -1, -1):
            it = self.playlist_widget.item(i)
            u_path = it.data(Qt.ItemDataRole.UserRole)
            if not u_path:
                continue
            nu = os.path.abspath(os.path.normpath(u_path)).replace('\\', '/')
            if nu.lower() == norm_new.lower():
                if found_existing_new:
                    self.playlist_widget.takeItem(i)
                else:
                    found_existing_new = True
            elif nu.lower() == norm_old.lower():
                if found_existing_new:
                    self.playlist_widget.takeItem(i)
                else:
                    it.setText(new_file_name)
                    it.setToolTip(norm_new)
                    it.setData(Qt.ItemDataRole.UserRole, norm_new)
                    found_existing_new = True

        self.save_playlist_history()

        # 2. 작업 히스토리(task_history.json) 내 원본 경로 일괄 갱신
        history_updated = False
        if hasattr(self, 'task_histories') and isinstance(self.task_histories, list):
            for t in self.task_histories:
                v_in = t.get('video_in')
                if v_in and os.path.abspath(os.path.normpath(v_in)).replace('\\', '/').lower() == norm_old.lower():
                    t['video_in'] = norm_new
                    history_updated = True
            if history_updated:
                save_app_data_json("task_history.json", self.task_histories)
                self.load_task_history()

        # 3. 현재 로드/재생 중인 파일인 경우 재생 중단 없이 경로, 타이틀바, 출력 파일명(nameInput) 동기화
        cached = self.player_widget.video_path_cached
        cur_input = self.fileInput.text().strip()
        is_active = (
            (cached and os.path.abspath(os.path.normpath(cached)).replace('\\', '/').lower() == norm_old.lower()) or
            (cur_input and os.path.abspath(os.path.normpath(cur_input)).replace('\\', '/').lower() == norm_old.lower())
        )
        if is_active:
            self.player_widget.video_path_cached = norm_new
            self.fileInput.blockSignals(True)
            self.fileInput.setText(norm_new)
            self.fileInput.blockSignals(False)
            self.nameInput.setText(new_base)
            self.update_window_title_for_file(norm_new)
            self.update_output_dir()
            self.check_target_file_exists()
            self.update_timeline_cut_highlights()

        self.refresh_playlist_colors()
        self.show_toast(f"외부 이름 변경 반영: '{old_base}' -> '{new_base}'")

    def handle_external_file_deleted(self, deleted_path: str, is_active: bool = False):
        """외부에서 파일이 삭제되었을 때: 재생목록에서 즉시 제거하고, 재생 중인 화면은 정지할 때까지 유지"""
        norm_del = os.path.abspath(os.path.normpath(deleted_path)).replace('\\', '/')
        self.playlist_file_ids.pop(norm_del.lower(), None)

        removed_any = False
        for i in range(self.playlist_widget.count() - 1, -1, -1):
            it = self.playlist_widget.item(i)
            u_path = it.data(Qt.ItemDataRole.UserRole)
            if u_path and os.path.abspath(os.path.normpath(u_path)).replace('\\', '/').lower() == norm_del.lower():
                self.playlist_widget.takeItem(i)
                removed_any = True

        self.playlist_files = [
            p for p in self.playlist_files
            if os.path.abspath(os.path.normpath(p)).replace('\\', '/').lower() != norm_del.lower()
        ]
        if removed_any:
            self.save_playlist_history()
            self.refresh_playlist_colors()

        file_name = os.path.basename(norm_del)
        if is_active:
            from PyQt6.QtMultimedia import QMediaPlayer
            self.player_widget.external_deleted_pending_unload = True
            if self.player_widget.media_player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
                self.player_widget.unload_video()
                self.fileInput.blockSignals(True)
                self.fileInput.setText("")
                self.fileInput.blockSignals(False)
                self.update_window_title_for_file("")
            self.show_toast(f"외부에서 '{file_name}' 삭제됨: 목록에서 제거 (정지 시까지 화면 유지)")
        elif removed_any:
            self.show_toast(f"외부에서 '{file_name}' 파일이 삭제되어 목록에서 제거되었습니다.")

    def check_external_file_changes(self):
        """주기적으로 재생 중인 파일 핸들 및 재생목록 파일의 외부 이름변경/삭제 여부를 점검"""
        if getattr(self, 'is_loading_file', False):
            return

        # 1. 현재 플레이어에 로드/재생 중인 파일 점검
        if self.player_widget.has_video_loaded and self.player_widget.video_path_cached:
            cached = os.path.abspath(os.path.normpath(self.player_widget.video_path_cached)).replace('\\', '/')
            if not getattr(self.player_widget, 'external_deleted_pending_unload', False):
                live_path = self.player_widget.get_current_handle_path()
                if live_path:
                    in_recycle = ("/$recycle.bin/" in live_path.lower())
                    exists_now = os.path.exists(live_path)
                    if in_recycle or not exists_now:
                        self.handle_external_file_deleted(cached, is_active=True)
                    elif live_path.lower() != cached.lower():
                        self.apply_external_file_rename(cached, live_path)
                else:
                    if not os.path.exists(cached):
                        renamed_path = self._find_renamed_file_by_id(cached)
                        if renamed_path and "/$recycle.bin/" not in renamed_path.lower():
                            self.apply_external_file_rename(cached, renamed_path)
                        else:
                            self.handle_external_file_deleted(cached, is_active=True)

        # 2. 재생목록 내 비활성 파일들 점검
        active_lower = (
            os.path.abspath(os.path.normpath(self.player_widget.video_path_cached)).replace('\\', '/').lower()
            if self.player_widget.video_path_cached else ""
        )
        for p in list(self.playlist_files):
            norm_p = os.path.abspath(os.path.normpath(p)).replace('\\', '/')
            if norm_p.lower() == active_lower:
                continue
            if not os.path.exists(norm_p):
                renamed_path = self._find_renamed_file_by_id(norm_p)
                if renamed_path and "/$recycle.bin/" not in renamed_path.lower():
                    self.apply_external_file_rename(norm_p, renamed_path)
                else:
                    self.handle_external_file_deleted(norm_p, is_active=False)

    def closeEvent(self, event):
        """창 종료 시 백그라운드 타이머, 스레드, 모달 창, IPC 서버 및 미디어 핸들을 모두 해제하고 프로세스를 완전 종료"""
        try:
            if hasattr(self, 'fs_sync_timer') and self.fs_sync_timer:
                self.fs_sync_timer.stop()
            if hasattr(self, 'local_server') and self.local_server:
                self.local_server.close()
                QLocalServer.removeServer(SINGLE_INSTANCE_SERVER_NAME)
            if hasattr(self, 'edit_modal') and self.edit_modal:
                self.edit_modal.close()
            if hasattr(self, 'playlist_modal') and self.playlist_modal:
                self.playlist_modal.close()
            if hasattr(self, 'hotkey_modal') and self.hotkey_modal:
                self.hotkey_modal.close()
            if hasattr(self, 'player_widget') and self.player_widget:
                self.player_widget.cleanup()
            if hasattr(self, 'toast_label') and self.toast_label:
                self.toast_label.close()
        except Exception as e:
            logging.error(f"Error during closeEvent cleanup: {e}")
        super().closeEvent(event)
        app = QApplication.instance()
        if app:
            app.quit()
