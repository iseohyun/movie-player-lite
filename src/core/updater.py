import os
import re
import sys
import json
import time
import shutil
import tempfile
import subprocess
import urllib.request
import urllib.error
from PyQt6.QtCore import QThread, pyqtSignal

CURRENT_VERSION = "1.7.1"
GITHUB_REPO = "iseohyun/movie-player-lite"
GITHUB_LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases"


def parse_version(ver_str: str) -> tuple:
    """Parse a version string like 'v1.7.1' or '1.7.1' into a comparable integer tuple."""
    if not ver_str:
        return (0, 0, 0)
    cleaned = str(ver_str).strip().lstrip("vV")
    nums = [int(p) for p in re.findall(r"\d+", cleaned)]
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:4])


def read_version_from_md(md_path: str) -> str | None:
    """Extract the newest '## [vX.Y.Z]' version string from VERSION.md."""
    if not md_path or not os.path.isfile(md_path):
        return None
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^##\s+\[v?(\d+\.\d+(?:\.\d+)?)\]", line.strip(), re.IGNORECASE)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return None


def get_app_version() -> str:
    """Return the running app's semantic version string (e.g. '1.7.1')."""
    candidates = []
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            candidates.append(os.path.join(sys._MEIPASS, "VERSION.md"))
        candidates.append(os.path.join(os.path.dirname(sys.executable), "VERSION.md"))
    else:
        src_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        candidates.append(os.path.join(src_root, "VERSION.md"))

    for path in candidates:
        ver = read_version_from_md(path)
        if ver:
            return ver
    return CURRENT_VERSION


def is_portable_onefile_exe(exe_path: str = None) -> bool:
    """
    Return True if the target executable is a standalone PyInstaller --onefile binary
    (e.g. dist/movie-player-lite.exe) rather than an Inno Setup installed folder build.
    """
    target = exe_path or (sys.executable if getattr(sys, "frozen", False) else "")
    if not target or not os.path.isfile(target):
        return False
    exe_dir = os.path.dirname(os.path.abspath(target))
    if os.path.isdir(os.path.join(exe_dir, "_internal")):
        return False
    if os.path.isfile(os.path.join(exe_dir, "unins000.exe")):
        return False
    return True


def find_local_repo_dir(custom_dir: str = None) -> str | None:
    """Locate the local git/source repository directory if present on this machine."""
    candidates = []
    if custom_dir:
        candidates.append(custom_dir)
    env_repo = os.environ.get("MOVIE_PLAYER_LITE_REPO")
    if env_repo:
        candidates.append(env_repo)
    if not getattr(sys, "frozen", False):
        src_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        candidates.append(src_root)
    candidates.append(r"C:\git\movie-player-lite")

    for path in candidates:
        if not path:
            continue
        norm = os.path.abspath(path)
        if os.path.isfile(os.path.join(norm, "movie-player-lite.py")) and os.path.isdir(os.path.join(norm, "src")):
            return norm
    return None


def get_latest_source_mtime(repo_dir: str) -> tuple[float, str]:
    """Return (latest_mtime, relative_path) across source and locale files in repo_dir."""
    if not repo_dir or not os.path.isdir(repo_dir):
        return 0.0, ""

    latest_mtime = 0.0
    latest_rel = ""

    top_files = ["movie-player-lite.py", "VERSION.md", "installer.iss"]
    for fname in top_files:
        fpath = os.path.join(repo_dir, fname)
        if os.path.isfile(fpath):
            try:
                mt = os.path.getmtime(fpath)
                if mt > latest_mtime:
                    latest_mtime = mt
                    latest_rel = fname
            except OSError:
                pass

    for sub in ("src", "locales"):
        subdir = os.path.join(repo_dir, sub)
        if not os.path.isdir(subdir):
            continue
        for root, dirs, files in os.walk(subdir):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                if not f.endswith((".py", ".json")):
                    continue
                fpath = os.path.join(root, f)
                try:
                    mt = os.path.getmtime(fpath)
                    if mt > latest_mtime:
                        latest_mtime = mt
                        latest_rel = os.path.relpath(fpath, repo_dir)
                except OSError:
                    pass

    return latest_mtime, latest_rel


