@echo off
setlocal
cd /d "%~dp0"

echo === NostaDiag Installer Builder ===
echo.

if not exist "dist\NostaDiag.exe" (
    echo [FAIL] dist\NostaDiag.exe not found.
    echo        Run build.bat first.
    pause
    exit /b 1
)

set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files (x86)\Inno Setup 5\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 5\ISCC.exe"

if not defined ISCC (
    echo [FAIL] Inno Setup nicht gefunden.
    echo        Bitte installieren: https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

echo Verwende: %ISCC%
echo.

"%ISCC%" NostaDiag_Setup.iss
if errorlevel 1 (
    echo.
    echo [FAIL] Installer-Build fehlgeschlagen.
    pause
    exit /b 1
)

echo.
echo === Fertig ===
echo Installer:  dist\NostaDiag_v2.0_Setup.exe
echo.
pause
