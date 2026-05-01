#!/bin/bash
# Claude Code 사용량 위젯 실행기 (Mac)
SCRIPT="/Users/geol/02_project/SSH/Pago/agent-tools/usage-checker/claude_usage.py"

# requests 없으면 자동 설치
python3 -c "import requests" 2>/dev/null || pip3 install requests -q

python3 "$SCRIPT" --desktop
