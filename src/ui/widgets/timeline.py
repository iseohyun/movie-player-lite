import os
import tempfile
import logging
import subprocess
from PyQt6.QtWidgets import QWidget, QStyle, QSlider
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QRectF
from PyQt6.QtGui import QPainter, QPixmap, QColor, QPen, QBrush
from PyQt6.QtMultimedia import QMediaPlayer

from src.core.metadata import get_ffmpeg_path, get_media_creation_time_and_duration

class FilmstripWidget(QWidget):
    """동영상 재생 바 배경에 그려지는 대표 씬 썸네일 스트립"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self.pixmaps = []
        self.setStyleSheet("background-color: #111; border-radius: 4px;")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_thumbnail_files(self, paths):
        pixmaps = []
        for p in paths:
            if os.path.exists(p):
                pm = QPixmap(p)
                if not pm.isNull():
                    pixmaps.append(pm)
        self.pixmaps = pixmaps
        self.update()

    def set_thumbnails(self, pixmaps):
        self.pixmaps = pixmaps
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        if not self.pixmaps:
            painter.setPen(Qt.GlobalColor.darkGray)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "썸네일 바 로딩 중...")
            return

        n = len(self.pixmaps)
        w = float(self.width()) / float(n)
        h = float(self.height())

        for i, pm in enumerate(self.pixmaps):
            rect = QRectF(i * w, 0, w, h)
            scaled = pm.scaled(int(w), int(h), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(rect.toRect(), scaled)


class ThumbnailGeneratorThread(QThread):
    """FFmpeg를 이용하여 동영상의 주요 씬 썸네일을 비동기로 생성하는 스레드 (즉시 중단 및 서브프로세스 강제 종료 지원)"""
    thumbnails_ready = pyqtSignal(list)
    _active_threads = set()

    def __init__(self, video_path: str, count: int = 10, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.count = count
        self._proc = None
        ThumbnailGeneratorThread._active_threads.add(self)

    def _kill_proc(self):
        proc = self._proc
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=1.0)
            except Exception as e:
                logging.debug(f"[ThumbThread] Proc kill error: {e}")
            finally:
                self._proc = None

    def stop_and_kill(self):
        """스레드 중단 요청 및 실행 중인 ffmpeg.exe 자식 프로세스 즉시 강제 종료 (파일 점유 즉시 해제)"""
        self.requestInterruption()
        self._kill_proc()
        if self.isRunning():
            self.wait(400)

    @classmethod
    def kill_all(cls, target_path: str = None) -> int:
        """현재 실행 중인 모든(또는 특정 파일 대상) 썸네일 추출 ffmpeg.exe 프로세스를 즉시 종료"""
        from src.core.lock_resolver import norm_path_key
        target_key = norm_path_key(target_path) if target_path else ""
        killed = 0
        for th in list(cls._active_threads):
            try:
                if not target_key or norm_path_key(th.video_path) == target_key:
                    th.stop_and_kill()
                    killed += 1
            except Exception:
                pass
        return killed

    def _run_ffmpeg_cancellable(self, cmd: list[str]) -> bool:
        if self.isInterruptionRequested():
            return False
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            while self._proc is not None and self._proc.poll() is None:
                if self.isInterruptionRequested():
                    self._kill_proc()
                    return False
                self.msleep(30)
            return True
        except Exception as e:
            logging.debug(f"[ThumbThread] Popen error: {e}")
            self._kill_proc()
            return False
        finally:
            self._kill_proc()

    def run(self):
        try:
            if self.isInterruptionRequested():
                return
            logging.info(f"[ThumbThread] Target video: {self.video_path}")
            duration_cs, _ = get_media_creation_time_and_duration(self.video_path)
            duration_sec = duration_cs / 100.0
            logging.info(f"[ThumbThread] Duration: {duration_sec}s")
            if duration_sec <= 0 or self.isInterruptionRequested():
                return

            ffmpeg_bin = get_ffmpeg_path()
            temp_dir = os.path.join(tempfile.gettempdir(), "mp4_trim_thumbs")
            os.makedirs(temp_dir, exist_ok=True)

            vid_hash = abs(hash(self.video_path)) % 100000
            for i in range(1, self.count + 1):
                old_p = os.path.join(temp_dir, f"thumb_{vid_hash}_{i:02d}.jpg")
                if os.path.exists(old_p):
                    try:
                        os.remove(old_p)
                    except OSError:
                        pass

            interval = max(0.2, duration_sec / float(self.count))
            fps_val = 1.0 / interval
            out_pattern = os.path.join(temp_dir, f"thumb_{vid_hash}_%02d.jpg").replace('\\', '/')

            # 긴 영상(8초 이상)은 키프레임 고속 디코딩(-skip_frame nokey)을 우선 적용하여
            # 4K/HEVC 영상의 파일 점유 시간을 수십 초에서 1초 미만으로 단축
            if duration_sec >= 8.0:
                fast_cmd = [
                    ffmpeg_bin, "-y",
                    "-skip_frame", "nokey",
                    "-i", self.video_path,
                    "-vf", f"fps={fps_val:.4f},scale=120:68",
                    "-vframes", str(self.count),
                    out_pattern
                ]
                self._run_ffmpeg_cancellable(fast_cmd)

            if self.isInterruptionRequested():
                return

            paths = [
                os.path.join(temp_dir, f"thumb_{vid_hash}_{i:02d}.jpg").replace('\\', '/')
                for i in range(1, self.count + 1)
                if os.path.exists(os.path.join(temp_dir, f"thumb_{vid_hash}_{i:02d}.jpg"))
                and os.path.getsize(os.path.join(temp_dir, f"thumb_{vid_hash}_{i:02d}.jpg")) > 0
            ]

            # 짧은 영상이거나 키프레임이 부족해 썸네일이 3장 미만인 경우 일반 추출 수행
            if len(paths) < min(3, self.count) and not self.isInterruptionRequested():
                cmd = [
                    ffmpeg_bin, "-y",
                    "-i", self.video_path,
                    "-vf", f"fps={fps_val:.4f},scale=120:68",
                    "-vframes", str(self.count),
                    out_pattern
                ]
                self._run_ffmpeg_cancellable(cmd)
                if self.isInterruptionRequested():
                    return
                paths = [
                    os.path.join(temp_dir, f"thumb_{vid_hash}_{i:02d}.jpg").replace('\\', '/')
                    for i in range(1, self.count + 1)
                    if os.path.exists(os.path.join(temp_dir, f"thumb_{vid_hash}_{i:02d}.jpg"))
                    and os.path.getsize(os.path.join(temp_dir, f"thumb_{vid_hash}_{i:02d}.jpg")) > 0
                ]

            logging.info(f"[ThumbThread] Extracted {len(paths)} / {self.count} thumbnails")
            if paths and not self.isInterruptionRequested():
                self.thumbnails_ready.emit(paths)
        except Exception as e:
            logging.error(f"[ThumbThread] Exception: {e}", exc_info=True)
        finally:
            self._kill_proc()
            ThumbnailGeneratorThread._active_threads.discard(self)


class JumpSlider(QSlider):
    """클릭한 위치로 타임스탬프가 즉시 이동하는 슬라이더"""
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            val = QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(), int(event.position().x()), self.width()
            )
            self.setValue(val)
            self.sliderMoved.emit(val)
        super().mousePressEvent(event)


class TrimmingSliderWidget(QWidget):
    """
    100% 비디오 플레이어 너비에 맞춰 표시되는 필름스트립 타임라인 바.
    - 10개 대표 씬 썸네일 타일링
    - 선택 구간 [Start, End] 밝게 표시 / 구간 밖은 반투명 어둡게 표시
    - 1px 녹색 편집점 시작/종료 세로선 (전체 높이)
    - 1px 빨간색 현재 재생 시점 세로선 (전체 높이)
    - 마커 클릭 선택 후 좌우 화살표키(← / →) 미세 조작 지원
    - 마우스 드래그로 시작점/종료점/재생 헤드 자유 이동
    """
    position_changed = pyqtSignal(int)   # ms
    start_changed = pyqtSignal(int)      # ms
    end_changed = pyqtSignal(int)        # ms
    region_selected = pyqtSignal(dict)
    region_rename_requested = pyqtSignal(int, dict)
    region_delete_requested = pyqtSignal(int, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        self.pixmaps = []

        self.duration_ms = 1000
        self.position_ms = 0
        self.start_ms = 0
        self.end_ms = 1000

        self.active_marker = None     # 'start', 'end', 'playhead'
        self.dragging_marker = None
        self.cut_history_regions = []
        self.selected_region_index = -1

    def set_thumbnail_files(self, paths):
        pixmaps = []
        for p in paths:
            if os.path.exists(p):
                pm = QPixmap(p)
                if not pm.isNull():
                    pixmaps.append(pm)
        self.pixmaps = pixmaps
        self.update()

    def set_thumbnails(self, pixmaps):
        self.pixmaps = pixmaps
        self.update()

    def set_duration(self, dur_ms: int):
        if dur_ms > 0:
            old_dur = self.duration_ms
            self.duration_ms = dur_ms
            if self.end_ms == old_dur or self.end_ms > dur_ms or self.end_ms == 0:
                self.end_ms = dur_ms
            self.update()

    def set_position(self, pos_ms: int):
        self.position_ms = max(0, min(self.duration_ms, pos_ms))
        self.update()

    def set_cut_history_regions(self, regions: list):
        self.cut_history_regions = regions
        self.update()

    def set_start_ms(self, start_ms: int):
        val = max(0, min(self.end_ms, start_ms))
        if self.start_ms != val:
            self.start_ms = val
            self.update()

    def set_end_ms(self, end_ms: int):
        val = max(self.start_ms, min(self.duration_ms, end_ms))
        if self.end_ms != val:
            self.end_ms = val
            self.update()

    def ms_to_x(self, ms: int) -> float:
        if self.duration_ms <= 0:
            return 0.0
        return (ms / float(self.duration_ms)) * float(self.width())

    def x_to_ms(self, x: float) -> int:
        if self.width() <= 0:
            return 0
        ratio = max(0.0, min(1.0, x / float(self.width())))
        return int(ratio * self.duration_ms)

    def paintEvent(self, event):
        super().paintEvent(event)
        w = float(self.width())
        h = float(self.height())
        if w <= 0 or h <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 0. 배경 썸네일 타일링 그리기
        if self.pixmaps:
            n = len(self.pixmaps)
            tw = w / float(n)
            for i, pm in enumerate(self.pixmaps):
                rect = QRectF(i * tw, 0, tw, h)
                scaled = pm.scaled(int(tw), int(h), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                painter.drawPixmap(rect.toRect(), scaled)
        else:
            painter.fillRect(QRectF(0, 0, w, h), QColor(17, 17, 17))
            painter.setPen(QColor(128, 128, 128))
            painter.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "썸네일 로딩 중...")

        sx = self.ms_to_x(self.start_ms)
        ex = self.ms_to_x(self.end_ms)
        px = self.ms_to_x(self.position_ms)

        # 0.2. 상단 시간 보조선 (자 디자인: 1초-짧은선, 5초-중간선, 10초-긴선 + 시간표시)
        if self.duration_ms > 0:
            dur_sec = int(self.duration_ms / 1000)
            px_per_sec = w / float(max(1, dur_sec))
            
            step_sec = 1
            if px_per_sec < 3.0:
                step_sec = 5
            if px_per_sec < 1.0:
                step_sec = 10

            font = painter.font()
            font.setPointSize(7)
            font.setBold(False)
            painter.setFont(font)

            for s in range(0, dur_sec + 1, step_sec):
                tx = self.ms_to_x(s * 1000)
                if tx < 0 or tx > w:
                    continue

                if s % 10 == 0:
                    # 10초 마다: 긴 선 (12px) + 시간 텍스트
                    painter.setPen(QPen(QColor(255, 255, 255, 220), 1.5))
                    painter.drawLine(int(tx), 0, int(tx), 12)
                    
                    time_str = f"{s//60:02d}:{s%60:02d}"
                    if tx + 35 < w and (px_per_sec >= 1.5 or s % 30 == 0):
                        painter.setPen(QColor(255, 255, 255, 190))
                        painter.drawText(QRectF(tx + 2, 0, 32, 12), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, time_str)
                elif s % 5 == 0:
                    # 5초 마다: 중간 선 (8px)
                    painter.setPen(QPen(QColor(255, 255, 255, 170), 1))
                    painter.drawLine(int(tx), 0, int(tx), 8)
                else:
                    # 1초 마다: 짧은 선 (4px)
                    painter.setPen(QPen(QColor(255, 255, 255, 120), 1))
                    painter.drawLine(int(tx), 0, int(tx), 4)

        # 0.5. 컷팅 히스토리 구간 하이라이트 (하위 40% 영역만 밝게 표시, 상단 60%에는 영상제목)
        if self.cut_history_regions and self.duration_ms > 0:
            for idx, region in enumerate(self.cut_history_regions):
                r_start = region.get('start_ms', 0)
                r_end = region.get('end_ms', 0)
                r_name = region.get('name', '')
                
                rx1 = self.ms_to_x(r_start)
                rx2 = self.ms_to_x(r_end)
                rw = max(3.0, rx2 - rx1)
                
                # 하위 40% 영역 하이라이트 (선택 시 주황색/빨간 테두리 강조)
                highlight_rect = QRectF(rx1, h * 0.6, rw, h * 0.4)
                if idx == self.selected_region_index:
                    painter.fillRect(highlight_rect, QColor(255, 152, 0, 240))
                    painter.setPen(QPen(QColor(255, 59, 48), 2))
                    painter.drawRect(highlight_rect)
                else:
                    painter.fillRect(highlight_rect, QColor(255, 235, 59, 220))
                
                # 상단 60% 영역 컷팅 제목 라벨 노출
                if r_name and rw > 15:
                    label_rect = QRectF(rx1, 0, rw, h * 0.6)
                    painter.setPen(QColor(255, 255, 255, 240))
                    font = painter.font()
                    font.setPointSize(9)
                    font.setBold(True)
                    painter.setFont(font)
                    painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextSingleLine, r_name)

        # 1. 선택 영역 밖 (0 ~ start_ms, end_ms ~ duration_ms) 반투명 블랙 딤(Dim) 처리
        dim_color = QColor(0, 0, 0, 160)
        if sx > 0:
            painter.fillRect(QRectF(0, 0, sx, h), dim_color)
        if ex < w:
            painter.fillRect(QRectF(ex, 0, w - ex, h), dim_color)

        # 2. 선택된 유효 구간 [start_ms, end_ms] 테두리 강조
        border_pen = QPen(QColor(0, 120, 215, 220), 1)
        painter.setPen(border_pen)
        painter.drawRect(QRectF(sx, 1, max(1.0, ex - sx), h - 2))

        # 3. 편집점 시작 마커 (재생바 전체 높이 1px 녹색 세로선)
        start_color = QColor(0, 230, 118) if self.active_marker == 'start' else QColor(0, 200, 83)
        painter.setPen(QPen(start_color, 1))
        painter.drawLine(int(sx), 0, int(sx), int(h))

        # 4. 편집점 종료 마커 (재생바 전체 높이 1px 녹색 세로선)
        end_color = QColor(0, 230, 118) if self.active_marker == 'end' else QColor(0, 200, 83)
        painter.setPen(QPen(end_color, 1))
        painter.drawLine(int(ex), 0, int(ex), int(h))

        # 5. 현재 재생 헤드 (재생바 전체 높이 1px 빨간색 세로선)
        playhead_color = QColor(255, 59, 48)
        painter.setPen(QPen(playhead_color, 1))
        painter.drawLine(int(px), 0, int(px), int(h))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            x = event.position().x()
            sx = self.ms_to_x(self.start_ms)
            ex = self.ms_to_x(self.end_ms)
            px = self.ms_to_x(self.position_ms)

            # 재생 중에 재생바를 클릭/조작 시 일시 정지
            if hasattr(self.parent(), 'media_player') and self.parent().media_player:
                if self.parent().media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                    self.parent().media_player.pause()

            if abs(x - sx) <= 10:
                self.active_marker = 'start'
                self.dragging_marker = 'start'
                self.selected_region_index = -1
            elif abs(x - ex) <= 10:
                self.active_marker = 'end'
                self.dragging_marker = 'end'
                self.selected_region_index = -1
            elif abs(x - px) <= 8:
                self.active_marker = 'playhead'
                self.dragging_marker = 'playhead'
                self.selected_region_index = -1
            else:
                # 컷 히스토리 노란색 영역 클릭 여부 검사
                clicked_region_idx = -1
                if self.cut_history_regions and self.duration_ms > 0:
                    for idx, region in enumerate(self.cut_history_regions):
                        r_start = region.get('start_ms', 0)
                        r_end = region.get('end_ms', 0)
                        rx1 = self.ms_to_x(r_start)
                        rx2 = self.ms_to_x(r_end)
                        if rx1 <= x <= rx2:
                            clicked_region_idx = idx
                            break

                if clicked_region_idx >= 0:
                    self.selected_region_index = clicked_region_idx
                    target_region = self.cut_history_regions[clicked_region_idx]
                    r_start = target_region.get('start_ms', 0)
                    r_end = target_region.get('end_ms', 0)

                    self.set_start_ms(r_start)
                    self.set_end_ms(r_end)
                    self.set_position(r_start)

                    self.start_changed.emit(r_start)
                    self.end_changed.emit(r_end)
                    self.position_changed.emit(r_start)
                    self.region_selected.emit(target_region)
                else:
                    self.selected_region_index = -1
                    self.active_marker = 'playhead'
                    self.dragging_marker = 'playhead'
                    new_ms = self.x_to_ms(x)
                    self.position_ms = new_ms
                    self.position_changed.emit(new_ms)
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            self.setFocus()
            self.update()

    def mouseMoveEvent(self, event):
        x = event.position().x()
        sx = self.ms_to_x(self.start_ms)
        ex = self.ms_to_x(self.end_ms)
        px = self.ms_to_x(self.position_ms)

        if self.dragging_marker:
            if hasattr(self.parent(), 'media_player') and self.parent().media_player:
                if self.parent().media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                    self.parent().media_player.pause()
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            new_ms = self.x_to_ms(x)
            
            # Ctrl 눌려있을 때 빨간 세로선(현재 재생 시점)으로 자석 스냅 기능
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                if self.dragging_marker in ('start', 'end'):
                    if abs(x - px) <= 12:
                        new_ms = self.position_ms

            if self.dragging_marker == 'start':
                self.start_ms = max(0, min(self.end_ms, new_ms))
                self.start_changed.emit(self.start_ms)
            elif self.dragging_marker == 'end':
                self.end_ms = max(self.start_ms, min(self.duration_ms, new_ms))
                self.end_changed.emit(self.end_ms)
            elif self.dragging_marker == 'playhead':
                self.position_ms = new_ms
                self.position_changed.emit(self.position_ms)
            self.update()
        else:
            if abs(x - sx) <= 10 or abs(x - ex) <= 10 or abs(x - px) <= 8:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        self.dragging_marker = None
        x = event.position().x()
        sx = self.ms_to_x(self.start_ms)
        ex = self.ms_to_x(self.end_ms)
        px = self.ms_to_x(self.position_ms)
        if abs(x - sx) <= 10 or abs(x - ex) <= 10 or abs(x - px) <= 8:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setFocus()
        if self.parent() and hasattr(self.parent(), 'setFocus'):
            self.parent().setFocus()
        self.update()

    def leaveEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F2:
            if 0 <= self.selected_region_index < len(self.cut_history_regions):
                self.region_rename_requested.emit(self.selected_region_index, self.cut_history_regions[self.selected_region_index])
                return
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if 0 <= self.selected_region_index < len(self.cut_history_regions):
                self.region_delete_requested.emit(self.selected_region_index, self.cut_history_regions[self.selected_region_index])
                return

        step_ms = 1000
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # 1프레임 이동 (FPS 기반 계산)
            fps = 30.0
            parent_player = self.parent()
            if hasattr(parent_player, 'video_info') and parent_player.video_info and parent_player.video_info.get("fps", 0) > 0:
                fps = float(parent_player.video_info["fps"])
            step_ms = max(1, int(round(1000.0 / fps)))

        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            delta = step_ms if event.key() == Qt.Key.Key_Right else -step_ms
            if self.active_marker == 'start':
                self.start_ms = max(0, min(self.end_ms, self.start_ms + delta))
                self.start_changed.emit(self.start_ms)
            elif self.active_marker == 'end':
                self.end_ms = max(self.start_ms, min(self.duration_ms, self.end_ms + delta))
                self.end_changed.emit(self.end_ms)
            elif self.active_marker == 'playhead':
                new_ms = max(0, min(self.duration_ms, self.position_ms + delta))
                self.position_ms = new_ms
                self.position_changed.emit(new_ms)
            self.update()
        else:
            super().keyPressEvent(event)
