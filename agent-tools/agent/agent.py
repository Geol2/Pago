"""
eXrep dWorks 개발 보조 에이전트
Ollama + qwen3.5 기반 tool-calling 루프
"""
import json
import os
import re
import sys
import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

# Windows 터미널 한글 출력 설정
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    sys.stdin.reconfigure(encoding="utf-8")

from config import OLLAMA_URL, MODEL, SYSTEM_PROMPT
from tools import TOOL_DEFINITIONS, call_tool
import cache

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.live import Live
from rich.text import Text
from rich.table import Table
from rich import box

console = Console()
MAX_STEPS = 30
TIMEOUT   = 600

TOOL_ICONS = {
    "read_file":   "📄",
    "write_file":  "✏️",
    "list_files":  "📁",
    "search_code": "🔍",
}


_STREAM_DONE = object()  # 스트림 종료 센티널


def chat_with_spinner(messages: list, step: int, step_history: list):
    """스트리밍으로 Ollama 호출.
    - 첫 토큰 전: 경과 시간 스피너 표시
    - 첫 토큰 후: 실시간 스트리밍 출력
    """
    start      = time.time()
    token_q    = queue.Queue()   # 토큰 큐 (스레드 → 메인)
    tool_calls = []
    err_box    = {}

    def _stream():
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "messages": messages,
                    "tools": TOOL_DEFINITIONS,
                    "stream": True,
                    "options": {"temperature": 0.2, "num_ctx": 16384},
                    "think": False,
                },
                stream=True,
                timeout=(10, 180),
            )
            resp.raise_for_status()
            in_think = False
            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                chunk = json.loads(raw_line)
                msg   = chunk.get("message", {})

                # tool_calls는 어느 청크에나 올 수 있음
                if msg.get("tool_calls"):
                    tool_calls.extend(msg["tool_calls"])

                token = msg.get("content", "")
                if token:
                    # <think> 블록 필터링 (Qwen3 thinking 모드)
                    if "<think>" in token:
                        in_think = True
                    if in_think:
                        if "</think>" in token:
                            in_think = False
                        continue
                    token_q.put(token)
        except Exception as exc:
            err_box["exc"] = exc
        finally:
            token_q.put(_STREAM_DONE)

    threading.Thread(target=_stream, daemon=True).start()

    # ── 첫 토큰 전: 스피너 + 경과 시간 ──
    spinner      = Spinner("dots")
    full_content = []
    first_arrived = False

    with Live(console=console, refresh_per_second=12) as live:
        while True:
            try:
                item = token_q.get(timeout=0.08)
            except queue.Empty:
                if not first_arrived:
                    elapsed = int(time.time() - start)
                    live.update(Text.assemble(
                        spinner.render(time.time()), " ",
                        ("생각 중... ", "dim"),
                        (f"(step {step})", "dim cyan"),
                        ("  ", ""),
                        (f"{elapsed}s", "bold yellow"),
                    ))
                continue

            if item is _STREAM_DONE:
                break

            if not first_arrived:
                live.stop()
                console.print(f"\n[dim cyan](step {step})[/dim cyan]")
                first_arrived = True

            full_content.append(item)
            console.print(item, end="", highlight=False)

    if "exc" in err_box:
        raise err_box["exc"]

    if full_content:
        console.print()  # 줄바꿈

    elapsed_final = time.time() - start
    step_history.append(elapsed_final)
    return {"role": "assistant", "content": "".join(full_content), "tool_calls": tool_calls}


def _make_diff(old: str, new: str, path: str) -> str:
    """unified diff 문자열을 반환한다."""
    import difflib
    diff = list(difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"기존  {path}",
        tofile=f"변경후 {path}",
        n=3,
    ))
    if not diff:
        return "(변경 없음)"
    # 최대 60줄만 표시
    lines = diff[:60]
    if len(diff) > 60:
        lines.append(f"... ({len(diff) - 60}줄 더)\n")
    return "".join(lines)


