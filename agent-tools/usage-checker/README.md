# Claude Code 사용량 체커

Claude Code 의 5시간/7일 사용량 한도를 시각화하고, 동시에 동작 중인 Claude 세션의 작업 상태를
오크(워크래프트3 일꾼) 위젯으로 보여준다. 인증 토큰은 시스템에 저장된 Claude Code 자격을
재사용하므로 별도 로그인 불필요.

## 의존성

- Python 3.9+
- 공통: `requests`, `pillow`
- 트레이(Windows): `pystray`
- 트레이(macOS): `rumps`
- `--graph`: `matplotlib`, `numpy`

처음 실행하면 부족한 패키지는 런처(.bat/.command)에서 자동 설치한다. 수동 설치:

```bash
pip install requests pillow pystray   # Windows
pip3 install requests pillow rumps    # macOS
```

## 실행 모드

| 모드 | 명령 | 용도 |
| --- | --- | --- |
| 트레이/메뉴바 ⭐ | `python claude_usage.py --tray` | 항상 보이는 알림 영역 아이콘. 사용량 + 작업 상태 배지 |
| 오크 위젯 | `python claude_usage.py --orc` | 항상 위 떠있는 데스크탑 캐릭터. 세션마다 오크 한 마리 |
| 접기/펴기 위젯 | `python claude_usage.py --desktop` | 게이지 + 막대 그래프 (Tk) |
| 게이지 그래프 | `python claude_usage.py --graph` | matplotlib 풀스크린 차트, 키 `R` 로 새로고침 |
| CLI 텍스트 | `python claude_usage.py` | 한 번 출력하고 종료. CI/스크립트용 |

`--tray` 와 `--orc` 는 같은 상태 파일(`~/.claude/agent_state.json`)을 공유하므로 동시 실행 가능.

### 트레이 (`--tray`)

- 사용률에 따라 아이콘 색 변화: 🟢 ~50% / 🟡 50–80% / 🔴 80%+
- 우상단에 작업 상태 배지(망치/?/✓)
- 우클릭 메뉴: 새로고침, 시작 시 자동 실행 토글, 종료
- 폴링 주기: 사용량 60초, 작업 상태 2초

### 오크 위젯 (`--orc`)

- 4가지 상태별 비주얼:
  - 💤 `idle` — 자는 오크, 라벨 "z z z"
  - 🔨 `working` — 망치 4프레임 스윙, 라벨 "열일 중..."
  - ❓ `waiting` — 멍한 표정 + 송곳니 뼈 장식, 라벨 "컨펌 대기"
  - ✅ `done` — 양팔 만세 + 별 반짝임, 라벨 "Jobs done!" (5초 후 자동 idle 강등)
- **여러 Claude Code 세션 동시 표시** — 세션마다 카드 한 장(프로젝트명 + 오크 + 라벨), 가로 나열, 최대 5개
- 위젯 시작 후 발생한 이벤트만 노출 — 실행 전 잔재 무시
- 마우스 좌클릭 드래그로 위치 이동, 우클릭 메뉴(컴팩트 모드/종료)
- 인증 불필요 (상태 파일만 읽음)

## Claude Code 훅 설치 — 작업 상태 추적

오크/트레이가 상태(working/waiting/done)를 표시하려면 Claude Code 의
세션 이벤트가 `~/.claude/agent_state.json` 에 기록돼야 한다. 다음 한 번 실행:

```bash
python hooks/install.py            # 설치
python hooks/install.py --status   # 현재 등록 상태 확인
python hooks/install.py --uninstall # 제거
```

**이벤트 매핑:**

| Claude Code 이벤트 | 매핑 상태 | 의미 |
| --- | --- | --- |
| `UserPromptSubmit` | `working` | 사용자 프롬프트 → Claude 작업 시작 |
| `Notification` (메시지에 `permission`/`권한`) | `waiting` | 도구 사용 권한 컨펌 요청 |
| `Notification` (그 외) | `done` | "your input 기다리는 중" 류 → 만세 후 idle |
| `Stop` | `done` | 응답 완료 |

설치 후 **새로 시작하는 Claude Code 세션**부터 적용된다. 기존 실행 중인 세션엔 영향 없음.

설치는 `~/.claude/settings.json` 의 `hooks` 항목만 손대고, 기존 설정은 백업
(`settings.json.bak.YYYYMMDD_HHMMSS`) 후 보존한다.

## 오크 스프라이트 커스터마이징

PIL 도형으로 그린 기본 오크 대신 본인이 만든 이미지로 교체 가능.
`agent-tools/usage-checker/orc_images/` 에 다음 명명 규칙으로 파일 두면 자동 인식:

| 파일명 | 종류 | 비고 |
| --- | --- | --- |
| `<state>.gif` | 애니메이션 GIF | 프레임별 native duration 존중 |
| `<state>_1.png`, `<state>_2.png`, … | PNG 시퀀스 | 100ms 간격으로 순환 |
| `<state>.png` | 단일 정적 이미지 | 애니메이션 없음 |

