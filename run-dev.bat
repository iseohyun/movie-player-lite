@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0"

rem ===================================================
rem   Movie Player Lite - Dev build and run
rem   Usage: run-dev.bat          (light build, without ffmpeg)
rem          run-dev.bat full     (full package, bundles ffmpeg.exe)
rem   1) stops the running app and any unfinished build
rem   2) rebuilds dist\movie-player-lite.exe
rem   3) launches the new build
rem ===================================================

set "APP_NAME=movie-player-lite"
set "APP_EXE=dist\%APP_NAME%.exe"
set "PYI_ARGS=--noconfirm --name "%APP_NAME%" --noupx --onefile --noconsole --hidden-import PyQt6.QtCore --hidden-import PyQt6.QtGui --hidden-import PyQt6.QtWidgets --hidden-import PyQt6.QtMultimedia --hidden-import PyQt6.QtMultimediaWidgets --hidden-import PyQt6.QtNetwork --add-data "icon.ico;." --add-data "locales;locales" --copy-metadata pyinstaller --copy-metadata PyQt6-sip --icon="icon.ico""

echo [1/3] Stopping running app and unfinished builds...
taskkill /F /T /IM "%APP_NAME%.exe" > nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -match 'PyInstaller' -and $_.CommandLine -match '%APP_NAME%' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" > nul 2>&1

set /a WAIT_COUNT=0
:wait_for_exit
tasklist /FI "IMAGENAME eq %APP_NAME%.exe" 2>nul | findstr /I /C:"%APP_NAME%.exe" > nul
if errorlevel 1 goto build
set /a WAIT_COUNT+=1
if %WAIT_COUNT% GEQ 15 (
    echo [ERROR] %APP_NAME%.exe is still running. Close it manually and try again.
    exit /b 1
)
ping -n 2 127.0.0.1 > nul
goto wait_for_exit

:build
if /I "%~1"=="full" (
    if not exist "ffmpeg.exe" (
        echo [ERROR] ffmpeg.exe not found in "%CD%". Required for the full package.
        exit /b 1
    )
    echo [2/3] Building full package with ffmpeg.exe...
    python -m PyInstaller %PYI_ARGS% --add-binary "ffmpeg.exe;." movie-player-lite.py
) else (
    echo [2/3] Building light version...
    python -m PyInstaller %PYI_ARGS% movie-player-lite.py
)
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. The app was not started.
    exit /b 1
)
if not exist "%APP_EXE%" (
    echo [ERROR] Build finished but "%APP_EXE%" was not created.
    exit /b 1
)

echo [3/3] Starting %APP_EXE% ...
start "" "%CD%\%APP_EXE%"
endlocal
