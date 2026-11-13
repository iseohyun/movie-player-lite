import logging

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from src.core import youtube

THREAD_STOP_WAIT_MS = 3000


class _ResolveThread(QThread):
    done = pyqtSignal(int, dict)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, url: str, parent=None):
        super().__init__(parent)
        self.request_id = request_id
        self.url = url

    def run(self):
        try:
            self.done.emit(self.request_id, youtube.resolve_stream(self.url))
        except Exception as e:
            logging.error(f"YouTube resolve failed: {e}")
            self.failed.emit(self.request_id, str(e))


class _DownloadThread(QThread):
    done = pyqtSignal(str, str)
    failed = pyqtSignal(str, str)

    def __init__(self, video_id: str, url: str, parent=None):
        super().__init__(parent)
        self.video_id = video_id
        self.url = url
        self.cancelled = False

    def run(self):
        try:
            self.done.emit(self.video_id, youtube.download_to_cache(self.url, lambda: self.cancelled))
        except youtube.DownloadCancelled:
            logging.info(f"YouTube download cancelled: {self.video_id}")
        except Exception as e:
            logging.error(f"YouTube download failed: {e}")
            if not self.cancelled:
                self.failed.emit(self.video_id, str(e))


class YouTubeController(QObject):
    """유튜브 주소 해석과 오프라인 저장을 UI 스레드 밖에서 수행하고 결과를 시그널로 알린다."""

    stream_ready = pyqtSignal(dict)          # {"id", "title", "duration_ms", "height", "stream_url", "url"}
    stream_failed = pyqtSignal(str)          # 오류 메시지
    download_finished = pyqtSignal(str, str)  # 영상 ID, 저장된 파일 경로
    download_failed = pyqtSignal(str, str)    # 영상 ID, 오류 메시지

    def __init__(self, parent=None):
        super().__init__(parent)
        self._request_id = 0
        self._resolve_threads = []
        self._download_threads = {}

    def resolve(self, url: str):
        """가장 최근 요청의 결과만 전달한다 (연달아 여러 주소를 열면 앞선 요청은 버린다)."""
        self._request_id += 1
        thread = _ResolveThread(self._request_id, url, self)
        thread.done.connect(lambda rid, info, u=url: self._on_resolved(rid, info, u))
        thread.failed.connect(self._on_resolve_failed)
        thread.finished.connect(lambda t=thread: self._resolve_threads.remove(t) if t in self._resolve_threads else None)
        self._resolve_threads.append(thread)
        thread.start()

    def _on_resolved(self, request_id: int, info: dict, url: str):
        if request_id == self._request_id:
            info["url"] = url
            self.stream_ready.emit(info)

    def _on_resolve_failed(self, request_id: int, message: str):
        if request_id == self._request_id:
            self.stream_failed.emit(message)

    def download(self, video_id: str, url: str):
        """같은 영상은 한 번에 하나만 내려받는다."""
        if video_id in self._download_threads:
            return
        thread = _DownloadThread(video_id, url, self)
        thread.done.connect(self.download_finished)
        thread.failed.connect(self.download_failed)
        thread.finished.connect(lambda vid=video_id: self._download_threads.pop(vid, None))
        self._download_threads[video_id] = thread
        thread.start()

    def shutdown(self):
        """프로그램 종료 시: 내려받기를 취소하고 스레드와 로컬 재생목록 서버를 정리한다."""
        self._request_id += 1
        threads = list(self._download_threads.values()) + list(self._resolve_threads)
        for thread in threads:
            if isinstance(thread, _DownloadThread):
                thread.cancelled = True
        for thread in threads:
            if thread.isRunning() and not thread.wait(THREAD_STOP_WAIT_MS):
                thread.terminate()
                thread.wait(500)
        youtube.shutdown_playlist_server()
