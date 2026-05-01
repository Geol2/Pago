#!/bin/bash
# macOS용 더블클릭 런처 — 메뉴바에 Claude 사용량 표시
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

pip show rumps &>/dev/null || pip install rumps -q

python3 "$SCRIPT_DIR/claude_usage.py" --tray
