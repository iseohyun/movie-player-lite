"""유튜브 URL 재생 지원 (yt-dlp 기반).

- 첫 재생: 영상(H.264)·음성 HLS 스트림을 하나로 묶은 재생목록을 로컬(127.0.0.1)에서 제공해 바로 스트리밍한다.
  (유튜브는 영상과 음성을 따로 제공하므로, 플레이어가 한 주소로 둘 다 받을 수 있게 묶어 준다.)
- 동시에 같은 영상을 캐시 폴더에 mp4로 내려받아 두고, 다음부터는 그 파일로 재생한다.
"""
import os
import re
import glob
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src.core.metadata import get_ffmpeg_path

CACHE_DIR_NAME = "youtube_cache"
USER_DATA_DIR_NAME = "MP4-Trim"
STREAM_MAX_HEIGHT = 1080
STREAM_VIDEO_CODEC_PREFIX = "avc1"   # Qt 플레이어와 무손실 컷팅(mp4) 모두에서 호환되는 H.264만 사용
DOWNLOAD_FORMAT = "bv*[vcodec^=avc1]+ba[acodec^=mp4a]/bv*+ba/b"
CACHE_FILE_TEMPLATE = "%(title).80B [%(id)s].%(ext)s"
VIDEO_ID_PATTERN = r"[A-Za-z0-9_-]{11}"
_URL_PATTERNS = (
    re.compile(r"(?:https?://)?(?:www\.|m\.|music\.)?youtube\.com/watch\?(?:.*&)?v=(" + VIDEO_ID_PATTERN + r")"),
    re.compile(r"(?:https?://)?(?:www\.|m\.)?youtube\.com/(?:shorts|embed|live)/(" + VIDEO_ID_PATTERN + r")"),
    re.compile(r"(?:https?://)?youtu\.be/(" + VIDEO_ID_PATTERN + r")"),
)


class DownloadCancelled(Exception):
    pass


def extract_video_id(text: str):
    """유튜브 주소에서 영상 ID(11자)를 뽑는다. 유튜브 주소가 아니면 None."""
    if not text:
        return None
    for pattern in _URL_PATTERNS:
        match = pattern.search(text.strip())
        if match:
            return match.group(1)
    return None


def canonical_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def get_cache_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, USER_DATA_DIR_NAME, CACHE_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def find_cached_file(video_id: str):
    """이미 내려받은 오프라인 파일 경로 (없으면 None)."""
    pattern = os.path.join(glob.escape(get_cache_dir()), f"*[[]{video_id}[]].mp4")
    matches = [p for p in glob.glob(pattern) if os.path.isfile(p)]
    return matches[0] if matches else None


# ---------------------------------------------------------------------------
# 로컬 재생목록 서버: 영상·음성 스트림을 묶은 HLS 마스터 재생목록을 플레이어에 제공
# ---------------------------------------------------------------------------
_playlists = {}
_server = None
_server_lock = threading.Lock()


class _PlaylistHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = _playlists.get(self.path.strip("/"))
        if body is None:
            self.send_error(404)
            return
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.apple.mpegurl")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    do_HEAD = do_GET

    def log_message(self, *args):
        pass


def _publish_playlist(video_id: str, text: str) -> str:
    global _server
    with _server_lock:
        if _server is None:
            _server = ThreadingHTTPServer(("127.0.0.1", 0), _PlaylistHandler)
            _server.daemon_threads = True
            threading.Thread(target=_server.serve_forever, daemon=True).start()
        name = f"{video_id}.m3u8"
        _playlists[name] = text
        return f"http://127.0.0.1:{_server.server_address[1]}/{name}"


def shutdown_playlist_server():
    global _server
    with _server_lock:
        if _server is not None:
            try:
                _server.shutdown()
                _server.server_close()
            except Exception as e:
                logging.debug(f"Playlist server shutdown error: {e}")
            _server = None
        _playlists.clear()


