import os
import sys
import gc
import time
import ctypes
import logging
from ctypes import wintypes
from PyQt6.QtWidgets import QApplication


def norm_path_key(path: str) -> str:
    """경로 비교용 정규화 문자열 반환 (슬래시 통일 + 소문자 변환)"""
    if not path or not isinstance(path, str):
        return ""
    try:
        return os.path.abspath(os.path.normpath(path.strip())).replace("\\", "/").lower()
    except Exception:
        return path.strip().replace("\\", "/").lower()


# ---------------------------------------------------------------------------
# Windows Restart Manager API (rstrtmgr.dll) 구조체 및 함수 정의
# ---------------------------------------------------------------------------
CCH_RM_SESSION_KEY = 32
CCH_RM_MAX_APP_NAME = 255
CCH_RM_MAX_SVC_NAME = 63
ERROR_MORE_DATA = 234


class RM_UNIQUE_PROCESS(ctypes.Structure):
    _fields_ = [
        ("dwProcessId", wintypes.DWORD),
        ("ProcessStartTime", wintypes.FILETIME),
    ]


class RM_PROCESS_INFO(ctypes.Structure):
    _fields_ = [
        ("Process", RM_UNIQUE_PROCESS),
        ("strAppName", wintypes.WCHAR * (CCH_RM_MAX_APP_NAME + 1)),
        ("strServiceShortName", wintypes.WCHAR * (CCH_RM_MAX_SVC_NAME + 1)),
        ("ApplicationType", wintypes.DWORD),
        ("AppStatus", wintypes.ULONG),
        ("TSSessionId", wintypes.DWORD),
        ("bRestartable", wintypes.BOOL),
    ]


def get_locking_processes(file_path: str) -> list[dict]:
    """
    Windows Restart Manager API를 사용하여 특정 파일을 점유 중인 프로세스 목록을 조회한다.
    반환 형태: [{"pid": int, "name": str, "exe_path": str}, ...]
    """
    if os.name != "nt" or not file_path:
        return []

    abs_path = os.path.abspath(os.path.normpath(file_path))
    if not os.path.exists(abs_path):
        return []

    results = []
    rstrtmgr = ctypes.windll.rstrtmgr
    session_handle = wintypes.DWORD(0)
    session_key = (wintypes.WCHAR * (CCH_RM_SESSION_KEY + 1))()

    res = rstrtmgr.RmStartSession(ctypes.byref(session_handle), 0, session_key)
    if res != 0:
        return []

    try:
        resources = (wintypes.LPCWSTR * 1)(abs_path)
        res = rstrtmgr.RmRegisterResources(
            session_handle, 1, resources, 0, None, 0, None
        )
        if res != 0:
            return []

        proc_info_needed = wintypes.UINT(0)
        proc_info_count = wintypes.UINT(0)
        reboot_reasons = wintypes.DWORD(0)

        res = rstrtmgr.RmGetList(
            session_handle,
            ctypes.byref(proc_info_needed),
            ctypes.byref(proc_info_count),
            None,
            ctypes.byref(reboot_reasons),
        )
        if res == ERROR_MORE_DATA and proc_info_needed.value > 0:
            count = proc_info_needed.value
            proc_info_Count_buf = wintypes.UINT(count)
            rg_affected = (RM_PROCESS_INFO * count)()
            res = rstrtmgr.RmGetList(
                session_handle,
                ctypes.byref(proc_info_needed),
                ctypes.byref(proc_info_Count_buf),
                rg_affected,
                ctypes.byref(reboot_reasons),
            )
            if res == 0:
                for i in range(proc_info_Count_buf.value):
                    info = rg_affected[i]
                    pid = int(info.Process.dwProcessId)
                    app_name = str(info.strAppName or "")
                    exe_path = _get_process_image_path(pid)
                    exe_name = os.path.basename(exe_path) if exe_path else app_name
                    results.append({
                        "pid": pid,
                        "name": exe_name or app_name or f"PID-{pid}",
                        "app_name": app_name,
                        "exe_path": exe_path,
                    })
    except Exception as e:
        logging.debug(f"[LockResolver] RmGetList error: {e}")
    finally:
        try:
            rstrtmgr.RmEndSession(session_handle)
        except Exception:
            pass

    return results


def _get_process_image_path(pid: int) -> str:
    """PID로부터 실행 파일 전체 경로를 조회한다."""
    if os.name != "nt" or pid <= 0:
        return ""
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = ctypes.c_void_p
    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_proc:
        return ""
    try:
        buf_len = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(1024)
        if kernel32.QueryFullProcessImageNameW(ctypes.c_void_p(h_proc), 0, buf, ctypes.byref(buf_len)):
            return buf.value
    except Exception:
        pass
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(h_proc))
    return ""


