@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0"

rem ===================================================
rem   Movie Player Lite - Installer build
rem   1) builds the app as a folder (PyInstaller --onedir) into dist_installer\
rem   2) compiles installer.iss with Inno Setup into installer_output\
rem   The version shown by the installer is the newest "## [vX.Y.Z]" entry in VERSION.md.
rem   Requires Inno Setup 6:  winget install JRSoftware.InnoSetup
rem ===================================================

set "APP_NAME=movie-player-lite"

set "APP_VERSION="
for /f "tokens=2 delims=[]" %%v in ('findstr /B /C:"## [v" VERSION.md') do if not defined APP_VERSION set "APP_VERSION=%%v"
if not defined APP_VERSION (
    echo [ERROR] Could not read a version like "## [v1.2.3]" from VERSION.md.
    exit /b 1
)
set "APP_VERSION=%APP_VERSION:~1%"

set "ISCC="
for %%i in (ISCC.exe) do if not "%%~$PATH:i"=="" set "ISCC=%%~$PATH:i"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo [ERROR] Inno Setup 6 was not found. Install it with: winget install JRSoftware.InnoSetup
    exit /b 1
)

echo [1/2] Building app folder for version %APP_VERSION% ...
python -m PyInstaller --noconfirm --name "%APP_NAME%" --noupx --onedir --noconsole --distpath dist_installer --workpath build_installer --specpath build_installer --hidden-import PyQt6.QtCore --hidden-import PyQt6.QtGui --hidden-import PyQt6.QtWidgets --hidden-import PyQt6.QtMultimedia --hidden-import PyQt6.QtMultimediaWidgets --hidden-import PyQt6.QtNetwork --add-data "%CD%\icon.ico;." --add-data "%CD%\locales;locales" --copy-metadata pyinstaller --copy-metadata PyQt6-sip --icon="%CD%\icon.ico" movie-player-lite.py
if errorlevel 1 (
    echo.
    echo [ERROR] App build failed. The installer was not created.
    exit /b 1
)

echo [2/2] Compiling installer...
"%ISCC%" /Qp /DAppVersion=%APP_VERSION% installer.iss
if errorlevel 1 (
    echo.
    echo [ERROR] Installer compilation failed.
    exit /b 1
)

echo.
echo Installer created: installer_output\MoviePlayerLite-Setup.exe  (version %APP_VERSION%)
endlocal
