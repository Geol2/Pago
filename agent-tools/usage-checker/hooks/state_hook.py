#!/usr/bin/env python3
"""
Claude Code 훅 — 현재 작업 상태를 ~/.claude/agent_state.json 에 기록.
사용량 트레이가 이 파일을 읽어 오크 상태(working / waiting / done)를 표시한다.

사용법:
    python state_hook.py --event=<state>
    state ∈ {working, waiting, done}

페이로드는 stdin 으로 JSON 으로 들어옴 — Claude Code 가 자동 전달.
훅은 빠르게 종료해야 하므로 어떤 예외도 표면화하지 않고 0 으로 끝난다.
"""
import sys
import json
import os
from datetime import datetime
from pathlib import Path

STATE_FILE = Path.home() / ".claude" / "agent_state.json"
STALE_SECONDS = 60 * 60  # 1시간 이상 갱신 없는 세션은 정리


def _parse_args() -> str:
    for arg in sys.argv[1:]:
        if arg.startswith("--event="):
            return arg.split("=", 1)[1].strip() or "unknown"
    return "unknown"


# Notification 메시지로 진짜 권한 컨펌 vs 일반 알림 구분
_PERMISSION_KEYWORDS = (
    "permission", "approve", "approval", "allow", "denied",
    "권한", "승인", "허용",
)


def _classify_state(event_arg: str, payload: dict) -> str:
    """Notification 은 메시지 내용으로 컨펌(waiting) vs 끝남(done) 구분."""
    if event_arg != "waiting":
        return event_arg
    msg = (payload.get("message") or "").lower()
    if any(kw in msg for kw in _PERMISSION_KEYWORDS):
        return "waiting"
    # "Claude is waiting for your input" 같은 단순 유휴 알림은 done 처리
    # → 위젯이 만세 5초 후 idle 로 강등
    return "done"


def _read_payload() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw and raw.strip() else {}
    except Exception:
        return {}


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {"sessions": {}, "latest": None}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"sessions": {}, "latest": None}
        if not isinstance(data.get("sessions"), dict):
            data["sessions"] = {}
        return data
    except Exception:
        return {"sessions": {}, "latest": None}


def _prune(sessions: dict, now: datetime) -> dict:
    fresh = {}
    for sid, info in sessions.items():
        if not isinstance(info, dict):
            continue
        try:
            ts = datetime.fromisoformat(info.get("updated_at", ""))
            if (now - ts).total_seconds() < STALE_SECONDS:
                fresh[sid] = info
        except Exception:
            continue
    return fresh


def main():
    event_arg = _parse_args()
    payload = _read_payload()
    state = _classify_state(event_arg, payload)
    now = datetime.now()

    session_id = str(payload.get("session_id") or "default")
    cwd = payload.get("cwd") or os.getcwd()
    tool_name = payload.get("tool_name") or ""

    state_data = _load_state()
    sessions = _prune(state_data.get("sessions", {}), now)

    sessions[session_id] = {
        "state": state,
        "tool": tool_name,
        "cwd": str(cwd),
        "updated_at": now.isoformat(timespec="seconds"),
        # 디버깅용 — 어떤 알림이 들어와서 분류됐는지 기록
        "raw_event": event_arg,
        "message": payload.get("message", ""),
        # Claude Code 프로세스 PID — 위젯이 종료 감지에 사용
        "claude_pid": os.getppid(),
    }

    state_data["sessions"] = sessions
    state_data["latest"] = session_id
    state_data["updated_at"] = now.isoformat(timespec="seconds")

    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(
            json.dumps(state_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass

    # 훅이 비-제로로 끝나면 PreToolUse 등에서 동작이 차단될 수 있음 — 항상 0 반환
    sys.exit(0)


if __name__ == "__main__":
    main()