def _terminate_pid(pid: int, wait_ms: int = 1000) -> bool:
    """지정한 PID 프로세스를 강제 종료하고 핸들 해제까지 대기한다."""
    if os.name != "nt" or pid <= 0 or pid == os.getpid():
        return False
    PROCESS_TERMINATE = 0x0001
    SYNCHRONIZE = 0x00100000
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = ctypes.c_void_p
    h_proc = kernel32.OpenProcess(PROCESS_TERMINATE | SYNCHRONIZE, False, pid)
    if not h_proc:
        return False
    try:
        ok = bool(kernel32.TerminateProcess(ctypes.c_void_p(h_proc), 1))
        if ok and wait_ms > 0:
            kernel32.WaitForSingleObject(ctypes.c_void_p(h_proc), wait_ms)
        return ok
    except Exception as e:
        logging.debug(f"[LockResolver] Failed to terminate PID {pid}: {e}")
        return False
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(h_proc))


def _is_self_or_same_app_process(proc_info: dict) -> bool:
    """
    점유 프로세스가 현재 앱의 이전 버전/중복 인스턴스(movie-player-lite, mp4-trim)이거나
    하위 ffmpeg/ffprobe 프로세스인지 판별한다.
    """
    name_low = (proc_info.get("name") or "").lower()
    app_low = (proc_info.get("app_name") or "").lower()
    exe_low = os.path.basename(proc_info.get("exe_path") or "").lower()

    target_keywords = (
        "movie-player-lite",
        "mp4-trim",
        "ffmpeg",
        "ffprobe",
    )
    for kw in target_keywords:
        if kw in name_low or kw in app_low or kw in exe_low:
            return True

    # 패키징된 실행 파일과 동일한 실행 파일명인 경우
    if getattr(sys, "frozen", False):
        my_exe = os.path.basename(sys.executable).lower()
        if my_exe and (name_low == my_exe or exe_low == my_exe):
            return True

    return False


def terminate_zombie_same_name_processes() -> list[int]:
    """
    앱 시작 시 IPC 서버가 응답하지 않는 상태인데 동일 이름(movie-player-lite.exe, mp4-trim.exe)의
    이전 버전 유령 프로세스가 백그라운드에 남아있다면 자동으로 정리한다.
    """
    if os.name != "nt":
        return []

    TH32CS_SNAPPROCESS = 0x00000002

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    h_snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if h_snap in (None, -1, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF):
        return []

    my_pid = os.getpid()
    target_exe_names = {"movie-player-lite.exe", "mp4-trim.exe"}
    if getattr(sys, "frozen", False):
        target_exe_names.add(os.path.basename(sys.executable).lower())

    terminated_pids = []
    try:
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        has_proc = kernel32.Process32FirstW(ctypes.c_void_p(h_snap), ctypes.byref(pe))
        while has_proc:
            pid = int(pe.th32ProcessID)
            exe_name = str(pe.szExeFile or "").lower()
            if pid != my_pid and exe_name in target_exe_names:
                if _terminate_pid(pid, wait_ms=800):
                    logging.info(f"[LockResolver] Terminated zombie process {exe_name} (PID={pid})")
                    terminated_pids.append(pid)
            has_proc = kernel32.Process32NextW(ctypes.c_void_p(h_snap), ctypes.byref(pe))
    except Exception as e:
        logging.debug(f"[LockResolver] Snapshot enumeration error: {e}")
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(h_snap))

    return terminated_pids


