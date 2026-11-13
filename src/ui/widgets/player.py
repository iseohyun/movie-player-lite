import os
import ctypes
import logging
if os.name == "nt":
    import msvcrt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy, QApplication,
    QGraphicsView, QGraphicsScene
)
from PyQt6.QtCore import Qt, QTimer, QUrl, QPoint, QPointF, QSizeF, QFile, QIODevice, QEvent
from PyQt6.QtGui import QTransform, QPainter, QPen, QColor, QPainterPath, QPolygonF
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
import time
import math

from src.ui.widgets.timeline import TrimmingSliderWidget, ThumbnailGeneratorThread
from src.utils.time_utils import ms_to_time_str
from src.core.i18n import tr


PEN_SHAPE_LABELS = {
    "round": tr("pen.shape.round"),
    "highlighter": tr("pen.shape.highlighter"),
    "dashed": tr("pen.shape.dashed"),
    "glow": tr("pen.shape.glow"),
    "arrow": tr("pen.shape.arrow"),
}

PEN_COLOR_PRESETS = [
    (tr("pen.color.red"), "#ff3b30"),
    (tr("pen.color.yellow"), "#ffeb3b"),
    (tr("pen.color.green"), "#4cd964"),
    (tr("pen.color.blue"), "#007aff"),
    (tr("pen.color.sky"), "#5ac8fa"),
    (tr("pen.color.pink"), "#ff2d55"),
    (tr("pen.color.orange"), "#ff9500"),
    (tr("pen.color.white"), "#ffffff"),
]

PEN_DURATION_PRESETS = [
    (1.0, tr("pen.duration.after", sec="1")),
    (2.0, tr("pen.duration.after", sec="2")),
    (3.0, tr("pen.duration.after", sec="3")),
    (5.0, tr("pen.duration.after", sec="5")),
    (10.0, tr("pen.duration.after", sec="10")),
    (0.0, tr("pen.duration.keep")),
]