def _confirm_writes(parsed_calls: list) -> list:
    """write_file 호출에 대해 diff를 보여주고 사용자 확인을 받는다."""
    import questionary
    confirmed = []
    for fn_name, fn_args in parsed_calls:
        if fn_name != "write_file":
            confirmed.append((fn_name, fn_args))
            continue

        path       = fn_args.get("path", "?")
        new_content = fn_args.get("content", "")

        # 기존 파일 읽기 (캐시 또는 디스크)
        from tools import read_file as _read
        existing = _read(path)
        is_new_file = existing.startswith("[ERROR]") or existing.startswith("[auto-found")

        # 내용이 스니펫(불완전)인지 경고
        ext = path.rsplit(".", 1)[-1].lower()
        is_snippet = False
        if ext == "java" and not new_content.lstrip().startswith("package"):
            is_snippet = True
        elif ext in ("xml", "html") and not new_content.lstrip().startswith("<"):
            is_snippet = True

        if is_new_file:
            panel_body = (
                f"[bold yellow]✏️  새 파일 생성[/bold yellow]\n"
                f"[dim]경로:[/dim] [cyan]{path}[/cyan]\n\n"
                f"[dim]내용 미리보기 (앞 300자):[/dim]\n{new_content[:300]}{'...' if len(new_content) > 300 else ''}"
            )
        else:
            diff_text = _make_diff(existing, new_content, path)
            panel_body = (
                f"[bold yellow]✏️  파일 수정 요청[/bold yellow]\n"
                f"[dim]경로:[/dim] [cyan]{path}[/cyan]\n\n"
                f"[dim]diff:[/dim]\n{diff_text}"
            )

        if is_snippet:
            panel_body += "\n\n[bold red]⚠ 경고: 완전한 파일이 아닌 코드 스니펫으로 보입니다. 저장하면 기존 파일 전체가 덮어써집니다.[/bold red]"

        console.print(Panel(panel_body, border_style="yellow", expand=False))

        ok = questionary.confirm(f"  {path} 을(를) 저장할까요?", default=not is_snippet).ask()
        if ok is None or not ok:
            console.print(f"[dim]↩ 건너뜀: {path}[/dim]")
            confirmed.append(("__skip__", {"path": path}))
        else:
            confirmed.append((fn_name, fn_args))
    return confirmed


def run_tools_parallel(parsed_calls: list) -> list:
    """write_file 확인 후 도구를 병렬 실행하고 라이브로 진행상황 표시."""
    parsed_calls = _confirm_writes(parsed_calls)
    n = len(parsed_calls)
    states  = ["pending"] * n   # pending | running | done | error
    results = [None] * n
    starts  = [None] * n

    def _run(idx: int, fn_name: str, fn_args: dict):
        if fn_name == "__skip__":
            results[idx] = f"[SKIPPED] 사용자가 저장을 취소했습니다: {fn_args.get('path')}"
            states[idx]  = "done"
            return
        states[idx] = "running"
        starts[idx] = time.time()
        try:
            results[idx] = call_tool(fn_name, fn_args)
            # [ERROR]로 시작하는 결과도 오류로 처리
            if isinstance(results[idx], str) and results[idx].startswith("[ERROR]"):
                states[idx] = "error"
            else:
                states[idx] = "done"
        except Exception as exc:
            results[idx] = f"[ERROR] {exc}"
            states[idx]  = "error"

    spinners = [Spinner("dots") for _ in range(n)]

    with Live(console=console, refresh_per_second=12) as live:
        with ThreadPoolExecutor(max_workers=n) as pool:
            futures = [
                pool.submit(_run, i, fn_name, fn_args)
                for i, (fn_name, fn_args) in enumerate(parsed_calls)
            ]

            while any(s in ("pending", "running") for s in states):
                now = time.time()
                grid = Table.grid(padding=(0, 1))
                for i, (fn_name, fn_args) in enumerate(parsed_calls):
                    icon       = TOOL_ICONS.get(fn_name, "🔧")
                    arg_preview = str(list(fn_args.values())[0]) if fn_args else ""
                    state      = states[i]

                    if state == "pending":
                        status = Text("대기 중", style="dim")
                        spin   = Text("  ")
                    elif state == "running":
                        elapsed = int(now - starts[i]) if starts[i] else 0
                        status  = Text(f"{elapsed}s", style="bold yellow")
                        spin    = spinners[i].render(now)
                    elif state == "done":
                        status = Text("완료", style="bold green")
                        spin   = Text("✓ ", style="bold green")
                    else:
                        status = Text("오류", style="bold red")
                        spin   = Text("✗ ", style="bold red")

                    grid.add_row(
                        spin,
                        Text(f"{icon} {fn_name}", style="bold cyan"),
                        Text(arg_preview, style="dim"),
                        status,
                    )
                live.update(grid)
                time.sleep(0.08)

            # 최종 상태 한 번 더 출력 (모두 완료)
            now  = time.time()
            grid = Table.grid(padding=(0, 1))
            for i, (fn_name, fn_args) in enumerate(parsed_calls):
                icon        = TOOL_ICONS.get(fn_name, "🔧")
                arg_preview = str(list(fn_args.values())[0]) if fn_args else ""
                state       = states[i]
                status      = Text("완료", style="bold green") if state == "done" else Text("오류", style="bold red")
                spin        = Text("✓ ", style="bold green") if state == "done" else Text("✗ ", style="bold red")
                grid.add_row(spin, Text(f"{icon} {fn_name}", style="bold cyan"), Text(arg_preview, style="dim"), status)
            live.update(grid)

    # 오류 및 write 결과를 Live 종료 후 출력
    for i, (fn_name, fn_args) in enumerate(parsed_calls):
        result = results[i] or ""
        if states[i] == "error":
            console.print(f"  [bold red]✗ {fn_name}[/bold red] [dim]{list(fn_args.values())[0] if fn_args else ''}[/dim]")
            console.print(f"    [red]{result}[/red]")
        elif fn_name == "write_file":
            path = fn_args.get("path", "")
            console.print(f"  [bold green]✓ 저장됨:[/bold green] [cyan]{path}[/cyan]  [dim]{result}[/dim]")

    return results


