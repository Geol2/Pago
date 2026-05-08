#!/bin/bash
# macOS 더블클릭 런처 — 오크 위젯 (터미널 창 없이 백그라운드 실행)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Pillow 자동 설치
python3 -c "import PIL" 2>/dev/null || pip3 install pillow -q

# 이미 실행 중이면 (--orc 인스턴스 한정) 종료
if pgrep -f "claude_usage.py --orc" > /dev/null 2>&1; then
    osascript -e 'tell application "Terminal" to close front window' 2>/dev/null || true
    exit 0
fi

# 백그라운드 분리 실행
nohup python3 "$SCRIPT_DIR/claude_usage.py" --orc >> /tmp/claude_usage_orc.log 2>&1 &
disown

# 터미널 창 자동 닫기
sleep 0.5
osascript -e 'tell application "Terminal" to close front window' 2>/dev/null || true
exit 0
