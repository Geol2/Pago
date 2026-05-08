@echo off
chcp 65001 > nul
title Claude 오크
SET PYTHONUTF8=1
SET SCRIPT_DIR=%~dp0
SET PY_SCRIPT=%SCRIPT_DIR%claude_usage.py

python -c "import PIL" 2>nul || pip install pillow -q

python "%PY_SCRIPT%" --orc
if %ERRORLEVEL% neq 0 pause
