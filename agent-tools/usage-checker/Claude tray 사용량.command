#!/bin/bash
# macOS용 더블클릭 런처 — 메뉴바에 Claude 사용량 표시 (터미널 창 없이 실행)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# rumps 설치 확인
python3 -c "import rumps" 2>/dev/null || pip3 install rumps -q

# 이미 실행 중이면 종료
if pgrep -f "claude_usage.py" > /dev/null 2>&1; then
    osascript -e 'tell application "Terminal" to close front window' 2>/dev/null || true
    exit 0
fi

# 백그라운드로 실행 (터미널과 분리)
nohup python3 "$SCRIPT_DIR/claude_usage.py" --tray >> /tmp/claude_usage_tray.log 2>&1 &
disown

# 터미널 창 자동 닫기
sleep 0.5
osascript -e 'tell application "Terminal" to close front window' 2>/dev/null || true
exit 0