`<state>` ∈ `idle`, `working`, `waiting`, `done`.
우선순위는 GIF → PNG 시퀀스 → 단일 PNG → (없으면) PIL 도형 폴백.
이미지는 자동으로 비율 유지하며 160×180 안에 맞춰진다. 위젯 재시작하면 적용.

## 자동 시작

### Windows

- **개발 환경(파이썬 사용)**: `자동시작 등록.bat` 더블클릭 → 시작 폴더에 `Claude사용량.vbs` 단축키 생성
- **트레이 메뉴**: `--tray` 실행 후 우클릭 → "시작 시 자동 실행" 토글
- 해제: `자동시작 해제.bat` 또는 트레이 메뉴 토글 OFF
- VBS 런처는 콘솔창 없이 백그라운드 실행하며 에러는 `vbs_error.log` 에 남긴다

### macOS

- **메뉴바에서**: 트레이 메뉴 → "시작 시 자동 실행" 토글 (LaunchAgent plist 자동 생성:
  `~/Library/LaunchAgents/com.claude.usage.plist`)
- **수동**: `Claude tray 사용량.command` 더블클릭 → nohup 으로 백그라운드 실행

## 빌드 (Windows .exe)

Python 없는 환경에 배포하려면 PyInstaller 단일 실행파일로 패키징:

```cmd
build.bat
```

결과: `dist\AI_Usage.exe` (matplotlib/numpy/rumps 제외해 ~30MB).
배포 시 다음 파일 함께 묶기:

- `dist\AI_Usage.exe`
- `dist-template\autostart_register.bat`
- `dist-template\autostart_unregister.bat`

## Mac 런처

| 파일 | 역할 |
| --- | --- |
| `Claude tray 사용량.command` | 메뉴바 트레이 백그라운드 실행 (rumps 자동 설치) |
| `Claude desktop 사용량.command` | 접기/펴기 데스크탑 위젯 실행 (경로 하드코딩 — 본인 환경에 맞게 수정 필요) |

`.command` 파일은 더블클릭으로 실행. Finder 에서 처음 한 번
"열기 권한" 허용 필요할 수 있음.

## 트러블슈팅

| 증상 | 원인 / 해결 |
| --- | --- |
| `인증 정보를 찾을 수 없습니다` | Claude Code 가 한 번도 로그인 안 됨. `claude` CLI 로 먼저 로그인 |
| 트레이 401 에러 (Windows) | 토큰 만료. `claude` CLI 재로그인 후 트레이 재시작. 자동 재시도(3회) 후 실패하면 로그(`usage_checker.log`) 확인 |
| 오크가 idle 상태에서 안 움직임 | 정상 — idle 은 호흡 애니메이션 작아 거의 안 보임 |
| 오크가 컨펌 대기에 갇힘 | 권한 컨펌 후 해소되거나, `Notification` 메시지가 권한 키워드 미포함이면 done 처리되어야 함. `~/.claude/agent_state.json` 의 `message` 필드 확인 |
| 오크 위젯에 마젠타 박스 (Mac) | Tk 8.5 이하 — 8.6+ 필요. `python -c "import tkinter; print(tkinter.TkVersion)"` 로 확인 |
| 오크 위젯 우클릭 메뉴 안 뜸 (Mac) | 트랙패드 두손가락 클릭 또는 `Button-2` 시도 |
| 빌드된 .exe 가 즉시 종료 | `--noconsole` 빌드라 stdout 없음. `pythonw` 로 직접 실행해 import 에러 확인 |

## 상태 파일 / 디버그

- 사용량 로그: `agent-tools/usage-checker/usage_checker.log`
- 작업 상태: `~/.claude/agent_state.json`
  ```json
  {
    "sessions": {
      "<session_id>": {
        "state": "working|waiting|done|idle",
        "tool": "Edit",
        "cwd": "/path/to/project",
        "updated_at": "2026-05-08T10:30:15",
        "raw_event": "waiting",
        "message": "Claude needs permission to use Bash"
      }
    },
    "latest": "<session_id>",
    "updated_at": "..."
  }
  ```
- 한 시간 이상 갱신 없는 세션은 훅에서 자동 정리 (`STALE_SECONDS = 3600`)

## 파일 구조

```
agent-tools/usage-checker/
├── claude_usage.py          # 메인 스크립트 (CLI/트레이/오크/그래프/데스크탑 통합)
├── hooks/
│   ├── install.py           # 훅 설치/제거/상태 확인
│   └── state_hook.py        # Claude Code 이벤트 → 상태 파일 기록
├── orc_images/              # 사용자 스프라이트 (선택)
├── build.bat                # Windows .exe 빌드
├── AI_Usage.spec            # PyInstaller 스펙
├── Claude사용량.bat          # Windows 콘솔 런처
├── Claude사용량.vbs          # Windows 콘솔 없는 런처
├── Claude tray 사용량.command  # macOS 트레이 런처
├── Claude desktop 사용량.command  # macOS 데스크탑 위젯 런처
├── 자동시작 등록.bat          # Windows 자동시작 단축키 생성
├── 자동시작 해제.bat          # Windows 자동시작 해제
├── usage_checker.log        # 인증/요청 진단 로그
└── README.md                # 이 파일
```
