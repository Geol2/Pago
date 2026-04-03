"""
eXrep dWorks 개발 보조 에이전트
Ollama + qwen3.5 기반 tool-calling 루프
"""
import json
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
MAX_STEPS = 10
TIMEOUT   = 300

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
                },
                stream=True,
                timeout=(10, 180),
            )
            resp.raise_for_status()
            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                chunk = json.loads(raw_line)
                msg   = chunk.get("message", {})
                token = msg.get("content", "")
                if token:
                    token_q.put(token)
                if chunk.get("done"):
                    tool_calls.extend(msg.get("tool_calls") or [])
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
                        ("첫 응답 대기 중... ", "dim"),
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


def run_tools_parallel(parsed_calls: list) -> list:
    """도구를 병렬 실행하고 라이브로 진행상황 표시. 원래 순서대로 결과 반환."""
    n = len(parsed_calls)
    states  = ["pending"] * n   # pending | running | done | error
    results = [None] * n
    starts  = [None] * n

    def _run(idx: int, fn_name: str, fn_args: dict):
        states[idx] = "running"
        starts[idx] = time.time()
        try:
            results[idx] = call_tool(fn_name, fn_args)
            states[idx]  = "done"
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

    return results


def run_agent(user_input: str):
    claude_md = cache.get_file("CLAUDE.md") or ""
    system_prompt = (
        SYSTEM_PROMPT
        + "\n\n## CLAUDE.md (프로젝트 규칙 — 이미 로드됨)\n"
        + claude_md
        + "\n\n"
        + cache.build_index_summary()
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_input},
    ]

    step_history = []
    console.print()
    for step in range(MAX_STEPS):
        message = chat_with_spinner(messages, step + 1, step_history)
        messages.append(message)

        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            content = message.get("content", "").strip()
            console.print(Panel(
                Markdown(content),
                title="[bold green]답변[/bold green]",
                border_style="green",
                box=box.ROUNDED,
            ))
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


def main():
    console.print(Panel(
        "[bold white]eXrep dWorks 개발 보조 에이전트[/bold white]\n"
        "[dim]Powered by Ollama · qwen3.5[/dim]\n\n"
        "[dim]종료: [bold]exit[/bold] 또는 Ctrl+C[/dim]",
        border_style="bright_blue",
        box=box.DOUBLE_EDGE,
        expand=False,
    ))

    console.print("[dim]프로젝트 캐시 로딩 중...[/dim]")
    cache.load(verbose=True)
    console.print("[dim]💡 CLAUDE.md·클래스 인덱스는 이미 로드됨 — 바로 질문하세요[/dim]")

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

        try:
            run_agent(user_input)
        except requests.exceptions.ConnectionError:
            console.print(Panel(
                "[red]Ollama에 연결할 수 없습니다.[/red]\n[dim]ollama serve 실행 여부를 확인하세요.[/dim]",
                border_style="red"
            ))
        except Exception as e:
            console.print(f"[red][ERROR][/red] {e}")


if __name__ == "__main__":
    main()