def get_installed_target_mtime(repo_dir: str = None) -> tuple[float, str]:
    """Return (mtime, path) of the currently running executable or installed build."""
    if getattr(sys, "frozen", False) and os.path.isfile(sys.executable):
        try:
            return os.path.getmtime(sys.executable), sys.executable
        except OSError:
            pass

    candidates = []
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        candidates.append(os.path.join(local_app_data, "Programs", "Movie Player Lite", "movie-player-lite.exe"))
    if repo_dir:
        candidates.append(os.path.join(repo_dir, "dist", "movie-player-lite.exe"))
        candidates.append(os.path.join(repo_dir, "installer_output", "MoviePlayerLite-Setup.exe"))

    best_mtime = 0.0
    best_path = ""
    for path in candidates:
        if os.path.isfile(path):
            try:
                mt = os.path.getmtime(path)
                if mt > best_mtime:
                    best_mtime = mt
                    best_path = path
            except OSError:
                pass
    return best_mtime, best_path


def check_git_remote_update(repo_dir: str, fetch: bool = True, timeout: float = 4.0) -> dict:
    """Check if origin/main has newer commits than local HEAD."""
    result = {"behind_count": 0, "latest_commit_msg": "", "remote_branch": "origin/main"}
    if not repo_dir or not os.path.isdir(os.path.join(repo_dir, ".git")):
        return result

    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        if fetch:
            subprocess.run(
                ["git", "fetch", "origin", "--quiet"],
                cwd=repo_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
                creationflags=creationflags,
            )
        proc = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..origin/main"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=creationflags,
        )
        if proc.returncode == 0 and proc.stdout.strip().isdigit():
            behind = int(proc.stdout.strip())
            result["behind_count"] = behind
            if behind > 0:
                msg_proc = subprocess.run(
                    ["git", "log", "-1", "--format=%s", "origin/main"],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    creationflags=creationflags,
                )
                if msg_proc.returncode == 0:
                    result["latest_commit_msg"] = msg_proc.stdout.strip()
    except Exception:
        pass
    return result