def _build_master_playlist(video_fmt: dict, audio_fmt: dict) -> str:
    bandwidth = int((video_fmt.get("tbr") or 2000) * 1000)
    width = video_fmt.get("width") or 1280
    height = video_fmt.get("height") or 720
    return (
        "#EXTM3U\n#EXT-X-VERSION:6\n#EXT-X-INDEPENDENT-SEGMENTS\n"
        f'#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud",NAME="audio",DEFAULT=YES,AUTOSELECT=YES,URI="{audio_fmt["url"]}"\n'
        f'#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},RESOLUTION={width}x{height},AUDIO="aud"\n'
        f'{video_fmt["url"]}\n'
    )


def _pick_audio(audio_formats: list) -> dict:
    """원본 언어(기본 트랙) 우선, 그중 가장 높은 음질."""
    def rank(fmt):
        return (fmt.get("language_preference") or 0, fmt.get("quality") or 0, fmt.get("tbr") or 0)
    return max(audio_formats, key=rank)


def resolve_stream(url: str) -> dict:
    """스트리밍 재생 정보 조회 (네트워크 사용, 수 초 소요 → 반드시 작업 스레드에서 호출).

    반환: {"id", "title", "duration_ms", "height", "stream_url"}
    """
    import yt_dlp

    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Not a YouTube video URL")
    options = {"quiet": True, "no_warnings": True, "noplaylist": True, "logger": _SilentLogger()}
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(canonical_url(video_id), download=False, process=False)

    hls_formats = [f for f in (info.get("formats") or []) if (f.get("protocol") or "").startswith("m3u8") and f.get("url")]
    video_formats = [
        f for f in hls_formats
        if (f.get("vcodec") or "none").startswith(STREAM_VIDEO_CODEC_PREFIX) and (f.get("height") or 0) <= STREAM_MAX_HEIGHT
    ]
    audio_formats = [f for f in hls_formats if (f.get("vcodec") or "none") == "none"]
    if not video_formats or not audio_formats:
        raise RuntimeError("No streamable video/audio format found")

    video_fmt = max(video_formats, key=lambda f: (f.get("height") or 0, f.get("tbr") or 0))
    audio_fmt = _pick_audio(audio_formats)
    stream_url = _publish_playlist(video_id, _build_master_playlist(video_fmt, audio_fmt))
    return {
        "id": video_id,
        "title": info.get("title") or video_id,
        "duration_ms": int((info.get("duration") or 0) * 1000),
        "height": video_fmt.get("height") or 0,
        "stream_url": stream_url,
    }


def download_to_cache(url: str, is_cancelled=None) -> str:
    """영상을 캐시 폴더에 mp4로 내려받고 파일 경로를 반환 (작업 스레드에서 호출).

    영상·음성을 합치는 데 ffmpeg가 필요하다. 취소되면 DownloadCancelled를 던지며,
    받다 만 조각(.part)은 남겨 두어 다음에 이어받는다.
    """
    import yt_dlp

    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Not a YouTube video URL")
    cached = find_cached_file(video_id)
    if cached:
        return cached

    def progress_hook(_status):
        if is_cancelled and is_cancelled():
            raise DownloadCancelled()

    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "logger": _SilentLogger(),
        "format": DOWNLOAD_FORMAT,
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(get_cache_dir(), CACHE_FILE_TEMPLATE),
        "windowsfilenames": True,
        "progress_hooks": [progress_hook],
    }
    ffmpeg_path = get_ffmpeg_path()
    if os.path.isfile(ffmpeg_path):
        options["ffmpeg_location"] = os.path.dirname(ffmpeg_path)
    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.extract_info(canonical_url(video_id), download=True)

    cached = find_cached_file(video_id)
    if not cached:
        raise RuntimeError("Download finished but the merged mp4 was not created (is ffmpeg available?)")
    return cached


class _SilentLogger:
    """yt-dlp 메시지를 콘솔 대신 debug.log로 보낸다 (--noconsole 빌드에는 콘솔이 없다)."""

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        logging.warning(f"yt-dlp: {msg}")

    def error(self, msg):
        logging.error(f"yt-dlp: {msg}")
