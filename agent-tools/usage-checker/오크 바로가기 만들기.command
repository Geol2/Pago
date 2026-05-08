#!/bin/bash
# macOS 바탕화면에 오크 위젯 바로가기(심볼릭 링크) 생성
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="$SCRIPT_DIR/Claude orc.command"
LINK="$HOME/Desktop/Claude 오크.command"

if [ ! -f "$TARGET" ]; then
    echo "[실패] Claude orc.command 가 없습니다: $TARGET"
    exit 1
fi

# 실행 권한 보장
chmod +x "$TARGET"

# 기존 링크가 있으면 갱신
ln -sf "$TARGET" "$LINK"
chmod +x "$LINK"

echo
echo "[완료] 바탕화면에 'Claude 오크' 바로가기 생성됨"
echo "  $LINK"
echo
echo "더블클릭으로 실행되며, 처음 한 번은 우클릭 → '열기' 로 권한 허용 필요할 수 있습니다."
echo
read -p "[엔터] 닫기" _