class DrawingOverlayWidget(QWidget):
    """동영상 화면 위에 마우스 드래그로 자유곡선 및 잔상(유지 시간 후 페이드아웃)을 그리는 투명 오버레이 캔버스"""

    def __init__(self, player_widget: "EmbeddedVideoPlayer", parent=None):
        super().__init__(parent or player_widget.video_widget)
        self.player = player_widget
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setMouseTracking(True)

        self.strokes = []
        self.current_stroke = None

        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(20)  # ~50fps 부드러운 페이드아웃 갱신
        self.anim_timer.timeout.connect(self._on_anim_tick)

    def set_drawing_mode(self, enabled: bool):
        if enabled:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            if self.current_stroke is not None:
                self.current_stroke["finished_at"] = time.monotonic()
                self.strokes.append(self.current_stroke)
                self.current_stroke = None
                self._ensure_timer()
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.unsetCursor()
        self.update()

    def clear_all(self):
        self.strokes.clear()
        self.current_stroke = None
        if self.anim_timer.isActive():
            self.anim_timer.stop()
        self.update()

    def undo_last(self) -> bool:
        if self.current_stroke is not None:
            self.current_stroke = None
            self.update()
            return True
        if self.strokes:
            self.strokes.pop()
            self.update()
            return True
        return False

    def _ensure_timer(self):
        has_timed = any(s.get("duration_sec", 0.0) > 0 for s in self.strokes)
        if has_timed and not self.anim_timer.isActive():
            self.anim_timer.start()
        elif not has_timed and self.current_stroke is None and self.anim_timer.isActive():
            self.anim_timer.stop()

    def _on_anim_tick(self):
        if not self.strokes and self.current_stroke is None:
            self.anim_timer.stop()
            return

        now = time.monotonic()
        alive = []
        changed = False
        for s in self.strokes:
            dur = float(s.get("duration_sec", 0.0))
            fin = s.get("finished_at")
            if dur <= 0.0 or fin is None:
                alive.append(s)
                continue
            fade_time = min(0.65, max(0.25, dur * 0.35))
            elapsed = now - fin
            if elapsed < dur + fade_time:
                alive.append(s)
                if elapsed >= dur:
                    changed = True
            else:
                changed = True

        if len(alive) != len(self.strokes):
            self.strokes = alive
            changed = True

        if changed or any(
            s.get("duration_sec", 0.0) > 0 and s.get("finished_at") is not None
            and (now - s["finished_at"]) >= s["duration_sec"]
            for s in self.strokes
        ):
            self.update()

        self._ensure_timer()

    def mousePressEvent(self, event):
        if not self.player.drawing_enabled:
            event.ignore()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            self.current_stroke = {
                "points": [QPointF(pos.x(), pos.y())],
                "color": QColor(self.player.pen_color),
                "shape": str(self.player.pen_shape),
                "width": int(self.player.pen_width),
                "opacity": float(self.player.pen_opacity),
                "duration_sec": float(self.player.pen_duration),
                "finished_at": None,
            }
            self.update()
            event.accept()
            return
        elif event.button() == Qt.MouseButton.RightButton:
            main_win = self.player.window()
            if hasattr(main_win, 'show_player_context_menu'):
                main_win.show_player_context_menu(event.globalPosition().toPoint())
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self.player.drawing_enabled:
            event.ignore()
            return
        pos = event.position()
        if (event.buttons() & Qt.MouseButton.LeftButton) and self.current_stroke is not None:
            pts = self.current_stroke["points"]
            new_pt = QPointF(pos.x(), pos.y())
            if not pts or math.hypot(new_pt.x() - pts[-1].x(), new_pt.y() - pts[-1].y()) >= 1.5:
                pts.append(new_pt)
                self.update()
            event.accept()
            return
        else:
            # 드래그 중이 아닐 때만 마우스 오버레이(상단 메뉴바/하단 재생바) 활성화
            self.player.on_mouse_activity(pos.toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if not self.player.drawing_enabled:
            event.ignore()
            return
        if event.button() == Qt.MouseButton.LeftButton and self.current_stroke is not None:
            pos = event.position()
            pts = self.current_stroke["points"]
            new_pt = QPointF(pos.x(), pos.y())
            if not pts or math.hypot(new_pt.x() - pts[-1].x(), new_pt.y() - pts[-1].y()) >= 1.0:
                pts.append(new_pt)
            if len(pts) == 1:
                pts.append(QPointF(pts[0].x() + 0.5, pts[0].y() + 0.5))
            self.current_stroke["finished_at"] = time.monotonic()
            self.strokes.append(self.current_stroke)
            self.current_stroke = None
            self._ensure_timer()
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.player.drawing_enabled:
            w = self.player.window()
            if hasattr(w, 'cycle_fullscreen_mode'):
                w.cycle_fullscreen_mode()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.player.zoom_in()
            elif delta < 0:
                self.player.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    @staticmethod
    def _build_smooth_path(points: list) -> QPainterPath:
        path = QPainterPath()
        if not points:
            return path
        path.moveTo(points[0])
        if len(points) == 1:
            path.lineTo(points[0].x() + 0.5, points[0].y() + 0.5)
            return path
        if len(points) == 2:
            path.lineTo(points[1])
            return path
        for i in range(1, len(points) - 1):
            mid_x = (points[i].x() + points[i + 1].x()) * 0.5
            mid_y = (points[i].y() + points[i + 1].y()) * 0.5
            path.quadTo(points[i], QPointF(mid_x, mid_y))
        path.lineTo(points[-1])
        return path

    def _draw_arrowhead(self, painter: QPainter, points: list, color: QColor, width: int):
        if len(points) < 2:
            return
        tip = points[-1]
        # 방향 계산을 위해 끝점에서 최소 거리가 떨어진 이전 점 탐색
        prev = points[0]
        for idx in range(len(points) - 2, -1, -1):
            if math.hypot(tip.x() - points[idx].x(), tip.y() - points[idx].y()) >= max(6.0, width * 1.5):
                prev = points[idx]
                break
        dx = tip.x() - prev.x()
        dy = tip.y() - prev.y()
        length = math.hypot(dx, dy)
        if length < 1.0:
            return
        angle = math.atan2(dy, dx)
        head_len = max(12.0, width * 3.2)
        wing_angle = math.radians(28)

        p1 = QPointF(
            tip.x() - head_len * math.cos(angle - wing_angle),
            tip.y() - head_len * math.sin(angle - wing_angle),
        )
        p2 = QPointF(
            tip.x() - head_len * math.cos(angle + wing_angle),
            tip.y() - head_len * math.sin(angle + wing_angle),
        )
        painter.save()
        pen = QPen(color, max(2.0, float(width)), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(color)
        poly = QPolygonF([tip, p1, p2])
        painter.drawPolygon(poly)
        painter.restore()

    def _render_stroke(self, painter: QPainter, stroke: dict, now: float):
        pts = stroke.get("points", [])
        if not pts:
            return

        base_opacity = max(0.05, min(1.0, float(stroke.get("opacity", 0.9))))
        dur = float(stroke.get("duration_sec", 0.0))
        fin = stroke.get("finished_at")

        fade_factor = 1.0
        if dur > 0.0 and fin is not None:
            fade_time = min(0.65, max(0.25, dur * 0.35))
            elapsed = now - fin
            if elapsed >= dur + fade_time:
                return
            elif elapsed > dur:
                fade_factor = max(0.0, 1.0 - (elapsed - dur) / fade_time)

        effective_alpha = max(0.0, min(1.0, base_opacity * fade_factor))
        if effective_alpha <= 0.01:
            return

        color = QColor(stroke.get("color", "#ff3b30"))
        color.setAlphaF(effective_alpha)
        width = max(1, int(stroke.get("width", 5)))
        shape = stroke.get("shape", "round")

        path = self._build_smooth_path(pts)

        if shape == "glow":
            # 외곽 네온 광채 + 중심 코어 이중 렌더링
            glow_color = QColor(color)
            glow_color.setAlphaF(min(1.0, effective_alpha * 0.32))
            glow_pen = QPen(glow_color, width * 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

            mid_pen = QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(mid_pen)
            painter.drawPath(path)

            core_color = QColor("#ffffff")
            core_color.setAlphaF(min(1.0, effective_alpha * 0.75))
            core_pen = QPen(core_color, max(1.0, width * 0.35), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(core_pen)
            painter.drawPath(path)
            return

        if shape == "highlighter":
            pen = QPen(color, width * 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.BevelJoin)
        elif shape == "dashed":
            pen = QPen(color, width, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        else:
            # "round" 및 "arrow"
            pen = QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        if shape == "arrow":
            self._draw_arrowhead(painter, pts, color, width)

    def paintEvent(self, event):
        if not self.strokes and self.current_stroke is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        now = time.monotonic()
        for s in self.strokes:
            self._render_stroke(painter, s, now)
        if self.current_stroke is not None:
            self._render_stroke(painter, self.current_stroke, now)
        painter.end()



class EmbeddedVideoPlayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(280)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(1.0)
        self.media_player.setAudioOutput(self.audio_output)

        # 1. 동영상 화면 컨테이너 (기본 최소 베젤 0px, 회전/반전 시 빨간색 저장 대기 테두리 표시)
        self.video_container = QFrame(self)
        self.video_container.setObjectName("video_container")
        self.video_container.setMouseTracking(True)
        self.video_container.setStyleSheet("QFrame#video_container { background-color: #000000; border-radius: 0px; }")
        self.container_layout = QVBoxLayout(self.video_container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)

        self.graphics_scene = QGraphicsScene(self)
        self.graphics_view = QGraphicsView(self.graphics_scene, self.video_container)
        self.graphics_view.setStyleSheet("QGraphicsView { background-color: #000000; border: none; }")
        self.graphics_view.setFrameShape(QFrame.Shape.NoFrame)
        self.graphics_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.graphics_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.graphics_view.setMouseTracking(True)
        if self.graphics_view.viewport():
            self.graphics_view.viewport().setMouseTracking(True)
            self.graphics_view.viewport().installEventFilter(self)

        self.video_item = QGraphicsVideoItem()
        self.graphics_scene.addItem(self.video_item)
        self.media_player.setVideoOutput(self.video_item)
        self.video_item.nativeSizeChanged.connect(lambda _: self.update_transform_border())

        self.video_widget = self.graphics_view
        self.container_layout.addWidget(self.graphics_view, 1)
        main_layout.addWidget(self.video_container, 1)

        # 동영상 위 마우스 드래그 그리기(잔상) 투명 캔버스 오버레이
        self.drawing_overlay = DrawingOverlayWidget(self, self.video_widget)
        self.drawing_overlay.show()

        # 변형 상태 표시 빨간색 배지 (저장 대기 유지)
        self.transform_badge = QLabel(self.video_widget)
        self.transform_badge.setStyleSheet(
            "QLabel { background-color: rgba(255, 59, 48, 0.95); color: #ffffff; font-weight: bold; "
            "font-size: 12px; padding: 6px 12px; border-radius: 4px; }"
        )
        self.transform_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.transform_badge.hide()

        # 그리기 모드 활성화 표시 배지
        self.draw_badge = QLabel(self.video_widget)
        self.draw_badge.setStyleSheet(
            "QLabel { background-color: rgba(0, 120, 215, 0.92); color: #ffffff; font-weight: bold; "
            "font-size: 12px; padding: 5px 11px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.35); }"
        )
        self.draw_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.draw_badge.hide()

        # 비디오 화면 하단 좌측 오버레이 시간/상태 정보 배지 (윗행: 변경상태 요약, 아랫행: 시간)
        self.time_label = QLabel("00:00:00.00 / 00:00:00.00", self.video_widget)
        self.time_label.setStyleSheet(
            "QLabel { color: #ffffff; font-weight: bold; font-family: Consolas, 'Malgun Gothic', monospace; "
            "font-size: 12px; background: rgba(0, 0, 0, 0.75); padding: 5px 10px; border-radius: 4px; "
            "border: 1px solid rgba(255, 255, 255, 0.2); }"
        )
        self.time_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.time_label.adjustSize()
        self.time_label.show()

        # 하단 100% 필름스트립 타임라인 슬라이더 (오버레이 방식, 기본 숨김)
        self.trimming_slider = TrimmingSliderWidget(self)
        self.trimming_slider.position_changed.connect(self.on_slider_seek)
        self.trimming_slider.hide()

        self.show_time_label = True
        self.auto_hide_timeline = True
        self.auto_hide_menubar = True
        self.edit_modal_pinned = False

        # 배속, 확대/축소, 위치 이동, 회전/반전 상태 변수
        self.playback_rate = 1.0
        self.zoom_scale = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.transform_rotation = 0  # 0, 90, 180, 270 degrees
        self.transform_flip_h = False
        self.transform_flip_v = False
        self.is_video_only_fullscreen = False
        self.is_stretch_fill = False
        self.at_end_of_media = False

        # 그리기(드로잉 오버레이) 상태 및 펜 설정 변수
        self.drawing_enabled = False
        self.pen_color = "#ff3b30"
        self.pen_shape = "round"
        self.pen_width = 5
        self.pen_opacity = 0.90
        self.pen_duration = 2.0  # 초 단위 (0.0이면 계속 유지)

        # 시그널 연결
        self.media_player.positionChanged.connect(self.on_position_changed)
        self.media_player.durationChanged.connect(self.on_duration_changed)
        self.media_player.playbackStateChanged.connect(self.on_playback_state_changed)
        self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)

        # 오버레이(메뉴바/재생바) 자동 숨김 타이머
        self.hide_timer = QTimer(self)
        self.hide_timer.setInterval(2200)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_overlay)

        self.drag_start_pos = None

        # 동영상 상세 설정 정보 반투명 노란색 오버레이 HUD (` 키 단독 토글 방식)
        self.info_overlay = QLabel(self)
        self.info_overlay.setWindowFlags(
            Qt.WindowType.ToolTip |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.info_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.info_overlay.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.info_overlay.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.info_overlay.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 0.85);
                color: #ffeb3b;
                border-radius: 6px;
                padding: 8px 12px;
                font-family: Consolas, monospace;
                font-size: 11px;
                border: 1px solid rgba(255, 235, 59, 0.4);
            }
        """)
        self.info_overlay.hide()

        self.video_info = None
        self.has_video_loaded = False
        self.video_path_cached = ""
        self._source_qfile = None
        self._source_win32_handle = None
        self.external_deleted_pending_unload = False
        self._last_hud_text = ""
        self._last_hud_visible = False
        self.force_hud_visible = False  # ` (백틱) 및 메뉴 단독 토글 플래그

        # HUD 실시간 프레임/시각 갱신 타이머 (100ms)
        self.hud_timer = QTimer(self)
        self.hud_timer.setInterval(100)
        self.hud_timer.timeout.connect(self.update_hud)
        self.hud_timer.start()

    def eventFilter(self, obj, event):
        if getattr(self, 'drawing_enabled', False):
            return super().eventFilter(obj, event)
        if event.type() == QEvent.Type.MouseMove:
            self.on_mouse_activity(event.position().toPoint())
        elif event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self.drag_start_pos = event.globalPosition().toPoint()
                self.on_mouse_activity(event.position().toPoint())
            elif event.button() == Qt.MouseButton.RightButton:
                main_win = self.window()
                if hasattr(main_win, 'show_player_context_menu'):
                    main_win.show_player_context_menu(event.globalPosition().toPoint())
                    return True
        elif event.type() == QEvent.Type.MouseButtonRelease:
            self.drag_start_pos = None
        elif event.type() == QEvent.Type.MouseButtonDblClick:
            if event.button() == Qt.MouseButton.LeftButton:
                w = self.window()
                if hasattr(w, 'cycle_fullscreen_mode'):
                    w.cycle_fullscreen_mode()
                else:
                    self.toggle_fullscreen()
                return True
        elif event.type() == QEvent.Type.Wheel:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                delta = event.angleDelta().y()
                if delta > 0:
                    self.zoom_in()
                elif delta < 0:
                    self.zoom_out()
                return True
        return super().eventFilter(obj, event)

    def on_mouse_activity(self, local_pos: QPoint = None):
        self.show_overlay(local_pos)

    def mouseMoveEvent(self, event):
        if getattr(self, 'drawing_enabled', False):
            super().mouseMoveEvent(event)
            return
        self.on_mouse_activity(event.position().toPoint())
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_start_pos is not None:
            top_win = self.window()
            if top_win and not top_win.isFullScreen():
                top_win.move(top_win.pos() + event.globalPosition().toPoint() - self.drag_start_pos)
                self.drag_start_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if getattr(self, 'drawing_enabled', False):
            super().mousePressEvent(event)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.globalPosition().toPoint()
            self.on_mouse_activity(event.position().toPoint())
        elif event.button() == Qt.MouseButton.RightButton:
            main_win = self.window()
            if hasattr(main_win, 'show_player_context_menu'):
                main_win.show_player_context_menu(event.globalPosition().toPoint())
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_start_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not getattr(self, 'drawing_enabled', False):
            w = self.window()
            if hasattr(w, 'cycle_fullscreen_mode'):
                w.cycle_fullscreen_mode()
            else:
                self.toggle_fullscreen()
        super().mouseDoubleClickEvent(event)

    def layout_overlay_widgets(self):
        w = self.width()
        h = self.height()
        if hasattr(self, 'drawing_overlay') and self.drawing_overlay and hasattr(self, 'video_widget') and self.video_widget:
            self.drawing_overlay.setGeometry(0, 0, self.video_widget.width(), self.video_widget.height())
            self.drawing_overlay.raise_()
        slider_h = self.trimming_slider.height() if hasattr(self, 'trimming_slider') else 38
        if hasattr(self, 'trimming_slider') and self.trimming_slider:
            self.trimming_slider.setGeometry(0, max(0, h - slider_h), w, slider_h)
            self.trimming_slider.raise_()
        main_win = self.window()
        if hasattr(main_win, 'layout_top_menu_bar'):
            main_win.layout_top_menu_bar()
        self.update_transform_badge_position()
        self.update_time_label_position()

    def update_transform_badge_position(self):
        main_win = self.window()
        top_offset = 14
        if hasattr(main_win, 'top_menu_bar') and main_win.top_menu_bar and main_win.top_menu_bar.isVisible():
            top_offset = main_win.top_menu_bar.height() + 8
        if hasattr(self, 'transform_badge') and self.transform_badge:
            self.transform_badge.move(14, top_offset)
            self.transform_badge.raise_()
            if self.transform_badge.isVisible():
                top_offset += self.transform_badge.height() + 6
        if hasattr(self, 'draw_badge') and self.draw_badge:
            self.draw_badge.move(14, top_offset)
            self.draw_badge.raise_()

    def show_overlay(self, local_pos: QPoint = None):
        main_win = self.window()
        if hasattr(main_win, 'top_menu_bar') and main_win.top_menu_bar:
            if not self.auto_hide_menubar:
                main_win.top_menu_bar.show()
                main_win.top_menu_bar.raise_()
            else:
                # 마우스 감지 시 상단 오버레이 메뉴바 표시
                main_win.top_menu_bar.show()
                main_win.top_menu_bar.raise_()

        if hasattr(self, 'trimming_slider') and self.trimming_slider:
            self.trimming_slider.show()
            self.trimming_slider.raise_()

        self.update_transform_badge_position()
        self.update_time_label_position()
        self.hide_timer.start()

    def hide_overlay(self):
        main_win = self.window()
        # 1. 상단 메뉴바 숨김 판정
        if hasattr(main_win, 'top_menu_bar') and main_win.top_menu_bar:
            if self.auto_hide_menubar:
                menu_active = main_win.top_menu_bar.activeAction() is not None
                under_mouse = main_win.top_menu_bar.underMouse()
                if not menu_active and not under_mouse:
                    main_win.top_menu_bar.hide()
            else:
                main_win.top_menu_bar.show()
                main_win.top_menu_bar.raise_()

        # 2. 하단 재생바 숨김 판정 (편집 모달이 열려 있으면 고정 표시 유지)
        if hasattr(self, 'trimming_slider') and self.trimming_slider:
            edit_open = bool(getattr(self, 'edit_modal_pinned', False))
            if hasattr(main_win, 'edit_modal') and main_win.edit_modal and main_win.edit_modal.isVisible():
                edit_open = True

            if not self.auto_hide_timeline or edit_open:
                self.trimming_slider.show()
                self.trimming_slider.raise_()
            else:
                dragging = getattr(self.trimming_slider, 'dragging_marker', None) is not None
                under_slider = self.trimming_slider.underMouse()
                if not dragging and not under_slider:
                    self.trimming_slider.hide()

        self.update_transform_badge_position()
        self.update_time_label_position()

    def apply_auto_hide_settings(self):
        """설정 변경 또는 편집 모달 열림/닫힘 시 즉시 메뉴바/재생바 가시성 갱신"""
        main_win = self.window()
        if hasattr(main_win, 'top_menu_bar') and main_win.top_menu_bar:
            if not self.auto_hide_menubar:
                main_win.top_menu_bar.show()
                main_win.top_menu_bar.raise_()
            else:
                main_win.top_menu_bar.hide()

        edit_open = bool(getattr(self, 'edit_modal_pinned', False))
        if hasattr(main_win, 'edit_modal') and main_win.edit_modal and main_win.edit_modal.isVisible():
            edit_open = True

        if not self.auto_hide_timeline or edit_open:
            self.trimming_slider.show()
            self.trimming_slider.raise_()
        else:
            self.trimming_slider.hide()

        self.layout_overlay_widgets()

    def on_slider_seek(self, pos_ms: int):
        dur = self.media_player.duration()
        if dur > 0 and pos_ms < dur - 35:
            self.at_end_of_media = False
        self.media_player.setPosition(pos_ms)

    def step_time(self, delta_ms: int):
        dur = self.media_player.duration()
        if dur <= 0:
            dur = getattr(self.trimming_slider, 'duration_ms', 0)
        if dur <= 0:
            return
        cur_pos = self.media_player.position()
        # 동영상 재생 완료(마지막 프레임 정지) 상태에서 이후로의 이동은 무시
        if delta_ms > 0 and (self.at_end_of_media or cur_pos >= dur - 35):
            return
        if delta_ms < 0:
            self.at_end_of_media = False
        target_max = max(0, dur - 33)
        pos = max(0, min(target_max, cur_pos + delta_ms))
        self.media_player.setPosition(pos)

    def step_frame(self, forward=True):
        dur = self.media_player.duration()
        if dur <= 0:
            dur = getattr(self.trimming_slider, 'duration_ms', 0)
        if dur <= 0:
            return
        fps = 30.0
        if self.video_info and self.video_info.get("fps", 0) > 0:
            fps = float(self.video_info["fps"])
        frame_ms = max(10, int(round(1000.0 / fps)))
        cur_pos = self.media_player.position()
        # 마지막 프레임에서 이후 프레임 이동은 무시
        if forward and (self.at_end_of_media or cur_pos >= dur - frame_ms):
            return
        if not forward:
            self.at_end_of_media = False
        target_max = max(0, dur - frame_ms)
        pos = cur_pos + frame_ms if forward else cur_pos - frame_ms
        pos = max(0, min(target_max, pos))
        self.media_player.setPosition(pos)

    # -------------------------------------------------------------
    # 배속, 볼륨/음소거, 확대/축소/이동 제어 메서드
    # -------------------------------------------------------------
    def set_playback_rate(self, rate: float):
        clamped = round(max(0.25, min(3.0, float(rate))), 2)
        self.playback_rate = clamped
        self.media_player.setPlaybackRate(clamped)
        self.refresh_time_label()
        main_win = self.window()
        if hasattr(main_win, 'sync_menu_check_states'):
            main_win.sync_menu_check_states()
        if hasattr(main_win, 'show_toast'):
            main_win.show_toast(tr("toast.speed", value=f"{clamped:g}"))

    def change_playback_rate(self, delta: float):
        self.set_playback_rate(self.playback_rate + delta)

    def reset_playback_rate(self):
        self.set_playback_rate(1.0)

    def change_volume(self, delta: float):
        if self.audio_output.isMuted() and delta > 0:
            self.audio_output.setMuted(False)
        vol = round(max(0.0, min(1.0, self.audio_output.volume() + delta)), 2)
        self.audio_output.setVolume(vol)
        main_win = self.window()
        if hasattr(main_win, 'sync_menu_check_states'):
            main_win.sync_menu_check_states()
        if hasattr(main_win, 'show_toast'):
            main_win.show_toast(tr("toast.volume", value=int(round(vol * 100))))

    def toggle_mute(self):
        muted = not self.audio_output.isMuted()
        self.audio_output.setMuted(muted)
        main_win = self.window()
        if hasattr(main_win, 'sync_menu_check_states'):
            main_win.sync_menu_check_states()
        if hasattr(main_win, 'show_toast'):
            main_win.show_toast(tr("toast.mute_on") if muted else tr("toast.mute_off"))

    def zoom_in(self, step: float = 0.1):
        self.zoom_scale = round(min(5.0, self.zoom_scale + step), 2)
        self.update_transform_border()
        self.refresh_time_label()
        main_win = self.window()
        if hasattr(main_win, 'show_toast'):
            main_win.show_toast(tr("toast.zoom_in", value=int(round(self.zoom_scale * 100))))

    def zoom_out(self, step: float = 0.1):
        self.zoom_scale = round(max(0.5, self.zoom_scale - step), 2)
        if abs(self.zoom_scale - 1.0) < 1e-4:
            self.zoom_scale = 1.0
        self.update_transform_border()
        self.refresh_time_label()
        main_win = self.window()
        if hasattr(main_win, 'show_toast'):
            main_win.show_toast(tr("toast.zoom_out", value=int(round(self.zoom_scale * 100))))

    def pan_view(self, dx: int, dy: int):
        self.pan_x += int(dx)
        self.pan_y += int(dy)
        self.update_transform_border()
        self.refresh_time_label()

    def reset_zoom_pan(self):
        self.zoom_scale = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.update_transform_border()
        self.refresh_time_label()
        main_win = self.window()
        if hasattr(main_win, 'show_toast'):
            main_win.show_toast(tr("toast.zoom_reset"))

    # -------------------------------------------------------------
    # 그리기(드로잉 오버레이) 모드 및 펜 속성 제어 메서드
    # -------------------------------------------------------------
    def update_draw_badge(self):
        if not hasattr(self, 'draw_badge') or not self.draw_badge:
            return
        if self.drawing_enabled:
            shape_name = PEN_SHAPE_LABELS.get(self.pen_shape, self.pen_shape)
            dur_str = tr("badge.seconds", sec=f"{self.pen_duration:g}") if self.pen_duration > 0 else tr("badge.keep")
            self.draw_badge.setText(
                tr("badge.draw", shape=shape_name, width=self.pen_width, opacity=int(round(self.pen_opacity * 100)), duration=dur_str)
            )
            self.draw_badge.adjustSize()
            self.update_transform_badge_position()
            self.draw_badge.show()
            self.draw_badge.raise_()
        else:
            self.draw_badge.hide()
            self.update_transform_badge_position()

    def set_drawing_enabled(self, enabled: bool, silent: bool = False):
        self.drawing_enabled = bool(enabled)
        if hasattr(self, 'drawing_overlay') and self.drawing_overlay:
            self.drawing_overlay.set_drawing_mode(self.drawing_enabled)
        self.update_draw_badge()
        self.refresh_time_label()
        main_win = self.window()
        if hasattr(main_win, 'sync_menu_check_states'):
            main_win.sync_menu_check_states()
        if hasattr(main_win, 'sync_draw_modal_ui'):
            main_win.sync_draw_modal_ui()
        if not silent and hasattr(main_win, 'show_toast'):
            main_win.show_toast(tr("toast.draw_on") if self.drawing_enabled else tr("toast.draw_off"))

    def toggle_drawing_mode(self):
        self.set_drawing_enabled(not self.drawing_enabled)

    def clear_drawings(self, silent: bool = False):
        if hasattr(self, 'drawing_overlay') and self.drawing_overlay:
            self.drawing_overlay.clear_all()
        main_win = self.window()
        if not silent and hasattr(main_win, 'show_toast'):
            main_win.show_toast(tr("toast.draw_cleared"))

    def undo_last_drawing(self):
        if hasattr(self, 'drawing_overlay') and self.drawing_overlay:
            undone = self.drawing_overlay.undo_last()
            main_win = self.window()
            if hasattr(main_win, 'show_toast'):
                main_win.show_toast(tr("toast.draw_undone") if undone else tr("toast.draw_nothing_to_undo"))

    def set_pen_color(self, color_hex: str, silent: bool = False):
        c = QColor(color_hex)
        if not c.isValid():
            return
        self.pen_color = c.name()
        self.update_draw_badge()
        main_win = self.window()
        if hasattr(main_win, 'sync_menu_check_states'):
            main_win.sync_menu_check_states()
        if hasattr(main_win, 'sync_draw_modal_ui'):
            main_win.sync_draw_modal_ui()
        if hasattr(main_win, 'save_draw_settings'):
            main_win.save_draw_settings()
        if not silent and hasattr(main_win, 'show_toast'):
            color_label = next((name for name, hx in PEN_COLOR_PRESETS if hx.lower() == self.pen_color.lower()), self.pen_color)
            main_win.show_toast(tr("toast.pen_color", value=color_label))

    def set_pen_shape(self, shape_key: str, silent: bool = False):
        if shape_key not in PEN_SHAPE_LABELS:
            return
        self.pen_shape = shape_key
        self.update_draw_badge()
        main_win = self.window()
        if hasattr(main_win, 'sync_menu_check_states'):
            main_win.sync_menu_check_states()
        if hasattr(main_win, 'sync_draw_modal_ui'):
            main_win.sync_draw_modal_ui()
        if hasattr(main_win, 'save_draw_settings'):
            main_win.save_draw_settings()
        if not silent and hasattr(main_win, 'show_toast'):
            main_win.show_toast(tr("toast.pen_shape", value=PEN_SHAPE_LABELS[shape_key]))

    def set_pen_width(self, width: int, silent: bool = False):
        self.pen_width = max(1, min(40, int(width)))
        self.update_draw_badge()
        main_win = self.window()
        if hasattr(main_win, 'sync_menu_check_states'):
            main_win.sync_menu_check_states()
        if hasattr(main_win, 'sync_draw_modal_ui'):
            main_win.sync_draw_modal_ui()
        if hasattr(main_win, 'save_draw_settings'):
            main_win.save_draw_settings()
        if not silent and hasattr(main_win, 'show_toast'):
            main_win.show_toast(tr("toast.pen_width", value=self.pen_width))

    def set_pen_opacity(self, opacity: float, silent: bool = False):
        self.pen_opacity = round(max(0.10, min(1.0, float(opacity))), 2)
        self.update_draw_badge()
        main_win = self.window()
        if hasattr(main_win, 'sync_menu_check_states'):
            main_win.sync_menu_check_states()
        if hasattr(main_win, 'sync_draw_modal_ui'):
            main_win.sync_draw_modal_ui()
        if hasattr(main_win, 'save_draw_settings'):
            main_win.save_draw_settings()
        if not silent and hasattr(main_win, 'show_toast'):
            main_win.show_toast(tr("toast.pen_opacity", value=int(round(self.pen_opacity * 100))))

    def set_pen_duration(self, duration_sec: float, silent: bool = False):
        self.pen_duration = max(0.0, float(duration_sec))
        self.update_draw_badge()
        main_win = self.window()
        if hasattr(main_win, 'sync_menu_check_states'):
            main_win.sync_menu_check_states()
        if hasattr(main_win, 'sync_draw_modal_ui'):
            main_win.sync_draw_modal_ui()
        if hasattr(main_win, 'save_draw_settings'):
            main_win.save_draw_settings()
        if not silent and hasattr(main_win, 'show_toast'):
            dur_label = tr("pen.duration.after", sec=f"{self.pen_duration:g}") if self.pen_duration > 0 else tr("pen.duration.keep")
            main_win.show_toast(tr("toast.pen_duration", value=dur_label))

    # -------------------------------------------------------------
    # 미디어 소스 핸들 (FILE_SHARE_DELETE 지원)
    # -------------------------------------------------------------
    def _close_source_device(self):
        try:
            self.media_player.setSourceDevice(None)
        except Exception:
            pass
        try:
            self.media_player.setSource(QUrl())
        except Exception:
            pass
        if getattr(self, '_source_qfile', None) is not None:
            try:
                if self._source_qfile.isOpen():
                    self._source_qfile.close()
            except Exception as e:
                logging.debug(f"Failed to close _source_qfile: {e}")
            self._source_qfile = None
        self._source_win32_handle = None
        self.external_deleted_pending_unload = False

    def _open_shared_source(self, file_path: str) -> bool:
        """Windows에서 재생 중에도 외부 이름변경/삭제가 가능하도록 FILE_SHARE_DELETE 플래그로 열기"""
        if os.name == "nt":
            try:
                norm_win_path = os.path.abspath(os.path.normpath(file_path))
                GENERIC_READ = 0x80000000
                FILE_SHARE_ALL = 0x00000001 | 0x00000002 | 0x00000004  # READ | WRITE | DELETE
                OPEN_EXISTING = 3
                FILE_ATTRIBUTE_NORMAL = 0x80
                kernel32 = ctypes.windll.kernel32
                kernel32.CreateFileW.restype = ctypes.c_void_p
                handle = kernel32.CreateFileW(
                    norm_win_path,
                    GENERIC_READ,
                    FILE_SHARE_ALL,
                    None,
                    OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL,
                    None,
                )
                invalid_handles = (None, 0, -1, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF)
                if handle not in invalid_handles:
                    fd = msvcrt.open_osfhandle(int(handle), os.O_RDONLY)
                    qf = QFile(self)
                    if qf.open(fd, QIODevice.OpenModeFlag.ReadOnly, QFile.FileHandleFlag.AutoCloseHandle):
                        self._source_qfile = qf
                        self._source_win32_handle = int(handle)
                        self.media_player.setSourceDevice(qf, QUrl.fromLocalFile(file_path))
                        return True
                    else:
                        os.close(fd)
            except Exception as e:
                logging.warning(f"Shared handle open fallback to standard QUrl: {e}")
        self.media_player.setSource(QUrl.fromLocalFile(file_path))
        return False

    def get_current_handle_path(self):
        """현재 열린 Win32 파일 핸들의 실시간 OS 경로를 조회 (외부 이름변경/휴지통 이동 감지)"""
        if os.name != "nt" or not getattr(self, '_source_win32_handle', None):
            return None
        try:
            kernel32 = ctypes.windll.kernel32
            buf = ctypes.create_unicode_buffer(1024)
            length = kernel32.GetFinalPathNameByHandleW(
                ctypes.c_void_p(self._source_win32_handle), buf, 1024, 0
            )
            if length > 0:
                raw_path = buf.value
                if raw_path.startswith("\\\\?\\UNC\\"):
                    raw_path = "\\\\" + raw_path[8:]
                elif raw_path.startswith("\\\\?\\"):
                    raw_path = raw_path[4:]
                return os.path.normpath(raw_path).replace('\\', '/')
        except Exception as e:
            logging.debug(f"GetFinalPathNameByHandleW error: {e}")
        return None

    def stop_thumbnail_thread(self):
        """백그라운드 썸네일 추출 스레드 및 자식 ffmpeg.exe 프로세스를 즉시 종료하여 파일 점유 해제"""
        try:
            ThumbnailGeneratorThread.kill_all()
        except Exception:
            pass
        if hasattr(self, 'thumb_thread') and self.thumb_thread:
            try:
                if hasattr(self.thumb_thread, 'stop_and_kill'):
                    self.thumb_thread.stop_and_kill()
                elif self.thumb_thread.isRunning():
                    self.thumb_thread.requestInterruption()
                    self.thumb_thread.wait(300)
            except Exception:
                pass
            self.thumb_thread = None

    def unload_video(self):
        self.stop_thumbnail_thread()
        self.media_player.stop()
        self._close_source_device()
        self.has_video_loaded = False
        self.video_info = None
        self.video_path_cached = None
        self.at_end_of_media = False
        if hasattr(self, 'info_overlay') and self.info_overlay:
            self.info_overlay.hide()
        if hasattr(self, 'trimming_slider') and self.trimming_slider:
            self.trimming_slider.set_duration(0)
            self.trimming_slider.set_cut_history_regions([])

    def cleanup(self):
        """프로그램 종료 시 모든 타이머, 백그라운드 스레드, 미디어 핸들 및 오버레이 윈도우 정리"""
        if hasattr(self, 'hud_timer') and self.hud_timer:
            self.hud_timer.stop()
        if hasattr(self, 'hide_timer') and self.hide_timer:
            self.hide_timer.stop()
        if hasattr(self, 'drawing_overlay') and self.drawing_overlay:
            self.drawing_overlay.clear_all()
        self.stop_thumbnail_thread()
        self.unload_video()
        if hasattr(self, 'info_overlay') and self.info_overlay:
            self.info_overlay.close()

    def load_video(self, file_path: str, auto_play=True):
        if file_path and os.path.isfile(file_path):
            norm_path = os.path.abspath(os.path.normpath(file_path)).replace('\\', '/')
            self.at_end_of_media = False
            self.stop_thumbnail_thread()
            self.media_player.stop()
            self._close_source_device()
            self._open_shared_source(norm_path)
            self.media_player.setPlaybackRate(self.playback_rate)
            if auto_play:
                self.media_player.play()
            else:
                self.media_player.setPosition(0)
                self.media_player.pause()

            from src.core.metadata import get_detailed_video_info
            try:
                self.video_info = get_detailed_video_info(norm_path)
                self.has_video_loaded = True
                self.video_path_cached = norm_path
            except Exception as e:
                logging.error(f"Failed to load video properties: {e}")
                self.video_info = None
                self.has_video_loaded = False

            self.trimming_slider.placeholder_text = None
            self.trimming_slider.set_thumbnails([])
            self.thumb_thread = ThumbnailGeneratorThread(norm_path, count=10, parent=self)
            self.thumb_thread.thumbnails_ready.connect(self.trimming_slider.set_thumbnail_files)
            self.thumb_thread.start()
            self.reset_transform()
            self.setFocus()

    def load_stream(self, stream_url: str, auto_play=True):
        """네트워크 스트림(예: 유튜브) 재생. 로컬 파일 전용 기능(썸네일 타임라인·상세 정보 HUD)은 쓰지 않는다."""
        self.at_end_of_media = False
        self.stop_thumbnail_thread()
        self.media_player.stop()
        self._close_source_device()
        self.media_player.setSource(QUrl(stream_url))
        self.media_player.setPlaybackRate(self.playback_rate)
        if auto_play:
            self.media_player.play()
        self.video_info = None
        self.has_video_loaded = False
        self.video_path_cached = None
        self.trimming_slider.placeholder_text = tr("timeline.streaming")
        self.trimming_slider.set_thumbnails([])
        self.trimming_slider.set_cut_history_regions([])
        self.reset_transform()
        self.setFocus()

    def is_transformed(self) -> bool:
        return self.transform_rotation != 0 or self.transform_flip_h or self.transform_flip_v

    def update_transform_border(self):
        if self.is_transformed():
            self.video_container.setStyleSheet("QFrame#video_container { background-color: #ff3b30; border-radius: 0px; }")
            if not getattr(self, 'is_video_only_fullscreen', False):
                self.container_layout.setContentsMargins(4, 4, 4, 4)
            parts = []
            if self.transform_rotation != 0:
                parts.append(tr("badge.rotated", deg=self.transform_rotation))
            if self.transform_flip_h:
                parts.append(tr("badge.flip_h"))
            if self.transform_flip_v:
                parts.append(tr("badge.flip_v"))

            desc = " | ".join(parts)
            self.transform_badge.setText(tr("badge.transform", desc=desc))
            self.transform_badge.adjustSize()
            self.update_transform_badge_position()
            self.transform_badge.show()
            self.transform_badge.raise_()
        else:
            self.video_container.setStyleSheet("QFrame#video_container { background-color: #000000; border-radius: 0px; }")
            self.container_layout.setContentsMargins(0, 0, 0, 0)
            self.transform_badge.hide()
            self.update_transform_badge_position()

        # -------------------------------------------------------------
        # Live Visual Transformation & Zoom/Pan on Screen (QGraphicsVideoItem)
        # -------------------------------------------------------------
        if hasattr(self, 'video_item') and self.video_item and hasattr(self, 'graphics_view') and self.graphics_view:
            v_size = self.graphics_view.size()
            cw, ch = float(v_size.width()), float(v_size.height())
            if cw > 0 and ch > 0:
                self.graphics_scene.setSceneRect(0, 0, cw, ch)

                item_size = self.video_item.nativeSize()
                vw = float(item_size.width()) if item_size.width() > 0 else cw
                vh = float(item_size.height()) if item_size.height() > 0 else ch

                if getattr(self, 'is_stretch_fill', False):
                    fit_w, fit_h = cw, ch
                else:
                    if self.transform_rotation in (90, 270):
                        scale = min(cw / vh, ch / vw)
                        fit_w = vw * scale
                        fit_h = vh * scale
                    else:
                        scale = min(cw / vw, ch / vh)
                        fit_w = vw * scale
                        fit_h = vh * scale

                self.video_item.setSize(QSizeF(fit_w, fit_h))

                pos_x = (cw - fit_w) / 2.0 + float(self.pan_x)
                pos_y = (ch - fit_h) / 2.0 + float(self.pan_y)
                self.video_item.setPos(pos_x, pos_y)

                center_x = fit_w / 2.0
                center_y = fit_h / 2.0

                t = QTransform()
                t.translate(center_x, center_y)
                t.scale(float(self.zoom_scale), float(self.zoom_scale))
                t.rotate(float(self.transform_rotation))
                sx = -1.0 if self.transform_flip_h else 1.0
                sy = -1.0 if self.transform_flip_v else 1.0
                t.scale(sx, sy)
                t.translate(-center_x, -center_y)

                self.video_item.setTransform(t)

        self.refresh_time_label()

    def set_fullscreen_mode(self, is_video_only: bool, stretch_fill: bool = False):
        self.is_video_only_fullscreen = is_video_only
        self.is_stretch_fill = stretch_fill
        self.update_transform_border()

    def toggle_time_label(self):
        self.show_time_label = not self.show_time_label
        if hasattr(self, 'time_label') and self.time_label:
            self.time_label.setVisible(self.show_time_label)
        main_win = self.window()
        if hasattr(main_win, 'sync_menu_check_states'):
            main_win.sync_menu_check_states()
        if hasattr(main_win, 'show_toast'):
            main_win.show_toast(tr("toast.time_on") if self.show_time_label else tr("toast.time_off"))

    def toggle_hud_overlay(self):
        """백틱(`) 키 또는 메뉴를 통한 상세 설정 정보 HUD 단독 토글"""
        self.force_hud_visible = not self.force_hud_visible
        main_win = self.window()
        if hasattr(main_win, 'hudCheck') and main_win.hudCheck:
            main_win.hudCheck.blockSignals(True)
            main_win.hudCheck.setChecked(self.force_hud_visible)
            main_win.hudCheck.blockSignals(False)
        if hasattr(main_win, 'sync_menu_check_states'):
            main_win.sync_menu_check_states()
        self.update_hud()
        if hasattr(main_win, 'show_toast'):
            main_win.show_toast(tr("toast.hud_on") if self.force_hud_visible else tr("toast.hud_off"))

    def reset_transform(self):
        self.transform_rotation = 0
        self.transform_flip_h = False
        self.transform_flip_v = False
        self.zoom_scale = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.update_transform_border()

    def flip_horizontal(self):
        self.transform_flip_h = not self.transform_flip_h
        self.update_transform_border()
        status = tr("toast.flip_h_on") if self.transform_flip_h else tr("toast.flip_h_off")
        main_win = self.window()
        if hasattr(main_win, 'show_toast'):
            main_win.show_toast(tr("toast.save_hint", status=status))

    def flip_vertical(self):
        self.transform_flip_v = not self.transform_flip_v
        self.update_transform_border()
        status = tr("toast.flip_v_on") if self.transform_flip_v else tr("toast.flip_v_off")
        main_win = self.window()
        if hasattr(main_win, 'show_toast'):
            main_win.show_toast(tr("toast.save_hint", status=status))

    def rotate_right(self):
        self.transform_rotation = (self.transform_rotation + 90) % 360
        self.update_transform_border()
        main_win = self.window()
        if hasattr(main_win, 'show_toast'):
            main_win.show_toast(tr("toast.rot_right", deg=self.transform_rotation))

    def rotate_left(self):
        self.transform_rotation = (self.transform_rotation - 90) % 360
        self.update_transform_border()
        main_win = self.window()
        if hasattr(main_win, 'show_toast'):
            main_win.show_toast(tr("toast.rot_left", deg=self.transform_rotation))

    def toggle_play(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            dur = self.media_player.duration()
            if self.at_end_of_media or (dur > 0 and self.media_player.position() >= dur - 40):
                self.at_end_of_media = False
                self.media_player.setPosition(0)
            self.media_player.play()
        self.setFocus()

    def on_media_status_changed(self, status):
        """동영상 재생 완료 시 마지막 프레임에서 정지(일시정지 상태 유지)하여 화살표 등으로 즉시 탐색 가능하게 처리"""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if getattr(self, 'external_deleted_pending_unload', False):
                return
            dur = self.media_player.duration()
            if dur > 0:
                self.at_end_of_media = True
                last_pos = max(0, dur - 33)
                self.media_player.setPosition(last_pos)
                self.media_player.pause()
                self.trimming_slider.set_position(dur)
                self.refresh_time_label(override_pos_ms=dur)

    def on_playback_state_changed(self, state):
        if getattr(self, 'external_deleted_pending_unload', False) and state == QMediaPlayer.PlaybackState.StoppedState:
            main_win = self.window()
            QTimer.singleShot(0, self.unload_video)
            if hasattr(main_win, 'fileInput') and main_win.fileInput:
                main_win.fileInput.blockSignals(True)
                main_win.fileInput.setText("")
                main_win.fileInput.blockSignals(False)
        self.setFocus()

    def set_position(self, position):
        dur = self.media_player.duration()
        if dur > 0 and position < dur - 35:
            self.at_end_of_media = False
        self.media_player.setPosition(position)

    def build_status_summary_line(self) -> str:
        """확대/위치/배속/회전/반전 중 변경된 상태가 있을 때만 요약 문자열을 생성 (무변형 시 빈 문자열)"""
        parts = []
        zoom_pct = int(round(self.zoom_scale * 100))
        if zoom_pct != 100 or self.pan_x != 0 or self.pan_y != 0:
            parts.append(tr("status.zoom", zoom=zoom_pct, x=self.pan_x, y=self.pan_y))
        if abs(self.playback_rate - 1.0) > 1e-4:
            parts.append(tr("status.speed", value=f"{self.playback_rate:g}"))
        if self.transform_rotation != 0:
            parts.append(tr("status.rotation", deg=self.transform_rotation))
        if self.transform_flip_h:
            parts.append(tr("status.flip_h"))
        if self.transform_flip_v:
            parts.append(tr("status.flip_v"))
        return " | ".join(parts)

    def refresh_time_label(self, override_pos_ms: int = None):
        if not hasattr(self, 'time_label') or not self.time_label:
            return
        pos_ms = override_pos_ms if override_pos_ms is not None else self.media_player.position()
        dur_ms = self.media_player.duration()
        time_line = f"{ms_to_time_str(pos_ms)} / {ms_to_time_str(dur_ms)}"
        summary_line = self.build_status_summary_line()
        if summary_line:
            self.time_label.setText(f"{summary_line}\n{time_line}")
        else:
            self.time_label.setText(time_line)
        self.update_time_label_position()

    def on_position_changed(self, position_ms):
        dur_ms = self.media_player.duration()
        if (
            self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
            and dur_ms > 0
            and position_ms >= dur_ms - 30
            and not getattr(self, 'external_deleted_pending_unload', False)
        ):
            self.at_end_of_media = True
            self.media_player.pause()
            self.trimming_slider.set_position(dur_ms)
            self.refresh_time_label(override_pos_ms=dur_ms)
            return

        self.trimming_slider.set_position(position_ms)
        self.refresh_time_label(override_pos_ms=position_ms)

    def on_duration_changed(self, duration_ms):
        self.trimming_slider.set_duration(duration_ms)
        self.refresh_time_label()

    def update_time_label_position(self):
        if hasattr(self, 'time_label') and self.time_label and hasattr(self, 'video_widget') and self.video_widget:
            self.time_label.adjustSize()
            vw_h = self.video_widget.height()
            tl_h = self.time_label.height()
            bottom_margin = 14
            if hasattr(self, 'trimming_slider') and self.trimming_slider and self.trimming_slider.isVisible():
                bottom_margin = self.trimming_slider.height() + 10
            if vw_h > 0:
                self.time_label.move(14, max(14, vw_h - tl_h - bottom_margin))
                self.time_label.raise_()

    def toggle_fullscreen(self):
        w = self.window()
        if w:
            if w.isFullScreen():
                w.showNormal()
            else:
                w.showFullScreen()
        self.setFocus()

    def update_hud(self):
        # 백틱(`) 단독 토글 방식으로 동작 (CapsLock 연동 제거)
        should_show = bool(self.force_hud_visible) and self.has_video_loaded and bool(self.video_info)

        top_win = self.window()
        if top_win:
            if not top_win.isActiveWindow() or top_win.isMinimized() or not top_win.isVisible() or not self.isVisible():
                should_show = False

        if should_show:
            pos_ms = self.media_player.position()
            fps = self.video_info.get("fps", 0.0)

            if fps > 0:
                sec_part = (pos_ms % 1000) / 1000.0
                frame_idx = int(round(sec_part * fps))
                frame_str = f"+ {frame_idx:02d}f"
            else:
                frame_str = ""

            time_str = ms_to_time_str(pos_ms)
            ctrl_pressed = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier)

            text = (
                f"{tr('hud.title')}\n"
                f"• {tr('hud.file')}: {os.path.basename(self.video_path_cached)}\n"
                f"• {tr('hud.resolution')}: {self.video_info.get('width', 0)}x{self.video_info.get('height', 0)} ({self.video_info.get('nickname', '')})\n"
                f"• {tr('hud.ratio')}: {self.video_info.get('aspect_ratio', '')}\n"
                f"• {tr('hud.frame')}: {fps:.2f} fps\n"
                f"• {tr('hud.duration')}: {self.video_info.get('duration', '')}\n"
                f"• {tr('hud.current')}: {time_str} {frame_str}\n"
                f"• {tr('hud.speed_zoom')}: {self.playback_rate:g}x / {int(round(self.zoom_scale * 100))}% (X:{self.pan_x}, Y:{self.pan_y})\n"
                f"• {tr('hud.bitrate')}: {self.video_info.get('bitrate', '')}\n"
                f"• {tr('hud.bit_depth')}: {self.video_info.get('bit_depth', '')} ({self.video_info.get('pix_fmt', '')})"
            )

            if ctrl_pressed:
                meta_lines = []
                for k, v in self.video_info.get("metadata", {}).items():
                    if len(meta_lines) >= 10:
                        break
                    meta_lines.append(f"{k}: {v}")
                meta_str = "\n  ".join(meta_lines) if meta_lines else "None"
                text += f"\n• {tr('hud.metadata')}:\n  {meta_str}"
            else:
                text += f"\n\n{tr('hud.ctrl_hint')}"

            if text != self._last_hud_text:
                self.info_overlay.setText(text)
                self.info_overlay.adjustSize()
                self._last_hud_text = text

            top_y = 12
            if hasattr(top_win, 'top_menu_bar') and top_win.top_menu_bar and top_win.top_menu_bar.isVisible():
                top_y = top_win.top_menu_bar.height() + 8
            if self.transform_badge.isVisible():
                top_y = self.transform_badge.y() + self.transform_badge.height() + 8
            if hasattr(self, 'draw_badge') and self.draw_badge.isVisible():
                top_y = self.draw_badge.y() + self.draw_badge.height() + 8

            gpos = self.video_widget.mapToGlobal(QPoint(12, top_y))
            self.info_overlay.move(gpos)
            self.info_overlay.raise_()

            if not self._last_hud_visible:
                self.info_overlay.show()
                self.info_overlay.raise_()
                self._last_hud_visible = True
        else:
            if self._last_hud_visible:
                self.info_overlay.hide()
                self._last_hud_visible = False
                self._last_hud_text = ""

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.layout_overlay_widgets()
        if hasattr(self, 'graphics_view') and hasattr(self, 'video_item'):
            v_size = self.graphics_view.size()
            w, h = float(v_size.width()), float(v_size.height())
            if w > 0 and h > 0:
                self.graphics_scene.setSceneRect(0, 0, w, h)
                self.video_item.setSize(QSizeF(w, h))
                self.video_item.setTransformOriginPoint(w / 2.0, h / 2.0)
                self.update_transform_border()
        if self._last_hud_visible and self.video_widget.isVisible():
            self.update_hud()
