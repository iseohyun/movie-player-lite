import os
import array
import tempfile
import logging
import subprocess
from PyQt6.QtWidgets import QWidget, QStyle, QSlider
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QRectF
from PyQt6.QtGui import QPainter, QPixmap, QColor, QPen, QBrush
from PyQt6.QtMultimedia import QMediaPlayer

from src.core.metadata import get_ffmpeg_path, get_media_creation_time_and_duration
from src.core.i18n import tr


def compute_active_regions_from_silence(duration_ms: int, silent_regions: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """전체 길이(duration_ms)에서 빈 구간(silent_regions)을 제외한 유음 구간(active_regions) 목록을 반환"""
    if duration_ms <= 0:
        return []
    if not silent_regions:
        return [(0, duration_ms)]
    sorted_sil = sorted((max(0, int(s)), min(duration_ms, int(e))) for s, e in silent_regions if e > s)
    active = []
    cursor = 0
    for s_start, s_end in sorted_sil:
        if s_start > cursor:
            active.append((cursor, s_start))
        cursor = max(cursor, s_end)
    if cursor < duration_ms:
        active.append((cursor, duration_ms))
    return active


def analyze_pcm_waveform_and_silence(
    pcm_bytes: bytes,
    sample_rate: int = 1000,
    bin_count: int = 240,
    chunk_ms: int = 50,
    silence_ratio: float = 0.05,
    min_silence_ms: int = 200,
) -> tuple[list[float], list[tuple[int, int]], list[tuple[int, int]]]:
    """
    16-bit signed mono PCM 바이트에서:
    1) 타임라인 렌더링용 정규화 음파 피크 리스트 (peaks: 0.0 ~ 1.0)
    2) 빈 구간(무음 구간) 리스트: silent_regions = [(start_ms, end_ms), ...]
    3) 빈 구간을 제외한 유음 구간 리스트: active_regions = [(start_ms, end_ms), ...]
    을 계산하여 반환합니다.
    """
    usable_len = (len(pcm_bytes) // 2) * 2
    if usable_len <= 0 or sample_rate <= 0:
        return [], [], []

    samples = array.array("h")
    samples.frombytes(pcm_bytes[:usable_len])
    total_samples = len(samples)
    if total_samples == 0:
        return [], [], []

    duration_ms = max(1, int(round(total_samples * 1000.0 / sample_rate)))

    # 1. 타임라인 파형 피크 계산 (bin_count 개수)
    actual_bins = max(16, min(bin_count, total_samples))
    peaks = []
    for i in range(actual_bins):
        i0 = int(i * total_samples / actual_bins)
        i1 = max(i0 + 1, int((i + 1) * total_samples / actual_bins))
        seg = samples[i0:i1]
        max_abs = max(abs(seg[0]), abs(min(seg)), abs(max(seg))) if seg else 0
        peaks.append(min(1.0, max_abs / 32768.0))

    max_peak = max(peaks) if peaks else 0.0
    if max_peak > 1e-4:
        peaks = [round(p / max_peak, 4) for p in peaks]
    else:
        peaks = [0.0 for _ in peaks]

    # 2. chunk_ms 단위 무음(빈 구간) 판정
    chunk_samples = max(1, int(round(sample_rate * (chunk_ms / 1000.0))))
    num_chunks = max(1, (total_samples + chunk_samples - 1) // chunk_samples)
    abs_thresh = max(160.0, (max_peak * 32768.0) * silence_ratio)

    silent_flags = []
    for c_idx in range(num_chunks):
        c0 = c_idx * chunk_samples
        c1 = min(total_samples, c0 + chunk_samples)
        seg = samples[c0:c1]
        c_max = max(abs(min(seg)), abs(max(seg))) if seg else 0
        silent_flags.append(c_max < abs_thresh)

    raw_silent = []
    in_sil = False
    sil_start_idx = 0
    for idx, is_sil in enumerate(silent_flags):
        if is_sil and not in_sil:
            in_sil = True
            sil_start_idx = idx
        elif not is_sil and in_sil:
            in_sil = False
            s_ms = int(round(sil_start_idx * chunk_ms))
            e_ms = min(duration_ms, int(round(idx * chunk_ms)))
            if (e_ms - s_ms) >= min_silence_ms:
                raw_silent.append((s_ms, e_ms))
    if in_sil:
        s_ms = int(round(sil_start_idx * chunk_ms))
        e_ms = duration_ms
        if (e_ms - s_ms) >= min_silence_ms:
            raw_silent.append((s_ms, e_ms))

    active_regions = compute_active_regions_from_silence(duration_ms, raw_silent)
    return peaks, raw_silent, active_regions


class AudioWaveformThread(QThread):
    """FFmpeg를 사용해 MP3/오디오 파일의 음파형(Waveform) 및 빈 구간(무음)/유음 구간을 고속 추출하는 스레드"""
    waveform_ready = pyqtSignal(list, list, list)  # peaks, silent_regions, active_regions
    _active_threads = set()

    def __init__(self, audio_path: str, bin_count: int = 240, parent=None):
        super().__init__(parent)
        self.audio_path = audio_path
        self.bin_count = bin_count
        self._proc = None
        AudioWaveformThread._active_threads.add(self)

    def _kill_proc(self):
        proc = self._proc
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=1.0)
            except Exception as e:
                logging.debug(f"[WaveformThread] Proc kill error: {e}")
            finally:
                self._proc = None

    def stop_and_kill(self):
        self.requestInterruption()
        self._kill_proc()
        if self.isRunning():
            self.wait(400)

    @classmethod
    def kill_all(cls, target_path: str = None) -> int:
        from src.core.lock_resolver import norm_path_key
        target_key = norm_path_key(target_path) if target_path else ""
        killed = 0
        for th in list(cls._active_threads):
            try:
                if not target_key or norm_path_key(th.audio_path) == target_key:
                    th.stop_and_kill()
                    killed += 1
            except Exception:
                pass
        return killed

    def run(self):
        try:
            if self.isInterruptionRequested():
                return
            ffmpeg_bin = get_ffmpeg_path()
            cmd = [
                ffmpeg_bin,
                "-v", "error",
                "-i", self.audio_path,
                "-vn",
                "-ac", "1",
                "-ar", "1000",
                "-f", "s16le",
                "-"
            ]
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            chunks = []
            while True:
                if self.isInterruptionRequested():
                    self._kill_proc()
                    return
                data = self._proc.stdout.read(32768) if self._proc and self._proc.stdout else b""
                if not data:
                    break
                chunks.append(data)
            if self._proc:
                self._proc.wait(timeout=1.0)
            if self.isInterruptionRequested():
                return
            pcm_bytes = b"".join(chunks)
            peaks, silent_regions, active_regions = analyze_pcm_waveform_and_silence(
                pcm_bytes, sample_rate=1000, bin_count=self.bin_count
            )
            if peaks and not self.isInterruptionRequested():
                self.waveform_ready.emit(peaks, silent_regions, active_regions)
        except Exception as e:
            logging.error(f"[WaveformThread] Exception: {e}", exc_info=True)
        finally:
            self._kill_proc()
            AudioWaveformThread._active_threads.discard(self)

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
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("timeline.loading_bar"))
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
        self.waveform_peaks = []
        self.silent_regions = []
        self.active_regions = []
        self.snap_tolerance_px = 12.0

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

    def set_waveform_data(self, peaks: list, silent_regions: list = None, active_regions: list = None):
        """오디오 음파형(peaks), 빈 구간(silent_regions), 유음 하이라이트 구간(active_regions)을 설정"""
        self.waveform_peaks = list(peaks) if peaks else []
        self.silent_regions = [(int(s), int(e)) for s, e in (silent_regions or []) if int(e) > int(s)]
        if active_regions is not None:
            self.active_regions = [(int(s), int(e)) for s, e in active_regions if int(e) > int(s)]
        else:
            self.active_regions = compute_active_regions_from_silence(self.duration_ms, self.silent_regions)
        self.update()

    def clear_waveform_data(self):
        self.waveform_peaks = []
        self.silent_regions = []
        self.active_regions = []
        self.update()

    def snap_marker_ms(self, marker: str, raw_ms: int, x_pos: float = None) -> int:
        """
        빈 구간(무음 구간) 자석 스냅:
        - 시작 막대('start')는 빈 구간의 시작지점(s_start)에 자석 스냅
        - 끝 막대('end')는 빈 구간의 끝지점(s_end)에 자석 스냅
        """
        if not self.silent_regions or self.duration_ms <= 0 or self.width() <= 0:
            return raw_ms
        if marker not in ("start", "end"):
            return raw_ms

        cur_x = float(x_pos) if x_pos is not None else self.ms_to_x(raw_ms)
        best_target_ms = None
        best_dist_px = self.snap_tolerance_px + 1.0

        for s_start, s_end in self.silent_regions:
            target_ms = s_start if marker == "start" else s_end
            target_x = self.ms_to_x(target_ms)
            dist_px = abs(cur_x - target_x)

            # 마우스가 스냅 반경(12px) 이내이거나, 화면상 좁은 빈 구간(24px 이하) 내부로 진입한 경우 즉시 스냅
            sx1 = self.ms_to_x(s_start)
            sx2 = self.ms_to_x(s_end)
            in_narrow_gap = (s_start <= raw_ms <= s_end) and ((sx2 - sx1) <= self.snap_tolerance_px * 2.0)

            if dist_px <= self.snap_tolerance_px or in_narrow_gap:
                if dist_px < best_dist_px:
                    best_dist_px = dist_px
                    best_target_ms = target_ms

        return best_target_ms if best_target_ms is not None else raw_ms

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

        # 0. 배경 썸네일 타일링 또는 오디오 음파형(Waveform) + 유음 구간 하이라이트 그리기
        if self.waveform_peaks:
            # 기본 배경 (빈 구간은 어두운 배경 유지)
            painter.fillRect(QRectF(0, 0, w, h), QColor(15, 18, 24))

            # 빈 구간을 제외한 유음 구간(active_regions) 배경 하이라이트 표시
            active_list = self.active_regions or compute_active_regions_from_silence(self.duration_ms, self.silent_regions)
            for a_start, a_end in active_list:
                ax1 = self.ms_to_x(a_start)
                ax2 = self.ms_to_x(a_end)
                aw = max(1.0, ax2 - ax1)
                painter.fillRect(QRectF(ax1, 0, aw, h), QColor(0, 180, 216, 58))
                painter.setPen(QPen(QColor(0, 229, 255, 130), 1))
                painter.drawLine(int(ax1), 0, int(ax2), 0)
                painter.drawLine(int(ax1), int(h - 1), int(ax2), int(h - 1))

            # 빈 구간(무음 구간) 경계 점선 가이드 표시
            for s_start, s_end in self.silent_regions:
                for bound_ms in (s_start, s_end):
                    if 0 < bound_ms < self.duration_ms:
                        bx = int(self.ms_to_x(bound_ms))
                        painter.setPen(QPen(QColor(255, 255, 255, 70), 1, Qt.PenStyle.DotLine))
                        painter.drawLine(bx, 0, bx, int(h))

            # 음파형(Waveform) 막대 렌더링
            n_bins = len(self.waveform_peaks)
            mid_y = h / 2.0
            max_half_h = (h * 0.42)
            bar_step = w / float(n_bins)
            bar_w = max(1.0, bar_step * 0.72)

            for i, pk in enumerate(self.waveform_peaks):
                bx = i * bar_step
                bin_ms = int(((i + 0.5) / float(n_bins)) * self.duration_ms)
                in_active = any(a_s <= bin_ms <= a_e for a_s, a_e in active_list) if active_list else (pk >= 0.05)
                if in_active:
                    half_bar = max(1.5, float(pk) * max_half_h)
                    painter.fillRect(
                        QRectF(bx, mid_y - half_bar, bar_w, half_bar * 2.0),
                        QColor(0, 230, 180, 225),
                    )
                else:
                    painter.fillRect(
                        QRectF(bx, mid_y - 0.8, bar_w, 1.6),
                        QColor(100, 110, 125, 90),
                    )
        elif self.pixmaps:
            n = len(self.pixmaps)
            tw = w / float(n)
            for i, pm in enumerate(self.pixmaps):
                rect = QRectF(i * tw, 0, tw, h)
                scaled = pm.scaled(int(tw), int(h), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                painter.drawPixmap(rect.toRect(), scaled)
        else:
            painter.fillRect(QRectF(0, 0, w, h), QColor(17, 17, 17))
            painter.setPen(QColor(128, 128, 128))
            painter.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, getattr(self, "placeholder_text", None) or tr("timeline.loading"))

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
            elif self.dragging_marker in ('start', 'end') and self.silent_regions:
                # 빈 구간(무음 구간) 자동 자석 스냅: 시작 막대는 빈 구간의 시작지점, 끝 막대는 빈 구간의 끝지점
                new_ms = self.snap_marker_ms(self.dragging_marker, new_ms, x_pos=x)

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
