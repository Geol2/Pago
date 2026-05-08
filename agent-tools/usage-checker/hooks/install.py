#!/usr/bin/env python3
"""
Claude Code 훅 설치/제거 — ~/.claude/settings.json 에 state_hook 등록.

  python install.py              # 설치 (기존 설정 백업)
  python install.py --uninstall  # 제거
  python install.py --status     # 현재 상태 확인

설치 후 Claude Code 새 세션부터 적용.
훅이 ~/.claude/agent_state.json 에 상태를 기록하면 트레이가 그것을 읽어 오크 배지를 표시한다.
"""
import sys
import json
import shutil
from datetime import datetime
from pathlib import Path

HOOK_SCRIPT = (Path(__file__).resolve().parent / "state_hook.py").resolve()
SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
HOOK_TAG = "agent-tools/usage-checker:state_hook"

# (이벤트명, 기록할 상태)
EVENTS = [
    ("UserPromptSubmit", "working"),
    ("Notification",     "waiting"),
    ("Stop",             "done"),
]


def _python_executable() -> str:
    """훅 실행에 쓸 파이썬 경로 — Windows 에서는 콘솔 깜빡임 방지를 위해 pythonw 우선."""
    if sys.platform == "win32":
        pyw = Path(sys.executable).with_name("pythonw.exe")
        if pyw.exists():
            return str(pyw)
    return sys.executable


def _hook_command(state: str) -> str:
    py = _python_executable()
    return f'"{py}" "{HOOK_SCRIPT}" --event={state} --tag={HOOK_TAG}'


def _is_our_hook(cmd: str) -> bool:
    return isinstance(cmd, str) and HOOK_TAG in cmd


def _load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"⚠ settings.json 파싱 실패: {e}")
        print("  파일이 손상되었을 수 있습니다. 수동 확인 후 다시 실행하세요.")
        sys.exit(1)


def _save_settings(data: dict):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SETTINGS_PATH.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = SETTINGS_PATH.with_name(f"settings.json.bak.{ts}")
        shutil.copy2(SETTINGS_PATH, backup)
    SETTINGS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _strip_existing(hooks: dict) -> dict:
    """이전에 우리가 설치한 훅 항목만 제거하고 그 외는 보존."""
    cleaned = {}
    for event, configs in hooks.items():
        if not isinstance(configs, list):
            cleaned[event] = configs
            continue
        new_configs = []
        for cfg in configs:
            if not isinstance(cfg, dict):
                new_configs.append(cfg)
                continue
            inner = cfg.get("hooks") or []
            kept = [
                h for h in inner
                if not (isinstance(h, dict) and _is_our_hook(h.get("command", "")))
            ]
            if kept:
                new_cfg = dict(cfg)
                new_cfg["hooks"] = kept
                new_configs.append(new_cfg)
            elif not inner:
                new_configs.append(cfg)
        if new_configs:
            cleaned[event] = new_configs
    return cleaned


def install():
    if not HOOK_SCRIPT.exists():
        print(f"훅 스크립트를 찾을 수 없습니다: {HOOK_SCRIPT}")
        sys.exit(1)

    data = _load_settings()
    hooks = data.get("hooks", {}) if isinstance(data.get("hooks"), dict) else {}
    hooks = _strip_existing(hooks)

    for event_name, state in EVENTS:
        cfg = {"hooks": [{"type": "command", "command": _hook_command(state)}]}
        hooks.setdefault(event_name, []).append(cfg)

    data["hooks"] = hooks
    _save_settings(data)

    print("✓ 훅 설치 완료")
    print(f"  설정 파일: {SETTINGS_PATH}")
    print(f"  훅 스크립트: {HOOK_SCRIPT}")
    print(f"  파이썬: {_python_executable()}")
    print()
    print("이벤트 매핑:")
    for ev, st in EVENTS:
        print(f"  {ev:18s} → state={st}")
    print()
    print("Claude Code 를 새로 실행하면 적용됩니다.")
    print("상태 파일: ~/.claude/agent_state.json")


def uninstall():
    data = _load_settings()
    if not data:
        print("설정 파일이 비어 있습니다.")
        return
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        print("hooks 항목이 없습니다.")
        return
    cleaned = _strip_existing(hooks)
    if cleaned:
        data["hooks"] = cleaned
    else:
        data.pop("hooks", None)
    _save_settings(data)
    print(f"✓ 훅 제거 완료 → {SETTINGS_PATH}")


def status():
    data = _load_settings()
    hooks = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(hooks, dict):
        print("훅이 설치되지 않았습니다.")
        return
    found = []
    for event_name, configs in hooks.items():
        if not isinstance(configs, list):
            continue
        for cfg in configs:
            if not isinstance(cfg, dict):
                continue
            for h in cfg.get("hooks") or []:
                if isinstance(h, dict) and _is_our_hook(h.get("command", "")):
                    found.append((event_name, h.get("command", "")))
    if not found:
        print("우리가 설치한 훅이 없습니다.")
        return
    print(f"설치된 훅: {len(found)}개")
    for ev, cmd in found:
        print(f"  [{ev}] {cmd}")


def main():
    if "--uninstall" in sys.argv:
        uninstall()
    elif "--status" in sys.argv:
        status()
    else:
        install()


if __name__ == "__main__":
    main()
