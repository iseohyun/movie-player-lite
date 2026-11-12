from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent

from src.core.hotkeys import event_to_key_str
from src.core.i18n import tr

class KeyCaptureDialog(QDialog):
    """새로운 단축키 조합을 감지하고 저장하는 대화상자"""
    def __init__(self, action_name: str, key_type: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("keycap.title"))
        self.setFixedSize(320, 140)
        self.captured_key_str = None

        layout = QVBoxLayout(self)
        label = QLabel(f"<b>{action_name}</b> ({key_type})<br><br>{tr('keycap.prompt')}")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        btn_box = QHBoxLayout()
        self.clear_btn = QPushButton(tr("keycap.clear"))
        self.cancel_btn = QPushButton(tr("common.cancel"))
        self.clear_btn.clicked.connect(self.on_clear)
        self.cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(self.clear_btn)
        btn_box.addWidget(self.cancel_btn)
        layout.addLayout(btn_box)

    def on_clear(self):
        self.captured_key_str = ""
        self.accept()

    def keyPressEvent(self, event: QKeyEvent):
        key_str = event_to_key_str(event)
        if key_str:
            self.captured_key_str = key_str
            self.accept()
        else:
            super().keyPressEvent(event)