def check_github_release(current_version: str = None, timeout: float = 5.0, api_url: str = None) -> dict:
    """Query GitHub Releases API for the latest release."""
    cur_ver = current_version or get_app_version()
    target_url = api_url or GITHUB_LATEST_RELEASE_API
    info = {
        "available": False,
        "latest_version": cur_ver,
        "download_url": "",
        "html_url": GITHUB_RELEASES_PAGE,
        "release_notes": "",
    }
    try:
        req = urllib.request.Request(
            target_url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"MoviePlayerLite/{cur_ver}",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tag_name = str(data.get("tag_name", "")).strip()
        if not tag_name:
            return info
        latest_clean = tag_name.lstrip("vV")
        info["latest_version"] = latest_clean
        info["html_url"] = data.get("html_url") or GITHUB_RELEASES_PAGE
        info["release_notes"] = str(data.get("body") or "").strip()

        for asset in data.get("assets", []) or []:
            name = str(asset.get("name", ""))
            dl_url = str(asset.get("browser_download_url", ""))
            if name.lower().endswith(".exe") and dl_url:
                info["download_url"] = dl_url
                if "setup" in name.lower():
                    break

        if parse_version(latest_clean) > parse_version(cur_ver):
            info["available"] = True
    except Exception:
        pass
    return info


def check_for_updates(
    repo_dir: str = None,
    check_github: bool = True,
    fetch_git: bool = True,
    current_version: str = None,
    installed_mtime_override: float = None,
    github_api_url: str = None,
) -> dict:
    """
    Check both local repository/builds and GitHub Releases for available updates.
    Returns a standardized dictionary describing the update state.
    """
    cur_ver = current_version or get_app_version()
    resolved_repo = find_local_repo_dir(repo_dir)

    result = {
        "available": False,
        "source": "none",
        "current_version": cur_ver,
        "latest_version": cur_ver,
        "summary": "",
        "repo_dir": resolved_repo,
        "installer_path": None,
        "dist_path": None,
        "download_url": None,
        "html_url": GITHUB_RELEASES_PAGE,
        "changed_file": "",
        "behind_count": 0,
    }

    if resolved_repo:
        repo_ver = read_version_from_md(os.path.join(resolved_repo, "VERSION.md")) or cur_ver
        installer_candidate = os.path.join(resolved_repo, "installer_output", "MoviePlayerLite-Setup.exe")
        has_installer = os.path.isfile(installer_candidate)
        installer_mtime = os.path.getmtime(installer_candidate) if has_installer else 0.0

        dist_candidate = os.path.join(resolved_repo, "dist", "movie-player-lite.exe")
        has_dist = os.path.isfile(dist_candidate)
        dist_mtime = os.path.getmtime(dist_candidate) if has_dist else 0.0

        if installed_mtime_override is not None:
            installed_mtime = installed_mtime_override
            running_path = ""
        else:
            installed_mtime, running_path = get_installed_target_mtime(resolved_repo)

        is_portable = is_portable_onefile_exe(running_path) if running_path else False
        src_mtime, latest_rel = get_latest_source_mtime(resolved_repo)
        git_info = check_git_remote_update(resolved_repo, fetch=fetch_git)

        # 1) Remote origin/main has newer commits than local HEAD
        if git_info["behind_count"] > 0:
            result.update({
                "available": True,
                "source": "git_remote",
                "latest_version": repo_ver,
                "behind_count": git_info["behind_count"],
                "summary": git_info["latest_commit_msg"] or f"origin/main (+{git_info['behind_count']} commits)",
                "installer_path": installer_candidate if has_installer else None,
            })
            return result

        # 2) Local source files or VERSION.md are newer than the currently running binary.
        #    Note: We intentionally do NOT trigger an update merely because MoviePlayerLite-Setup.exe
        #    finished compressing a few seconds after movie-player-lite.exe was compiled from the exact same sources.
        version_bumped = parse_version(repo_ver) > parse_version(cur_ver)
        source_modified_since_build = (installed_mtime > 0) and (src_mtime > installed_mtime + 2.0)

        if version_bumped or source_modified_since_build:
            chosen_source = "local_source"
            if is_portable:
                # If running a portable copy from another path and repo dist/ is already built from latest sources
                same_as_dist = (
                    has_dist
                    and running_path
                    and os.path.normcase(os.path.abspath(running_path)) == os.path.normcase(os.path.abspath(dist_candidate))
                )
                if has_dist and not same_as_dist and dist_mtime >= src_mtime - 2.0 and dist_mtime > installed_mtime + 2.0:
                    chosen_source = "local_dist"
            else:
                if has_installer and installer_mtime >= src_mtime - 2.0 and installer_mtime > installed_mtime + 2.0:
                    chosen_source = "local_build"

            summary_str = f"v{repo_ver} ({latest_rel or 'VERSION.md'})" if version_bumped else (latest_rel or "Local repository")
            result.update({
                "available": True,
                "source": chosen_source,
                "latest_version": repo_ver,
                "changed_file": latest_rel or "VERSION.md",
                "summary": summary_str,
                "installer_path": installer_candidate if has_installer else None,
                "dist_path": dist_candidate if has_dist else None,
            })
            return result

    if check_github:
        gh = check_github_release(current_version=cur_ver, api_url=github_api_url)
        if gh["available"]:
            result.update({
                "available": True,
                "source": "github_release",
                "latest_version": gh["latest_version"],
                "download_url": gh["download_url"],
                "html_url": gh["html_url"],
                "summary": gh["release_notes"][:200] if gh["release_notes"] else f"GitHub Release v{gh['latest_version']}",
            })
            return result

    return result


class UpdateCheckThread(QThread):
    check_finished = pyqtSignal(dict)

    def __init__(self, repo_dir: str = None, check_github: bool = True, fetch_git: bool = True, parent=None):
        super().__init__(parent)
        self.repo_dir = repo_dir
        self.check_github = check_github
        self.fetch_git = fetch_git

    def run(self):
        info = check_for_updates(
            repo_dir=self.repo_dir,
            check_github=self.check_github,
            fetch_git=self.fetch_git,
        )
        self.check_finished.emit(info)


class UpdateInstallThread(QThread):
    progress_text = pyqtSignal(str)
    install_finished = pyqtSignal(dict)

    def __init__(self, update_info: dict, parent=None):
        super().__init__(parent)
        self.update_info = dict(update_info or {})

    def _build_portable_onefile_to_temp(self, repo_dir: str, creationflags: int) -> tuple[bool, str]:
        """Build a standalone --onefile exe into a temp directory so it never locks a running dist/ exe."""
        temp_root = os.path.join(tempfile.gettempdir(), f"mpl_onefile_build_{os.getpid()}")
        dist_dir = os.path.join(temp_root, "dist")
        work_dir = os.path.join(temp_root, "build")
        os.makedirs(dist_dir, exist_ok=True)
        os.makedirs(work_dir, exist_ok=True)

        proc = subprocess.run(
            [
                "python", "-m", "PyInstaller", "--noconfirm",
                "--name", "movie-player-lite", "--noupx", "--onefile", "--noconsole",
                "--distpath", dist_dir,
                "--workpath", work_dir,
                "--specpath", work_dir,
                "--hidden-import", "PyQt6.QtCore",
                "--hidden-import", "PyQt6.QtGui",
                "--hidden-import", "PyQt6.QtWidgets",
                "--hidden-import", "PyQt6.QtMultimedia",
                "--hidden-import", "PyQt6.QtMultimediaWidgets",
                "--hidden-import", "PyQt6.QtNetwork",
                "--add-data", f"{os.path.join(repo_dir, 'icon.ico')};.",
                "--add-data", f"{os.path.join(repo_dir, 'VERSION.md')};.",
                "--add-data", f"{os.path.join(repo_dir, 'locales')};locales",
                "--copy-metadata", "pyinstaller",
                "--copy-metadata", "PyQt6-sip",
                f"--icon={os.path.join(repo_dir, 'icon.ico')}",
                os.path.join(repo_dir, "movie-player-lite.py"),
            ],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=600,
            creationflags=creationflags,
        )
        built_exe = os.path.join(dist_dir, "movie-player-lite.exe")
        if proc.returncode == 0 and os.path.isfile(built_exe):
            return True, built_exe
        err_detail = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        return False, err_detail[-500:] or "Portable onefile build failed"

    def run(self):
        source = self.update_info.get("source", "none")
        repo_dir = self.update_info.get("repo_dir")
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        running_portable = is_portable_onefile_exe()

        try:
            if source == "git_remote" and repo_dir:
                self.progress_text.emit("git pull origin main...")
                pull_proc = subprocess.run(
                    ["git", "pull", "--ff-only", "origin", "main"],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    creationflags=creationflags,
                )
                if pull_proc.returncode != 0:
                    self.install_finished.emit({
                        "success": False,
                        "error": pull_proc.stderr.strip() or "git pull failed",
                    })
                    return
                source = "local_source"

            if source == "local_dist":
                dist_path = self.update_info.get("dist_path")
                if dist_path and os.path.isfile(dist_path) and getattr(sys, "frozen", False):
                    staged_exe = os.path.join(tempfile.gettempdir(), f"mpl_portable_staged_{os.getpid()}.exe")
                    shutil.copy2(dist_path, staged_exe)
                    self.install_finished.emit({
                        "success": True,
                        "mode": "portable_replace",
                        "new_exe_path": staged_exe,
                        "target_exe_path": sys.executable,
                    })
                    return

            if source == "local_source" and repo_dir:
                if running_portable:
                    # Running dist/movie-player-lite.exe directly: build a fresh onefile into %TEMP%
                    # and replace sys.executable after this process exits!
                    self.progress_text.emit("Building standalone executable...")
                    ok, built_or_err = self._build_portable_onefile_to_temp(repo_dir, creationflags)
                    if not ok:
                        self.install_finished.emit({
                            "success": False,
                            "error": built_or_err,
                        })
                        return

                    # Also refresh installer_output if Inno Setup exists so installed copy stays in sync
                    build_installer_bat = os.path.join(repo_dir, "build-installer.bat")
                    setup_exe = os.path.join(repo_dir, "installer_output", "MoviePlayerLite-Setup.exe")
                    if os.path.isfile(build_installer_bat):
                        self.progress_text.emit("Updating installer package...")
                        subprocess.run(
                            ["cmd.exe", "/c", build_installer_bat],
                            cwd=repo_dir,
                            capture_output=True,
                            text=True,
                            timeout=600,
                            creationflags=creationflags,
                        )
                    self.install_finished.emit({
                        "success": True,
                        "mode": "portable_replace",
                        "new_exe_path": built_or_err,
                        "target_exe_path": sys.executable,
                        "installer_path": setup_exe if os.path.isfile(setup_exe) else None,
                    })
                    return

                build_installer_bat = os.path.join(repo_dir, "build-installer.bat")
                if os.path.isfile(build_installer_bat):
                    self.progress_text.emit("Building installer (build-installer.bat)...")
                    proc = subprocess.run(
                        ["cmd.exe", "/c", build_installer_bat],
                        cwd=repo_dir,
                        capture_output=True,
                        text=True,
                        timeout=600,
                        creationflags=creationflags,
                    )
                    setup_exe = os.path.join(repo_dir, "installer_output", "MoviePlayerLite-Setup.exe")
                    if proc.returncode == 0 and os.path.isfile(setup_exe):
                        dist_exe = os.path.join(repo_dir, "dist", "movie-player-lite.exe")
                        if os.path.isdir(os.path.join(repo_dir, "dist")):
                            ok, temp_exe = self._build_portable_onefile_to_temp(repo_dir, creationflags)
                            if ok:
                                try:
                                    shutil.copy2(temp_exe, dist_exe)
                                except OSError:
                                    pass
                        self.install_finished.emit({
                            "success": True,
                            "mode": "installer",
                            "installer_path": setup_exe,
                            "dist_exe": dist_exe if os.path.isfile(dist_exe) else None,
                        })
                        return
                    else:
                        err_detail = (proc.stdout or "") + "\n" + (proc.stderr or "")
                        self.install_finished.emit({
                            "success": False,
                            "error": err_detail.strip()[-500:] or "Installer build failed",
                        })
                        return

            if source == "local_build":
                installer_path = self.update_info.get("installer_path")
                if installer_path and os.path.isfile(installer_path):
                    self.install_finished.emit({
                        "success": True,
                        "mode": "installer",
                        "installer_path": installer_path,
                    })
                    return

            if source == "github_release":
                dl_url = self.update_info.get("download_url")
                html_url = self.update_info.get("html_url") or GITHUB_RELEASES_PAGE
                if not dl_url:
                    self.install_finished.emit({
                        "success": True,
                        "mode": "browser",
                        "html_url": html_url,
                    })
                    return

                self.progress_text.emit("Downloading MoviePlayerLite-Setup.exe...")
                temp_setup = os.path.join(tempfile.gettempdir(), "MoviePlayerLite-Setup-Update.exe")
                req = urllib.request.Request(dl_url, headers={"User-Agent": f"MoviePlayerLite/{CURRENT_VERSION}"})
                with urllib.request.urlopen(req, timeout=120) as resp, open(temp_setup, "wb") as out_f:
                    shutil.copyfileobj(resp, out_f)

                if os.path.isfile(temp_setup) and os.path.getsize(temp_setup) > 1024:
                    self.install_finished.emit({
                        "success": True,
                        "mode": "installer",
                        "installer_path": temp_setup,
                        "prefer_installed_relaunch": True,
                    })
                    return

            self.install_finished.emit({
                "success": False,
                "error": "No valid update source or installer found.",
            })
        except Exception as e:
            self.install_finished.emit({
                "success": False,
                "error": str(e),
            })


def spawn_update_and_relaunch(install_result: dict, current_media_path: str = None) -> bool:
    """
    Launch a detached helper batch script that waits for the current PID to terminate,
    applies either portable exe replacement or silent Inno Setup installation,
    resets PyInstaller's onefile environment, and restarts Movie Player Lite.
    """
    if not install_result:
        return False

    mode = install_result.get("mode", "")
    pid = os.getpid()
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    installed_exe = os.path.join(local_app_data, "Programs", "Movie Player Lite", "movie-player-lite.exe")
    media_arg = f' "{current_media_path}"' if (current_media_path and os.path.exists(current_media_path)) else ""

    wait_pid_block = (
        f"set /a WAIT_COUNT=0\r\n"
        f":wait_loop\r\n"
        f'tasklist /FI "PID eq {pid}" 2>NUL | find /I "{pid}" >NUL\r\n'
        f"if errorlevel 1 goto pid_exited\r\n"
        f"set /a WAIT_COUNT+=1\r\n"
        f"if %WAIT_COUNT% GEQ 15 goto pid_exited\r\n"
        f"timeout /t 1 /nobreak > nul\r\n"
        f"goto wait_loop\r\n"
        f":pid_exited\r\n"
    )

    if mode == "portable_replace":
        new_exe = install_result.get("new_exe_path", "")
        target_exe = install_result.get("target_exe_path", "")
        opt_installer = install_result.get("installer_path", "")
        if not new_exe or not os.path.isfile(new_exe) or not target_exe:
            return False

        optional_setup_line = ""
        if opt_installer and os.path.isfile(opt_installer) and os.path.isfile(installed_exe):
            optional_setup_line = f'"{opt_installer}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS\r\n'

        bat_content = (
            "@echo off\r\n"
            "chcp 65001 > nul\r\n"
            'set "PYINSTALLER_RESET_ENVIRONMENT=1"\r\n'
            + wait_pid_block
            + "set /a COPY_TRY=0\r\n"
            ":copy_retry\r\n"
            f'copy /Y "{new_exe}" "{target_exe}" > nul\r\n'
            "if not errorlevel 1 goto copy_done\r\n"
            "set /a COPY_TRY+=1\r\n"
            "if %COPY_TRY% GEQ 10 goto copy_done\r\n"
            "timeout /t 1 /nobreak > nul\r\n"
            "goto copy_retry\r\n"
            ":copy_done\r\n"
            f"{optional_setup_line}"
            f'del /Q "{new_exe}" 2>nul\r\n'
            f'start "" "{target_exe}"{media_arg}\r\n'
            'del "%~f0"\r\n'
        )
    elif mode == "installer":
        installer_path = install_result.get("installer_path", "")
        if not installer_path or not os.path.isfile(installer_path):
            return False

        prefer_installed = bool(install_result.get("prefer_installed_relaunch"))
        if getattr(sys, "frozen", False) and not is_portable_onefile_exe() and not prefer_installed:
            relaunch_target = sys.executable
        else:
            relaunch_target = installed_exe

        bat_content = (
            "@echo off\r\n"
            "chcp 65001 > nul\r\n"
            'set "PYINSTALLER_RESET_ENVIRONMENT=1"\r\n'
            + wait_pid_block
            + f'"{installer_path}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS\r\n'
            + f'if exist "{relaunch_target}" start "" "{relaunch_target}"{media_arg}\r\n'
            + 'del "%~f0"\r\n'
        )
    else:
        return False

    bat_path = os.path.join(tempfile.gettempdir(), f"mpl_update_{pid}.bat")
    try:
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
        creationflags = (subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS) if os.name == "nt" else 0
        subprocess.Popen(["cmd.exe", "/c", bat_path], creationflags=creationflags, close_fds=True)
        return True
    except Exception:
        return False


def spawn_installer_and_relaunch(installer_path: str, current_media_path: str = None) -> bool:
    """Backward-compatible wrapper around spawn_update_and_relaunch."""
    return spawn_update_and_relaunch(
        {"mode": "installer", "installer_path": installer_path},
        current_media_path=current_media_path,
    )
