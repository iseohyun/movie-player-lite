from PyQt6.QtWidgets import QMenu
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QFontMetrics, QPainter

HOTKEY_ID_PROPERTY = "hotkey_id"
HINT_RIGHT_MARGIN = 12      # 단축키 문구와 메뉴 오른쪽 끝 사이 여백(px)
HINT_LABEL_GAP = 16         # 가장 긴 항목 이름과 단축키 문구 사이 최소 간격(px)
HINT_COLOR = QColor(255, 255, 255, 120)          # 약간 옅은 색
HINT_COLOR_ACTIVE = QColor(255, 255, 255, 210)   # 마우스가 올라간 항목


def bind_hotkey_hint(action: QAction, hotkey_id: str):
    """메뉴 항목에 단축키 ID를 연결한다. ShortcutHintMenu가 오른쪽에 현재 단축키를 표시한다."""
    action.setProperty(HOTKEY_ID_PROPERTY, hotkey_id)


class ShortcutHintMenu(QMenu):
    """항목 이름은 왼쪽, 단축키는 오른쪽 정렬·옅은 색으로 그리는 메뉴.

    단축키 문구는 hint_provider(hotkey_id)로 매번 조회하므로 사용자가 단축키를 바꾸면 바로 반영된다.
    """

    def __init__(self, title: str, hint_provider, parent=None):
        super().__init__(title, parent)
        self._hint_provider = hint_provider
        self.aboutToShow.connect(self._reserve_hint_width)

    def _hint_for(self, action: QAction) -> str:
        if action.isSeparator() or action.menu():
            return ""
        hotkey_id = action.property(HOTKEY_ID_PROPERTY)
        return self._hint_provider(hotkey_id) if hotkey_id else ""

    def _mark_layout_dirty(self):
        # QMenu는 항목이 바뀔 때만 항목 영역을 다시 계산하므로 임시 항목을 넣었다 빼서 재계산을 유도한다.
        probe = QAction(self)
        self.addAction(probe)
        self.removeAction(probe)

    def _reserve_hint_width(self):
        metrics = QFontMetrics(self.font())
        widest_hint = max((metrics.horizontalAdvance(self._hint_for(a)) for a in self.actions()), default=0)
        self.setMinimumWidth(0)
        self._mark_layout_dirty()
        if widest_hint <= 0:
            return
        base_width = self.sizeHint().width()
        self.setMinimumWidth(base_width + widest_hint + HINT_LABEL_GAP)
        self._mark_layout_dirty()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setFont(self.font())
        active = self.activeAction()
        for action in self.actions():
            hint = self._hint_for(action)
            if not hint:
                continue
            rect = self.actionGeometry(action).adjusted(0, 0, -HINT_RIGHT_MARGIN, 0)
            painter.setPen(HINT_COLOR_ACTIVE if action is active else HINT_COLOR)
            painter.drawText(rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, hint)
        painter.end()