_VALID_TOOLS = {"read_file", "write_file", "list_files", "search_code"}


def _extract_inline_tool_calls(content: str) -> list:
    """모델이 tool_calls API 대신 텍스트로 출력한 JSON tool call을 파싱한다.
    한 줄·멀티라인·코드블록 모두 처리한다."""
    results = []
    seen = set()
    decoder = json.JSONDecoder()

    i = 0
    while i < len(content):
        idx = content.find('{', i)
        if idx == -1:
            break
        try:
            obj, end = decoder.raw_decode(content, idx)
            i = end
            if not isinstance(obj, dict):
                continue

            name = obj.get("name")
            if not name and isinstance(obj.get("function"), dict):
                name = obj["function"].get("name")

            args = obj.get("arguments")
            if args is None and isinstance(obj.get("function"), dict):
                args = obj["function"].get("arguments")
            if args is None:
                args = {}

            if name not in _VALID_TOOLS:
                continue

            key = (name, json.dumps(args, sort_keys=True))
            if key in seen:
                continue
            seen.add(key)
            results.append({"function": {"name": name, "arguments": args}})
        except json.JSONDecodeError:
            i = idx + 1

    return results


MAX_HISTORY_TURNS = 20  # user+assistant 쌍 기준 최대 유지 턴 수


def run_agent(user_input: str, messages: list):
    """messages 리스트에 이번 턴을 이어붙이고 에이전트 루프를 실행한다."""
    messages.append({"role": "user", "content": user_input})

    step_history = []
    console.print()
    for step in range(MAX_STEPS):
        message = chat_with_spinner(messages, step + 1, step_history)
        messages.append(message)

        tool_calls = message.get("tool_calls") or []

        # 모델이 tool call을 텍스트로 출력한 경우 fallback 파싱
        if not tool_calls:
            tool_calls = _extract_inline_tool_calls(message.get("content", ""))
            if tool_calls:
                console.print("[dim yellow]⚠ 인라인 tool call 감지 — 자동 실행합니다[/dim yellow]")

        if not tool_calls:
            # 스트리밍으로 이미 출력됨 — 구분선만 표시
            console.print("─" * 60, style="dim green")
            return

        # 도구 파싱
        parsed_calls = []
        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            fn_args = tc["function"].get("arguments", {})
            if isinstance(fn_args, str):
                fn_args = json.loads(fn_args)
            parsed_calls.append((fn_name, fn_args))

        # 병렬 실행 + 라이브 상태 표시
        tool_results = run_tools_parallel(parsed_calls)

        for tool_result in tool_results:
            messages.append({"role": "tool", "content": tool_result})

    console.print(Panel(
        "[yellow]최대 스텝에 도달했습니다.[/yellow]",
        border_style="yellow"
    ))


def _trim_history(messages: list):
    """system 메시지는 유지하고, 오래된 대화 턴을 잘라 컨텍스트 초과를 방지한다."""
    system = [m for m in messages if m["role"] == "system"]
    turns  = [m for m in messages if m["role"] != "system"]

    # user+assistant 쌍 기준으로 최근 N턴만 유지
    if len(turns) > MAX_HISTORY_TURNS * 2:
        turns = turns[-(MAX_HISTORY_TURNS * 2):]

    messages[:] = system + turns


