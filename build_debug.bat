@echo off
setlocal
cd /d "%~dp0"

echo === NostaDiag DEBUG build (console visible, no UPX) ===
echo This build shows a console window so startup errors are visible.
echo.

python -m pip install --quiet --upgrade pyinstaller pywebview pycryptodome pyserial
if errorlevel 1 (
    echo [FAIL] Could not install build dependencies.
    pause
    exit /b 1
)

if exist build rmdir /s /q build

REM --console : keep a console so tracebacks are visible
REM --noupx   : disable UPX (UPX can corrupt WebView2 / Python DLLs -> silent crash)
REM Separate name so it does not overwrite the normal dist\NostaDiag.exe
python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --console ^
    --noupx ^
    --name NostaDiag_debug ^
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
echo Now run it FROM PowerShell so you can read any error:
echo     .\dist\NostaDiag_debug.exe
echo.
pause
