# Claude Code 사용량 체커 🤖

Claude Code의 5시간/7일 사용량 한도를 실시간으로 확인하는 Python 프로그램입니다.

## 특징

- Windows / macOS 자동 인증 (Keychain / credentials.json)
- 5시간 rolling window 및 7일 주간 한도 사용률 확인
- 데스크탑 위젯: 접기/펴기 토글, 항상 위, 1분 자동 갱신
- 게이지 그래프: matplotlib 기반 시각화
- 리셋까지 남은 시간 표시 / 80% 초과 시 경고

## 파일 구성

```
usage-checker/
├── claude_usage.py          # 통합 메인 스크립트
├── Claude사용량.bat          # 위젯 실행 (터미널 창 포함)
├── Claude사용량.vbs          # 위젯 실행 (콘솔 창 없이)
```

## 요구사항

- Python 3.7+
- Claude Code 로그인 상태
  - Windows: `~/.claude/.credentials.json`
  - macOS: Keychain (`Claude Code-credentials`)
- 그래프 기능: `pip install matplotlib`

## 설치

```bash
pip install -r requirements.txt
```

## 사용법

### 터미널 텍스트 출력

```bash
python claude_usage.py
```

### 데스크탑 위젯 (접기/펴기)

```bash
python claude_usage.py --desktop
```

헤더 오른쪽 `▲/▼` 버튼으로 접기/펴기 가능:
- **펼침**: 프로그레스 바 + 리셋 시간 표시
- **접힘**: `5h 17%  7d 21%` 한 줄 미니뷰

Windows 더블클릭 실행:
- `Claude사용량.bat` — 터미널 창 포함
- `Claude사용량.vbs` — 콘솔 창 없이 백그라운드 실행

### 게이지 그래프 (matplotlib)

```bash
python claude_usage.py --graph
```

Windows 더블클릭 실행:
- `Claude사용량그래프.bat` — 터미널 창 포함
- `Claude사용량그래프.vbs` — 콘솔 창 없이 실행

## API 정보

- 엔드포인트: `GET https://api.anthropic.com/api/oauth/usage`
- 인증: OAuth Bearer 토큰 (Claude Code 로그인 시 자동 발급)

## 문제 해결

### 인증 정보를 찾을 수 없는 경우

```bash
claude logout
claude login
```

Windows에서 credentials 위치 확인:
```cmd
explorer %USERPROFILE%\.claude
```

### 토큰 만료

```bash
claude logout
claude login
```

## 추가 기능 아이디어

- [x] Windows/macOS 지원
- [x] 게이지 그래프 시각화
- [x] 데스크탑 위젯 접기/펴기
- [ ] 사용량 히스토리 로깅 & 추이 그래프
- [ ] cron으로 주기적 알림
- [ ] 터미널 상태바 통합 (tmux/zsh)

## 참고 자료

- [Claude Code 공식 문서](https://docs.anthropic.com/en/docs/claude-code/overview)
- [사용량 한도 설명](https://support.claude.com/en/articles/11647753-how-do-usage-and-length-limits-work)

## 라이센스

MIT

---

만든이: 인걸이 @ 엑스소프트 😎
