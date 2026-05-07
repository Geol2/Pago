@echo off
setlocal

REM ----------------------------------------------------------
REM Claude usage checker - Windows standalone exe builder
REM Output: dist\AI_Usage.exe (no Python required to run)
REM ----------------------------------------------------------

set SCRIPT_DIR=%~dp0
set PY_SCRIPT=%SCRIPT_DIR%claude_usage.py
set DIST_NAME=AI_Usage

pushd "%SCRIPT_DIR%"

echo.
echo [1/3] Checking dependencies
python -c "import PyInstaller" 2>nul || pip install pyinstaller -q
python -c "import requests"    2>nul || pip install requests -q
python -c "import pystray"     2>nul || pip install pystray -q
python -c "import PIL"         2>nul || pip install pillow -q

echo.
echo [2/3] Cleaning previous build
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
if exist "%DIST_NAME%.spec" del /q "%DIST_NAME%.spec"

echo.
echo [3/3] Running PyInstaller
python -m PyInstaller --onefile --noconsole --name "%DIST_NAME%" --hidden-import=pystray._win32 --hidden-import=PIL._tkinter_finder --collect-submodules=pystray --exclude-module=matplotlib --exclude-module=numpy --exclude-module=rumps "%PY_SCRIPT%"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [FAIL] Build error
    popd
    pause
    exit /b 1
)

echo.
echo ----------------------------------------------------------
echo [DONE] dist\%DIST_NAME%.exe created
echo.
echo Files to bundle for distribution:
echo   - dist\%DIST_NAME%.exe
echo   - dist-template\autostart_register.bat
echo   - dist-template\autostart_unregister.bat
echo ----------------------------------------------------------

popd
pause
