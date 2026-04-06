@echo off
chcp 65001 > nul
SET PYTHONUTF8=1
SET SCRIPT_DIR=%~dp0
SET PY_SCRIPT=%SCRIPT_DIR%claude_usage.py

python -c "import requests" 2>nul || pip install requests -q

python "%PY_SCRIPT%" --desktop
if %ERRORLEVEL% neq 0 pause
