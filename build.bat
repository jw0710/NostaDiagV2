@echo off
setlocal
cd /d "%~dp0"

echo === NostaDiag .exe Builder ===
echo.

REM Make sure pyinstaller is available
python -m pip install --quiet --upgrade pyinstaller pywebview pycryptodome pyserial
if errorlevel 1 (
    echo [FAIL] Could not install build dependencies.
    pause
    exit /b 1
)

REM Clean previous build
if exist build  rmdir /s /q build
if exist dist   rmdir /s /q dist
if exist NostaDiag.spec del /q NostaDiag.spec

REM Build single .exe with bundled resources
python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name NostaDiag ^
    --icon "assets\logo.ico" ^
    --add-data "webui;webui" ^
    --add-data "assets;assets" ^
    --add-data "sandbox_data.json;." ^
    app_web.py

if errorlevel 1 (
    echo.
    echo [FAIL] Build failed.
    pause
    exit /b 1
)

echo.
echo === Done ===
echo Your .exe is at:  dist\NostaDiag.exe
echo Just send that one file to anybody. No install needed.
echo.
pause
