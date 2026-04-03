# Claude Code 사용량 체커 🤖

Claude Code의 5시간/7일 사용량 한도를 실시간으로 확인하는 Python 프로그램입니다.

## 특징

- ✅ macOS Keychain에서 자동으로 인증 토큰 가져오기
- 📊 5시간 rolling window 사용률 확인
- 📅 7일 주간 한도 사용률 확인
- 🎨 프로그레스 바로 시각적 표시
- ⏰ 리셋까지 남은 시간 표시
- ⚠️ 80% 초과 시 경고 메시지

## 요구사항

- **Windows, macOS, Linux 모두 지원!**
- Python 3.7+
- Claude Code가 설치되어 있고 로그인된 상태
  - Windows: `%APPDATA%\Claude Code\credentials.json` 사용
  - macOS: Keychain 사용

## 설치

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. 실행 권한 부여
chmod +x claude_usage_checker.py
```

## 사용법

```bash
# 방법 1: Python으로 직접 실행 (Windows/macOS/Linux 모두)
python3 claude_usage_checker_v2.py

# 방법 2: 기본 버전 (macOS 전용)
python3 claude_usage_checker.py

# 방법 3: 실행 파일처럼 사용 (macOS/Linux)
chmod +x claude_usage_checker_v2.py
./claude_usage_checker_v2.py
```

## 출력 예시

```
🤖 Claude Code 사용량 체커
------------------------------------------------------------
✓ 인증 성공! (플랜: PRO)

📡 사용량 정보를 가져오는 중...

============================================================
📊 Claude Code 사용량 현황
============================================================

🕐 5시간 Rolling Window
   사용률: 23.5%
   [█████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]
   리셋: 3시간 42분 후

📅 7일 주간 한도
   사용률: 15.8%
   [██████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]
   리셋: 4일 12시간 후

============================================================

💡 Tip: 'claude /status' 명령어로도 터미널에서 확인 가능합니다.
```

## API 정보

이 프로그램은 다음 엔드포인트를 사용합니다:
- `GET https://api.anthropic.com/api/oauth/usage`

**인증 방법:**
- **Windows**: `%APPDATA%\Claude Code\credentials.json` 파일
- **macOS**: Keychain의 "Claude Code-credentials" 서비스
- **Linux**: Windows와 동일한 파일 경로 시도

## 문제 해결

### Windows: "Claude Code 인증 정보를 찾을 수 없습니다"

1. **Claude Code 설치 확인**
   ```cmd
   npm install -g @anthropic-ai/claude-code
   ```

2. **로그인 확인**
   ```cmd
   claude logout
   claude login
   ```

3. **credentials.json 위치 확인**
   - 기본 경로: `%APPDATA%\Claude Code\credentials.json`
   - 파워셸에서 확인: `explorer $env:APPDATA\Claude Code`

### macOS: "Keychain에서 Claude Code 인증 정보를 찾을 수 없습니다"

```bash
# Claude Code에 다시 로그인
claude logout
claude login
```

### 공통: "인증 실패. 토큰이 만료되었을 수 있습니다"

```bash
# 토큰 갱신
claude logout
claude login
```

## 추가 기능 아이디어

- [x] Windows/Linux 지원 (완료!)
- [ ] 터미널 상태바 통합 (tmux/zsh)
- [ ] JSON 출력 모드 추가
- [ ] cron으로 주기적 알림
- [ ] 웹 대시보드 버전

## 참고 자료

- [Claude Code 공식 문서](https://docs.anthropic.com/en/docs/claude-code/overview)
- [사용량 한도 설명](https://support.claude.com/en/articles/11647753-how-do-usage-and-length-limits-work)

## 라이센스

MIT

---

만든이: 인걸이 @ 엑스소프트 😎