def select_project() -> str:
    """파일 브라우저처럼 탐색하며 프로젝트 루트를 선택한다."""
    import config as _cfg
    import questionary
    from questionary import Style

    style = Style([
        ("qmark",        "fg:#5f87ff bold"),
        ("question",     "bold"),
        ("answer",       "fg:#5fffff bold"),
        ("pointer",      "fg:#5f87ff bold"),
        ("highlighted",  "fg:#5fffff bold"),
        ("selected",     "fg:#5fffff"),
        ("separator",    "fg:#6c7086"),
        ("instruction",  "fg:#6c7086"),
    ])

    home    = os.path.expanduser("~")
    current = home

    while True:
        # 현재 경로를 ~ 형태로 표시
        display = current.replace(home, "~", 1)

        # 하위 폴더 수집
        try:
            subdirs = sorted([
                d for d in os.listdir(current)
                if os.path.isdir(os.path.join(current, d)) and not d.startswith(".")
            ])
        except PermissionError:
            subdirs = []

        subdir_choices = [
            questionary.Choice(f"📁  {d}/", value=("enter", os.path.join(current, d)))
            for d in subdirs
        ]

        # 상위 폴더로 이동 가능 여부
        parent = os.path.dirname(current)
        can_go_up = parent != current  # 루트(/)가 아닌 경우

        choices = [
            questionary.Choice(f"✅  여기로 선택  ({display})", value=("select", current)),
            questionary.Separator(f"── 📂 {display} ──"),
            *subdir_choices,
        ]
        if can_go_up:
            choices += [
                questionary.Separator("──────────────────"),
                questionary.Choice("⬆️  상위 폴더로", value=("up", parent)),
            ]
        choices += [
            questionary.Separator("──────────────────"),
            questionary.Choice("⌨️  직접 입력...", value=("custom", None)),
        ]

        result = questionary.select(
            f"프로젝트 폴더 선택",
            choices=choices,
            style=style,
            use_shortcuts=False,
        ).ask()

        if result is None:  # Ctrl+C
            console.print("\n[dim]종료합니다.[/dim]")
            sys.exit(0)

        action, value = result

        if action == "select":
            _cfg.PROJECT_ROOT = value
            return value
        elif action in ("enter", "up"):
            current = value
        elif action == "custom":
            raw = questionary.path(
                "경로 입력:",
                default=current,
                style=style,
            ).ask()
            if raw is None:
                continue
            path = os.path.abspath(raw.strip())
            if os.path.isdir(path):
                _cfg.PROJECT_ROOT = path
                return path
            else:
                console.print(f"[yellow]존재하지 않는 경로입니다.[/yellow]")


def select_model() -> str:
    """방향키 메뉴로 Ollama 모델을 선택한다."""
    import config as _cfg
    import questionary
    from questionary import Style

    style = Style([
        ("qmark",        "fg:#5f87ff bold"),
        ("question",     "bold"),
        ("answer",       "fg:#5fffff bold"),
        ("pointer",      "fg:#5f87ff bold"),
        ("highlighted",  "fg:#5fffff bold"),
        ("selected",     "fg:#5fffff"),
        ("instruction",  "fg:#6c7086"),
    ])

    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        console.print("[yellow]Ollama 모델 목록을 가져올 수 없습니다. 기본 모델을 사용합니다.[/yellow]")
        return _cfg.MODEL

    if not models:
        return _cfg.MODEL

    default = _cfg.MODEL if _cfg.MODEL in models else models[0]

    chosen = questionary.select(
        "사용할 모델 선택",
        choices=models,
        default=default,
        style=style,
    ).ask()

    if chosen is None:
        console.print("\n[dim]종료합니다.[/dim]")
        sys.exit(0)

    _cfg.MODEL = chosen
    return chosen


def main():
    chosen_model = select_model()
    chosen_project = select_project()

    console.print(Panel(
        "[bold white]로컬 코딩 에이전트[/bold white]\n"
        f"[dim]모델: {chosen_model}[/dim]\n"
        f"[dim]프로젝트: {chosen_project}[/dim]\n\n"
        "[dim]종료: [bold]exit[/bold] 또는 Ctrl+C[/dim]",
        border_style="bright_blue",
        box=box.DOUBLE_EDGE,
        expand=False,
    ))

    console.print("[dim]프로젝트 캐시 로딩 중...[/dim]")
    cache.load(verbose=True)
    console.print("[dim]💡 CLAUDE.md·클래스 인덱스는 이미 로드됨 — 바로 질문하세요[/dim]")

    # 대화 히스토리 초기화 (session 내내 유지)
    system_prompt = SYSTEM_PROMPT + "\n\n" + cache.build_index_summary()
    messages = [{"role": "system", "content": system_prompt}]

    while True:
        try:
            user_input = console.input("\n[bold bright_blue]요청 >[/bold bright_blue] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]종료합니다.[/dim]")
            sys.exit(0)

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "종료"):
            console.print("[dim]종료합니다.[/dim]")
            sys.exit(0)
        if user_input.lower() in ("clear", "초기화"):
            messages[:] = [{"role": "system", "content": system_prompt}]
            console.print("[dim]대화 히스토리를 초기화했습니다.[/dim]")
            continue

        _trim_history(messages)

        try:
            run_agent(user_input, messages)
        except requests.exceptions.ConnectionError:
            console.print(Panel(
                "[red]Ollama에 연결할 수 없습니다.[/red]\n[dim]ollama serve 실행 여부를 확인하세요.[/dim]",
                border_style="red"
            ))
        except Exception as e:
            console.print(f"[red][ERROR][/red] {e}")


if __name__ == "__main__":
    main()
