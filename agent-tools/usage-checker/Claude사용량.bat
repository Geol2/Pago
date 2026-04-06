@echo off
chcp 65001 > nul
REM Claude Code 사용량 위젯 실행기 (Windows - 터미널 방식)

SET SCRIPT_DIR=%~dp0
SET PY_SCRIPT=%SCRIPT_DIR%claude_usage_checker.py

REM requests 없으면 자동 설치
python -c "import requests" 2>nul || pip install requests -q

python "%PY_SCRIPT%" --desktop