def release_file_locks(file_path: str, player_widget=None) -> list[str]:
    """
    지정한 파일에 걸린 점유(Lock)를 해제한다:
    1) 자기 자신(player_widget 및 백그라운드 ThumbnailGeneratorThread의 ffmpeg.exe)의 점유 즉시 해제
    2) Windows Restart Manager로 조회하여 자기 자신(PID 일치) 또는 동일 이름 프로세스
       (movie-player-lite.exe, mp4-trim.exe, ffmpeg.exe)가 점유 중이면 자동 해제/종료
    반환값: 해제 조치 로그 목록
    """
    actions_taken = []
    if not file_path:
        return actions_taken

    target_key = norm_path_key(file_path)

    # 1. 현재 프로세스의 썸네일 추출 스레드(ffmpeg.exe) 즉시 강제 종료
    try:
        from src.ui.widgets.timeline import ThumbnailGeneratorThread
        killed_count = ThumbnailGeneratorThread.kill_all(file_path)
        if killed_count > 0:
            actions_taken.append(f"stopped {killed_count} thumbnail ffmpeg process(es)")
    except Exception as e:
        logging.debug(f"[LockResolver] ThumbnailGeneratorThread.kill_all error: {e}")

    # 2. player_widget이 해당 파일을 로드 중이면 즉시 언로드하여 파일 핸들 반납
    if player_widget is not None:
        try:
            if hasattr(player_widget, "stop_thumbnail_thread"):
                player_widget.stop_thumbnail_thread()
            cached_key = norm_path_key(getattr(player_widget, "video_path_cached", "") or "")
            handle_key = norm_path_key(player_widget.get_current_handle_path() or "")
            if target_key in (cached_key, handle_key) or getattr(player_widget, "_source_win32_handle", None):
                player_widget.unload_video()
                actions_taken.append("unloaded active video from player_widget")
        except Exception as e:
            logging.debug(f"[LockResolver] player_widget unload error: {e}")

    app = QApplication.instance()
    if app:
        app.processEvents()
    gc.collect()

    # 3. Windows Restart Manager로 점유 프로세스 확인 및 동일 이름/자기 자신 해제
    locking_procs = get_locking_processes(file_path)
    my_pid = os.getpid()

    for pinfo in locking_procs:
        pid = pinfo["pid"]
        pname = pinfo["name"]
        if pid == my_pid:
            # 자기 자신이 아직 핸들을 쥐고 있는 경우 강제 언로드 및 가비지 컬렉션 수행
            if player_widget is not None:
                try:
                    player_widget.unload_video()
                except Exception:
                    pass
            if app:
                app.processEvents()
            gc.collect()
            time.sleep(0.05)
            actions_taken.append(f"released self handle (PID={my_pid})")
        elif _is_self_or_same_app_process(pinfo):
            if _terminate_pid(pid, wait_ms=1000):
                logging.info(f"[LockResolver] Terminated locking same-app/child process: {pname} (PID={pid})")
                actions_taken.append(f"terminated {pname} (PID={pid})")

    return actions_taken


def format_locking_processes_info(file_path: str) -> str:
    """외부 프로세스가 여전히 점유 중일 때 사용자에게 보여줄 안내 문자열 생성"""
    procs = get_locking_processes(file_path)
    if not procs:
        return ""
    desc = ", ".join(f"{p['name']} (PID: {p['pid']})" for p in procs)
    return f"\n\n[현재 파일 점유 프로세스]: {desc}"


def safe_rename_with_unlock(src: str, dst: str, player_widget=None):
    """
    파일 이름 변경(os.rename)을 수행하며, 점유 오류 발생 시 자기 자신 및 동일 이름 프로세스의
    점유를 자동 해제하면서 최대 4회 재시도한다.
    """
    try:
        from src.ui.widgets.timeline import ThumbnailGeneratorThread
        ThumbnailGeneratorThread.kill_all(src)
    except Exception:
        pass

    last_err = None
    for attempt in range(4):
        try:
            os.rename(src, dst)
            return
        except OSError as e:
            last_err = e
            logging.warning(f"[LockResolver] os.rename attempt {attempt + 1} failed for {src}: {e}")
            release_file_locks(src, player_widget=player_widget)
            time.sleep(0.08 * (attempt + 1))

    extra_info = format_locking_processes_info(src)
    raise OSError(f"{last_err}{extra_info}") from last_err


def safe_remove_with_unlock(target: str, player_widget=None):
    """
    파일 삭제(os.remove)를 수행하며, 점유 오류 발생 시 자기 자신 및 동일 이름 프로세스의
    점유를 자동 해제하면서 최대 4회 재시도한다.
    """
    if not os.path.exists(target):
        return

    try:
        from src.ui.widgets.timeline import ThumbnailGeneratorThread
        ThumbnailGeneratorThread.kill_all(target)
    except Exception:
        pass

    last_err = None
    for attempt in range(4):
        try:
            if not os.path.exists(target):
                return
            os.remove(target)
            return
        except OSError as e:
            last_err = e
            logging.warning(f"[LockResolver] os.remove attempt {attempt + 1} failed for {target}: {e}")
            release_file_locks(target, player_widget=player_widget)
            time.sleep(0.08 * (attempt + 1))

    extra_info = format_locking_processes_info(target)
    raise OSError(f"{last_err}{extra_info}") from last_err
