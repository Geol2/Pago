#!/usr/bin/env python3
"""
Claude Code 사용량 체커 (통합본)
  --tray     : 메뉴바(macOS) / 시스템 트레이(Windows) — 항상 표시 ★추천
  --desktop  : 접기/펴기 데스크탑 위젯
  --graph    : matplotlib 게이지 그래프
  (인수 없음): 터미널 텍스트 출력
"""

import subprocess
import json
import os
import sys
import time
import requests

if sys.platform == "win32":
    # --noconsole 빌드(.exe)에서는 stdout/stderr가 None — print() 호출 시 크래시 방지
    import io as _io
    if sys.stdout is None:
        sys.stdout = _io.StringIO()
    else:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr is None:
        sys.stderr = _io.StringIO()
    else:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from datetime import datetime
from typing import Optional, Dict, Any


# ──────────────────────────────────────────────
# 진단 로그 — 인증/요청 실패 원인 추적용
# ──────────────────────────────────────────────

_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "usage_checker.log")

def _log(msg: str):
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n")
    except Exception:
        pass


# ──────────────────────────────────────────────
# 사용량 체커 (API 통신)
# ──────────────────────────────────────────────

class ClaudeUsageChecker:
    API_URL     = "https://api.anthropic.com/api/oauth/usage"
    ACCOUNT_URL = "https://api.anthropic.com/api/oauth/account"
    KEYCHAIN_SERVICE = "Claude Code-credentials"
    KEY_LABELS = {
        "five_hour": "5시간 Rolling Window",
        "seven_day": "7일 주간 한도",
    }
    PLAN_LABELS = {
        "claude_pro":      "Claude Pro",
        "claude_max_5x":   "Claude Max (x5)",
        "claude_max_20x":  "Claude Max (x20)",
        "claude_free":     "Claude Free",
        "pro":             "Claude Pro",
        "max_5x":          "Claude Max (x5)",
        "max_20x":         "Claude Max (x20)",
        "free":            "Claude Free",
    }

    def __init__(self):
        self.token: Optional[str] = None
        self.usage_data: Optional[Dict[str, Any]] = None
        self.plan_name: Optional[str] = None

    def get_usage_sections(self) -> list:
        """API 응답에서 utilization 필드를 가진 모든 항목을 (key, data, label) 리스트로 반환."""
        if not self.usage_data:
            return []
        sections = []
        for key, data in self.usage_data.items():
            if isinstance(data, dict) and "utilization" in data:
                label = self.KEY_LABELS.get(key, key.replace("_", " ").title())
                sections.append((key, data, label))
        return sections

    def get_credentials_from_keychain(self) -> bool:
        if sys.platform == "win32":
            return self._get_credentials_windows()
        return self._get_credentials_macos()

    def _get_credentials_windows(self) -> bool:
        candidates = [
            os.path.join(os.path.expanduser("~"), ".claude", ".credentials.json"),
            os.path.join(os.path.expanduser("~"), ".claude", "credentials.json"),
            os.path.join(os.environ.get("APPDATA", ""), "Claude Code", "credentials.json"),
        ]
        for path in candidates:
            if os.path.exists(path):
                ok = self._parse_credentials_file(path)
                _log(f"_get_credentials_windows: {path} 로드 {'성공' if ok else '실패'}")
                return ok
        _log("_get_credentials_windows: 후보 경로 모두 없음 - " + " / ".join(candidates))
        print("인증 정보를 찾을 수 없습니다.")
        return False

    def _get_credentials_macos(self) -> bool:
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", self.KEYCHAIN_SERVICE, "-w"],
                capture_output=True, text=True, check=True
            )
            return self._parse_credentials_json(result.stdout.strip())
        except subprocess.CalledProcessError:
            print("Keychain에서 인증 정보를 찾을 수 없습니다.")
            return False
        except Exception as e:
            print(f"오류 발생: {e}")
            return False

    def _parse_credentials_file(self, path: str) -> bool:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return self._parse_credentials_json(f.read())
        except Exception as e:
            print(f"파일 읽기 실패 ({path}): {e}")
            return False

    def _parse_credentials_json(self, raw: str) -> bool:
        try:
            credentials = json.loads(raw)
            if "claudeAiOauth" in credentials:
                self.token = credentials["claudeAiOauth"]["accessToken"]
                return True
            return False
        except json.JSONDecodeError:
            return False

    def _auth_headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
            "anthropic-beta": "oauth-2025-04-20",
        }

    def _extract_plan(self, data: dict) -> Optional[str]:
        """응답 데이터에서 플랜 식별자를 찾아 표시 이름으로 반환."""
        for field in ("plan_type", "plan", "subscription_type", "tier", "subscription"):
            val = data.get(field)
            if isinstance(val, str) and val:
                return self.PLAN_LABELS.get(val.lower(), val)
            if isinstance(val, dict):
                inner = val.get("type") or val.get("plan_type") or val.get("name")
                if isinstance(inner, str) and inner:
                    return self.PLAN_LABELS.get(inner.lower(), inner)
        return None

    def fetch_usage(self) -> bool:
        # 콜드 스타트 시 자격이 아직 안 로드/만료된 경우를 위해 짧은 백오프 재시도
        for attempt in range(3):
            if not self.token:
                _log(f"fetch_usage: 토큰 없음 (시도 {attempt + 1}) — 자격 재로드")
                self.get_credentials_from_keychain()
                if not self.token:
                    time.sleep(2)
                    continue
            try:
                response = requests.get(self.API_URL, headers=self._auth_headers(), timeout=10)
                if response.status_code == 200:
                    self.usage_data = response.json()
                    self.plan_name = self._extract_plan(self.usage_data)
                    if not self.plan_name:
                        self._fetch_plan_from_account()
                    return True
                # 401: 토큰 만료 가능성 — 자격 재로드 후 즉시 재시도
                if response.status_code == 401 and attempt < 2:
                    _log(f"fetch_usage: 401 인증 실패 — 자격 재로드 후 재시도")
                    self.token = None
                    self.get_credentials_from_keychain()
                    time.sleep(1)
                    continue
                _log(f"fetch_usage: HTTP {response.status_code} body={response.text[:200]}")
                return False
            except requests.exceptions.RequestException as e:
                _log(f"fetch_usage: 네트워크 오류 (시도 {attempt + 1}): {e}")
                time.sleep(2)
        return False

    def _fetch_plan_from_account(self):
        """account 엔드포인트에서 플랜 정보를 보완 시도."""
        try:
            resp = requests.get(self.ACCOUNT_URL, headers=self._auth_headers(), timeout=10)
            if resp.status_code == 200:
                self.plan_name = self._extract_plan(resp.json())
        except requests.exceptions.RequestException:
            pass

    def format_reset_time(self, reset_time_str: Optional[str]) -> str:
        if not reset_time_str:
            return "정보 없음"
        try:
            reset_time = datetime.fromisoformat(reset_time_str.replace("Z", "+00:00"))
            now = datetime.now(reset_time.tzinfo)
            diff = reset_time - now
            if diff.total_seconds() < 0:
                return "리셋 완료"
            h = int(diff.total_seconds() // 3600)
            m = int((diff.total_seconds() % 3600) // 60)
            return f"{h}시간 {m}분 후" if h > 0 else f"{m}분 후"
        except Exception:
            return reset_time_str

    def print_usage(self):
        sections = self.get_usage_sections()
        if not sections:
            print("사용량 데이터가 없습니다.")
            return
        print("\n" + "=" * 60)
        plan_str = f"  [{self.plan_name}]" if self.plan_name else ""
        print(f"Claude Code 사용량 현황{plan_str}")
        print("=" * 60)
        for key, d, label in sections:
            u = d.get("utilization") or 0
            bar = "█" * min(40, int(40 * u / 100)) + "░" * max(0, 40 - int(40 * u / 100))
            over = " (초과)" if u > 100 else ""
            print(f"\n{label}")
            print(f"  {u:.1f}%{over}")
            print(f"  [{bar}]")
            print(f"  리셋: {self.format_reset_time(d.get('resets_at'))}")
        print("\n" + "=" * 60)

    def run(self):
        print("\nClaude Code 사용량 체커")
        print("-" * 60)
        if not self.get_credentials_from_keychain():
            return
        print("사용량 정보를 가져오는 중...")
        if not self.fetch_usage():
            print("API 호출 실패")
            return
        self.print_usage()


# ──────────────────────────────────────────────
# 데스크탑 위젯 (접기/펴기)
# ──────────────────────────────────────────────

def run_desktop_widget(checker: ClaudeUsageChecker):
    import tkinter as tk

    REFRESH_MS = 60_000
    TICK_MS    = 1_000

    BG     = "#1e1e2e"
    FG     = "#cdd6f4"
    GREEN  = "#a6e3a1"
    YELLOW = "#f9e2af"
    RED    = "#f38ba8"
    GRAY   = "#6c7086"
    PANEL  = "#313244"

    root = tk.Tk()
    root.title("Claude 사용량")
    root.configure(bg=BG)
    root.attributes("-topmost", True)
    root.resizable(False, False)

    expanded = tk.BooleanVar(value=True)

    # ── 드래그 이동 ──
    def on_drag_start(e):
        root._drag_x, root._drag_y = e.x, e.y
    def on_drag_move(e):
        dx, dy = e.x - root._drag_x, e.y - root._drag_y
        root.geometry(f"+{root.winfo_x()+dx}+{root.winfo_y()+dy}")
    root.bind("<ButtonPress-1>", on_drag_start)
    root.bind("<B1-Motion>", on_drag_move)

    # ── 헬퍼 ──
    def make_bar(pct: float, width: int = 26) -> str:
        filled = min(width, int(width * pct / 100))
        return "█" * filled + "░" * (width - filled)

    def pct_color(pct: float) -> str:
        if pct > 100: return RED
        if pct > 80:  return YELLOW
        return GREEN

    # ────────────────────────────────
    # 헤더 (항상 표시)
    # ────────────────────────────────
    header = tk.Frame(root, bg=BG)
    header.pack(fill="x", padx=8, pady=(6, 2))

    lbl_title = tk.Label(header, text="Claude Code", bg=BG, fg=FG,
                         font=("Segoe UI", 10, "bold"))
    lbl_title.pack(side="left")

    lbl_plan = tk.Label(header, text="", bg=BG, fg=GRAY,
                        font=("Segoe UI", 8))
    lbl_plan.pack(side="left", padx=(6, 0))

    # 접힌 상태 미니 수치
    lbl_mini = tk.Label(header, text="", bg=BG, fg=GREEN,
                        font=("Consolas", 9))
    lbl_mini.pack(side="left", padx=(8, 0))

    btn_toggle = tk.Label(header, text="▲", bg=BG, fg=GRAY,
                          font=("Segoe UI", 9), cursor="hand2")
    btn_toggle.pack(side="right")

    btn_refresh = tk.Label(header, text="↺", bg=BG, fg=GRAY,
                           font=("Segoe UI", 11), cursor="hand2")
    btn_refresh.pack(side="right", padx=(0, 6))

    tk.Frame(root, bg=GRAY, height=1).pack(fill="x", padx=8)

    # ────────────────────────────────
    # 펼쳐진 패널
    # ────────────────────────────────
    panel = tk.Frame(root, bg=BG)
    panel.pack(fill="x")

    def make_section(parent, title):
        tk.Label(parent, text=title, bg=BG, fg=FG,
                 font=("Segoe UI", 9), anchor="w").pack(fill="x", padx=14, pady=(8, 0))
        pct_lbl = tk.Label(parent, bg=BG, fg=GREEN, font=("Consolas", 9), anchor="w")
        pct_lbl.pack(fill="x", padx=14)
        bar_lbl = tk.Label(parent, bg=BG, fg=GREEN, font=("Consolas", 9), anchor="w")
        bar_lbl.pack(fill="x", padx=14)
        rst_lbl = tk.Label(parent, bg=BG, fg=GRAY, font=("Segoe UI", 8), anchor="w")
        rst_lbl.pack(fill="x", padx=14, pady=(0, 6))
        return pct_lbl, bar_lbl, rst_lbl

    sections_frame = tk.Frame(panel, bg=BG)
    sections_frame.pack(fill="x")

    lbl_updated = tk.Label(panel, bg=BG, fg=GRAY, font=("Segoe UI", 7), anchor="e")
    lbl_updated.pack(fill="x", padx=10, pady=4)

    _section_labels: dict = {}   # key -> (pct_lbl, bar_lbl, rst_lbl)
    _sections_built = [False]

    def build_sections():
        for w in sections_frame.winfo_children():
            w.destroy()
        _section_labels.clear()
        sections = checker.get_usage_sections()
        for i, (key, d, label) in enumerate(sections):
            if i > 0:
                tk.Frame(sections_frame, bg=GRAY, height=1).pack(fill="x", padx=8)
            lbls = make_section(sections_frame, label)
            _section_labels[key] = lbls
        if sections:
            tk.Frame(sections_frame, bg=GRAY, height=1).pack(fill="x", padx=8)
        _sections_built[0] = True

    # ── 접기/펴기 ──
    def toggle(_event=None):
        if expanded.get():
            panel.pack_forget()
            btn_toggle.config(text="▼")
            expanded.set(False)
        else:
            panel.pack(fill="x")
            btn_toggle.config(text="▲")
            expanded.set(True)

    btn_toggle.bind("<Button-1>", toggle)

    def refresh_now(_event=None):
        btn_refresh.config(text="…", fg=FG)
        import threading
        def _call():
            if not checker.token:
                checker.get_credentials_from_keychain()
            checker.fetch_usage()
            if not _sections_built[0]:
                root.after(0, build_sections)
            root.after(0, lambda: btn_refresh.config(text="↺", fg=GRAY))
        threading.Thread(target=_call, daemon=True).start()

    btn_refresh.bind("<Button-1>", refresh_now)

    # ── API fetch (백그라운드) ──
    def fetch_api():
        import threading
        def _call():
            if not checker.token:
                checker.get_credentials_from_keychain()
            checker.fetch_usage()
            if not _sections_built[0]:
                root.after(0, build_sections)
        threading.Thread(target=_call, daemon=True).start()
        root.after(REFRESH_MS, fetch_api)

    # ── 화면 갱신 (1초마다) ──
    def tick():
        if checker.usage_data and _sections_built[0]:
            if checker.plan_name:
                lbl_plan.config(text=f"({checker.plan_name})")
            sections = checker.get_usage_sections()
            pcts = [d.get("utilization") or 0 for _, d, _ in sections]
            if pcts:
                lbl_mini.config(
                    text="  ".join(f"{label.split()[0]} {u:.0f}%" for _, d, label in sections
                                   for u in [d.get("utilization") or 0]),
                    fg=pct_color(max(pcts))
                )
            for key, d, label in sections:
                if key not in _section_labels:
                    continue
                u = d.get("utilization") or 0
                pct_lbl, bar_lbl, rst_lbl = _section_labels[key]
                pct_lbl.config(text=f"  {u:.1f}%{'  초과' if u > 100 else ''}", fg=pct_color(u))
                bar_lbl.config(text=f"  [{make_bar(u)}]", fg=pct_color(u))
                rst_lbl.config(text=f"  리셋: {checker.format_reset_time(d.get('resets_at'))}")

        lbl_updated.config(text=f"갱신: {datetime.now().strftime('%H:%M:%S')}  ")
        root.after(TICK_MS, tick)

    fetch_api()
    tick()
    try:
        root.mainloop()
    except KeyboardInterrupt:
        root.destroy()


# ──────────────────────────────────────────────
# matplotlib 게이지 그래프
# ──────────────────────────────────────────────

def run_graph(checker: ClaudeUsageChecker):
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np
    import threading

    if sys.platform == "win32":
        plt.rcParams["font.family"] = "Malgun Gothic"
    elif sys.platform == "darwin":
        plt.rcParams["font.family"] = "AppleGothic"
    else:
        plt.rcParams["font.family"] = "NanumGothic"
    plt.rcParams["axes.unicode_minus"] = False

    def gauge_color(pct):
        if pct > 80: return "#f38ba8"
        if pct > 50: return "#f9e2af"
        return "#a6e3a1"

    def get_next_reset_time(data: dict) -> Optional[datetime]:
        """데이터에서 가장 가까운 리셋 시각을 반환."""
        times = []
        for d in data.values():
            if not isinstance(d, dict):
                continue
            rs = d.get("resets_at")
            if rs:
                try:
                    times.append(datetime.fromisoformat(rs.replace("Z", "+00:00")))
                except Exception:
                    pass
        return min(times) if times else None

    def draw_gauge(ax, pct, title, reset_label):
        pct_capped = min(pct, 100)
        color = gauge_color(pct)
        theta = np.linspace(np.pi, 0, 200)
        ax.plot(np.cos(theta), np.sin(theta), lw=18, color="#313244", solid_capstyle="round")
        ft = np.linspace(np.pi, np.pi - np.pi * (pct_capped / 100), 200)
        ax.plot(np.cos(ft), np.sin(ft), lw=18, color=color, solid_capstyle="round")
        ax.set_xlim(-1.3, 1.3); ax.set_ylim(-0.3, 1.2)
        ax.set_aspect("equal"); ax.axis("off")
        ax.text(0, 0.22, f"{pct:.1f}%", ha="center", va="center",
                fontsize=22, fontweight="bold", color=color)
        ax.text(0, -0.05, title, ha="center", va="center", fontsize=11, color="#cdd6f4")
        ax.text(0, -0.22, reset_label, ha="center", va="center", fontsize=8, color="#6c7086")

    def draw_bar(ax, sections):
        labels = [label for _, _, label in sections]
        values = [min(d.get("utilization") or 0, 100) for _, d, _ in sections]
        colors = [gauge_color(v) for v in values]
        ax.set_facecolor("#1e1e2e")
        bars = ax.barh(labels, values, color=colors, height=0.45)
        ax.axvline(x=100, color="#6c7086", lw=1.2, linestyle="--", alpha=0.7)
        ax.axvline(x=80,  color="#f9e2af", lw=0.8, linestyle=":",  alpha=0.5)
        for bar, val in zip(bars, values):
            ax.text(val + 1, bar.get_y() + bar.get_height() / 2,
                    f"{val:.1f}%", va="center", fontsize=10,
                    color="#cdd6f4", fontweight="bold")
        ax.set_xlim(0, 115)
        ax.set_xlabel("사용률 (%)", color="#cdd6f4", fontsize=9)
        ax.tick_params(colors="#cdd6f4", labelsize=9)
        ax.spines[:].set_color("#313244")
        ax.text(80,  -0.6, "80%\n경고", ha="center", fontsize=7, color="#f9e2af", alpha=0.8)
        ax.text(100, -0.6, "100%\n한도", ha="center", fontsize=7, color="#6c7086", alpha=0.8)

    def draw_all(fig):
        fig.clear()
        sections = checker.get_usage_sections()

        fig.patch.set_facecolor("#1e1e2e")
        plan_str = f"  [{checker.plan_name}]" if checker.plan_name else ""
        fig.suptitle(f"Claude Code 사용량 현황{plan_str}", color="#cdd6f4",
                     fontsize=15, fontweight="bold", y=0.97)
        fig.text(0.99, 0.01, f"갱신: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                 ha="right", va="bottom", color="#6c7086", fontsize=7)
        fig.text(0.01, 0.01, "R: 새로고침", ha="left", va="bottom",
                 color="#6c7086", fontsize=7)

        if not sections:
            ax = fig.add_axes([0.1, 0.1, 0.8, 0.8])
            ax.text(0.5, 0.5, "데이터 없음", ha="center", va="center",
                    transform=ax.transAxes, color="#cdd6f4", fontsize=14)
            ax.axis("off")
            fig.canvas.draw_idle()
            return

        n = len(sections)
        gauge_h = 0.52
        gauge_y = 0.38
        gauge_w = min(0.44, 0.90 / n)
        spacing = (0.90 - n * gauge_w) / max(n - 1, 1) if n > 1 else 0
        start_x = (1.0 - (n * gauge_w + (n - 1) * spacing)) / 2

        for i, (key, d, label) in enumerate(sections):
            u = d.get("utilization") or 0
            r_label = "리셋: " + checker.format_reset_time(d.get("resets_at"))
            x = start_x + i * (gauge_w + spacing)
            ax = fig.add_axes([x, gauge_y, gauge_w, gauge_h])
            draw_gauge(ax, u, label, r_label)

        bar_h = max(0.08 + 0.06 * n, 0.26)
        ax_bar = fig.add_axes([0.08, 0.06, 0.84, bar_h])
        draw_bar(ax_bar, sections)

        legend_elements = [
            mpatches.Patch(color="#a6e3a1", label="정상 (0~50%)"),
            mpatches.Patch(color="#f9e2af", label="주의 (50~80%)"),
            mpatches.Patch(color="#f38ba8", label="경고 (80%+)"),
        ]
        fig.legend(handles=legend_elements, loc="lower right",
                   bbox_to_anchor=(0.99, 0.36), fontsize=8,
                   facecolor="#313244", edgecolor="#6c7086",
                   labelcolor="#cdd6f4", framealpha=0.9)
        fig.canvas.draw_idle()

    fig = plt.figure(figsize=(10, 5.5), facecolor="#1e1e2e")
    draw_all(fig)

    # ── 리셋 감지 타이머 ──
    _fetching = threading.Event()

    def check_reset():
        if not plt.fignum_exists(fig.number):
            return
        data = checker.usage_data or {}
        next_reset = get_next_reset_time(data)
        if next_reset:
            now = datetime.now(next_reset.tzinfo)
            if now >= next_reset and not _fetching.is_set():
                _fetching.set()
                def _fetch_and_redraw():
                    checker.fetch_usage()
                    _fetching.clear()
                    # matplotlib은 메인 스레드에서만 그릴 수 있으므로 타이머로 위임
                    timer_redraw.start()
                threading.Thread(target=_fetch_and_redraw, daemon=True).start()

        timer_check.start()

    def do_redraw():
        if plt.fignum_exists(fig.number):
            draw_all(fig)

    # 1초마다 리셋 여부 체크, 리셋 후 즉시 재그리기용 원샷 타이머
    timer_check  = fig.canvas.new_timer(interval=1000)
    timer_check.add_callback(check_reset)
    timer_check.single_shot = True

    timer_redraw = fig.canvas.new_timer(interval=100)
    timer_redraw.add_callback(do_redraw)
    timer_redraw.single_shot = True

    def on_key(event):
        if event.key in ('r', 'R') and not _fetching.is_set():
            _fetching.set()
            def _fetch():
                checker.fetch_usage()
                _fetching.clear()
                timer_redraw.start()
            threading.Thread(target=_fetch, daemon=True).start()

    fig.canvas.mpl_connect('key_press_event', on_key)
    timer_check.start()
    plt.show()


# ──────────────────────────────────────────────
# 트레이 / 메뉴바 (macOS + Windows 공용)
# ──────────────────────────────────────────────

_TRAY_SHORT_LABELS: dict[str, str] = {
    "5시간 Rolling Window": "5시간 창",
    "7일 주간 한도":        "7일 한도",
    "Seven Day Sonnet":    "7일 Sonnet",
    "Seven Day Omelette":  "7일 Omelette",
    "Extra Usage":         "추가 사용량",
}


def _short_label(label: str) -> str:
    return _TRAY_SHORT_LABELS.get(label, label)


def _pct_bar(pct: float, width: int = 12) -> str:
    filled = min(width, round(width * min(pct, 100) / 100))
    return "█" * filled + "░" * (width - filled)


def _flag(pct: float) -> str:
    return "🔴" if pct > 80 else "🟡" if pct > 50 else "🟢"


def _tray_color(pct: float) -> tuple:
    """사용률에 따른 RGB 색상."""
    if pct > 80: return (243, 139, 168)   # 빨강
    if pct > 50: return (249, 226, 175)   # 노랑
    return (166, 227, 161)                # 초록


# ──────────────────────────────────────────────
# 에이전트(Claude Code) 작업 상태 — 훅이 ~/.claude/agent_state.json 에 기록
# ──────────────────────────────────────────────

_AGENT_STATE_FILE = os.path.join(os.path.expanduser("~"), ".claude", "agent_state.json")

# 세션 종료 감지: idle 상태로 이만큼 지나면 사라진 것으로 간주 (PID 모르는 경우의 폴백)
_ORPHAN_IDLE_SECONDS = 60


def _is_pid_alive(pid) -> bool:
    """프로세스 존재 확인. pid 가 None/잘못된 값이면 True (살아있다 가정)."""
    if not pid:
        return True
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return True
    if sys.platform == "win32":
        # Windows: os.kill(pid, 0) 은 TerminateProcess 를 호출해 위험.
        # OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION) 로 존재만 확인.
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                # ERROR_INVALID_PARAMETER(87) = PID 없음, ERROR_ACCESS_DENIED(5) = 존재함
                return kernel32.GetLastError() == 5
            try:
                exit_code = ctypes.c_ulong()
                if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    STILL_ACTIVE = 259
                    return exit_code.value == STILL_ACTIVE
                return True
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return True
    try:
        os.kill(pid, 0)  # POSIX: signal 0 = 권한 체크만, 프로세스 안 죽임
        return True
    except OSError:
        return False
    except Exception:
        return True

# 우선순위: 여러 세션이 있으면 가장 "활동 중"인 상태를 채택.
_STATE_PRIORITY = {"waiting": 3, "working": 2, "done": 1, "idle": 0, "unknown": 0}

# done(만세) 표시 지속 시간 — 이후 자동으로 idle 로 강등
_DONE_DISPLAY_SECONDS = 5

_STATE_LABELS_KO = {
    "working": "🔨 오크 열일 중",
    "waiting": "❓ 컨펌 대기 중",
    "done":    "✅ Jobs done!",
    "idle":    "💤 대기",
}


def _load_agent_state() -> dict:
    """훅이 남긴 상태 파일을 읽어 (잘못된 경우 빈 dict)."""
    try:
        if not os.path.exists(_AGENT_STATE_FILE):
            return {}
        with open(_AGENT_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}


def _aggregate_agent_state(max_idle_seconds: int = 600, min_event_at=None) -> dict:
    """
    여러 세션의 상태를 단일 표시용 dict 로 집계.
    반환: {state, sessions: [{state, tool, cwd, updated_at, age_seconds}], updated_at}
    max_idle_seconds 초 이상 갱신 없으면 'idle'로 강등.
    min_event_at(datetime)가 주어지면 그 시각 이전의 이벤트는 idle 로 간주
    — 위젯 시작 전에 남은 이전 세션 흔적을 무시하기 위함.
    """
    data = _load_agent_state()
    sessions = data.get("sessions") or {}
    now = datetime.now()

    rendered = []
    best_state = "idle"
    best_priority = -1
    latest_ts = None

    for sid, info in sessions.items():
        if not isinstance(info, dict):
            continue
        try:
            ts = datetime.fromisoformat(info.get("updated_at", ""))
        except Exception:
            continue
        age = (now - ts).total_seconds()
        raw_state = info.get("state") or "unknown"
        # 'done'(만세)은 짧게만 보여주고 곧바로 idle 로 강등 — 사용자 요청
        # 그 외 상태는 max_idle_seconds 동안 유지
        state = raw_state
        # 위젯 시작 전에 일어난 이벤트는 모두 idle 로 처리 (오래된 세션 흔적 무시)
        if min_event_at is not None and ts < min_event_at:
            state = "idle"
        elif raw_state == "done" and age > _DONE_DISPLAY_SECONDS:
            state = "idle"
        elif age > max_idle_seconds:
            state = "idle"

        rendered.append({
            "session_id": sid,
            "state": state,
            "raw_state": raw_state,
            "tool": info.get("tool") or "",
            "cwd": info.get("cwd") or "",
            "updated_at": info.get("updated_at") or "",
            "age_seconds": int(age),
            "claude_pid": info.get("claude_pid"),
        })
        prio = _STATE_PRIORITY.get(state, 0)
        if prio > best_priority:
            best_priority = prio
            best_state = state
        if latest_ts is None or ts > latest_ts:
            latest_ts = ts

    # 최근 활동순 정렬
    rendered.sort(key=lambda s: s["age_seconds"])
    return {
        "state": best_state,
        "sessions": rendered,
        "updated_at": latest_ts.isoformat(timespec="seconds") if latest_ts else None,
    }


def _agent_badge_color(state: str) -> tuple:
    """배지 RGB."""
    if state == "working": return (250, 179, 135)  # 주황 — 열일
    if state == "waiting": return (249, 226, 175)  # 노랑 — 대기
    if state == "done":    return (166, 227, 161)  # 초록 — 완료
    return (108, 112, 134)                          # 회색 — idle


def _draw_state_badge(img, state: str):
    """기존 게이지 아이콘 우상단에 작은 상태 배지 그리기."""
    from PIL import ImageDraw
    if state in (None, "idle", "unknown"):
        return
    draw = ImageDraw.Draw(img)
    # 우상단 22x22 배지
    s = 24
    pad = 2
    x0, y0 = 64 - s - pad, pad
    x1, y1 = 64 - pad, s + pad
    bg = _agent_badge_color(state) + (255,)
    fg = (30, 30, 46, 255)
    draw.ellipse([x0, y0, x1, y1], fill=bg, outline=fg, width=2)

    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    if state == "working":
        # 망치 — 자루 + 머리
        draw.line([cx - 4, cy + 6, cx + 4, cy - 4], fill=fg, width=2)
        draw.rectangle([cx + 1, cy - 7, cx + 7, cy - 2], fill=fg)
    elif state == "waiting":
        # ? — 호 + 점
        draw.arc([cx - 5, cy - 7, cx + 5, cy + 1], start=200, end=340, fill=fg, width=2)
        draw.line([cx, cy + 1, cx, cy + 4], fill=fg, width=2)
        draw.ellipse([cx - 1, cy + 5, cx + 1, cy + 7], fill=fg)
    elif state == "done":
        # ✓ — 두 선분
        draw.line([cx - 5, cy + 1, cx - 1, cy + 5], fill=fg, width=2)
        draw.line([cx - 1, cy + 5, cx + 6, cy - 4], fill=fg, width=2)


def _make_pil_icon(pct_max: float = 0, agent_state: str = "idle"):
    """pystray용 PIL 아이콘 — 어두운 원 위에 게이지 호 + 우상단 작업 상태 배지."""
    from PIL import Image, ImageDraw
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, 62, 62], fill=(30, 30, 46, 255))
    if pct_max > 0:
        color = _tray_color(pct_max) + (255,)
        end_angle = -90 + 360 * min(pct_max, 100) / 100
        draw.arc([8, 8, 56, 56], start=-90, end=end_angle, fill=color, width=10)
    _draw_state_badge(img, agent_state)
    return img


def _agent_state_lines(agent: dict) -> list[str]:
    """툴팁/메뉴용 사람-가독 표현."""
    lines = []
    label = _STATE_LABELS_KO.get(agent.get("state", "idle"), "💤 대기")
    lines.append(label)
    sessions = agent.get("sessions") or []
    if not sessions:
        return lines
    # 활성 세션이 여럿이면 최대 3개만 보여줌
    for s in sessions[:3]:
        st = s.get("state", "")
        sub_label = _STATE_LABELS_KO.get(st, st)
        proj = os.path.basename(s.get("cwd") or "") or "(?)"
        tool = s.get("tool") or ""
        suffix = f" · {tool}" if tool and st in ("working",) else ""
        lines.append(f"  · {proj}{suffix}  [{sub_label}]")
    if len(sessions) > 3:
        lines.append(f"  · 외 {len(sessions) - 3}개 세션")
    return lines


def run_tray(checker: ClaudeUsageChecker):
    if sys.platform == "darwin":
        _run_tray_macos(checker)
    else:
        _run_tray_windows(checker)


def _run_tray_macos(checker: ClaudeUsageChecker):
    try:
        import rumps
    except ImportError:
        print("rumps 미설치: pip install rumps")
        sys.exit(1)

    import threading
    import plistlib
    import subprocess
    from pathlib import Path

    REFRESH_SEC = 60

    # ── 시작 시 자동 실행 (LaunchAgent plist 방식) ──
    _PLIST_LABEL = "com.claude.usage"
    _PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{_PLIST_LABEL}.plist"
    _PY_SCRIPT = str(Path(__file__).resolve())

    def _is_autostart_enabled() -> bool:
        return _PLIST_PATH.exists()

    def _set_autostart(enabled: bool):
        if enabled:
            _PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "Label": _PLIST_LABEL,
                "ProgramArguments": [sys.executable, _PY_SCRIPT, "--tray"],
                "RunAtLoad": True,
                "KeepAlive": False,
            }
            with open(_PLIST_PATH, "wb") as f:
                plistlib.dump(data, f)
            subprocess.run(["launchctl", "load", str(_PLIST_PATH)], check=False)
        else:
            if _PLIST_PATH.exists():
                subprocess.run(["launchctl", "unload", str(_PLIST_PATH)], check=False)
                try:
                    _PLIST_PATH.unlink()
                except Exception:
                    pass

    def _on_toggle_autostart(item):
        new_state = item.state != 1
        _set_autostart(new_state)
        item.state = 1 if new_state else 0

    def _build_menu(fetch_cb):
        items = []
        sections = checker.get_usage_sections()

        # 에이전트 작업 상태
        agent = _aggregate_agent_state()
        for line in _agent_state_lines(agent):
            items.append(rumps.MenuItem(line))
        items.append(None)

        # 헤더: 플랜명
        if checker.plan_name:
            items.append(rumps.MenuItem(f"  {checker.plan_name}"))
            items.append(None)

        if sections:
            for _, d, label in sections:
                u    = d.get("utilization") or 0
                rst  = checker.format_reset_time(d.get("resets_at"))
                over = " 초과!" if u > 100 else ""
                items.append(rumps.MenuItem(
                    f"  {_flag(u)}  {_short_label(label)}   {_pct_bar(u)}  {u:.1f}%{over}"))
                items.append(rumps.MenuItem(f"       리셋까지  {rst}"))
                items.append(None)
        else:
            items.append(rumps.MenuItem("  데이터 없음"))
            items.append(None)

        items.append(rumps.MenuItem("  ↺  새로고침", callback=fetch_cb))

        auto_item = rumps.MenuItem("  시작 시 자동 실행", callback=_on_toggle_autostart)
        auto_item.state = 1 if _is_autostart_enabled() else 0
        items.append(auto_item)

        items.append(None)
        items.append(rumps.MenuItem("  종료", callback=rumps.quit_application))
        return items

    _STATE_PREFIX_KO = {
        "working": "🔨",
        "waiting": "❓",
        "done":    "✅",
        "idle":    "☁",
    }

    class UsageMenuBar(rumps.App):
        def __init__(self):
            super().__init__("☁ ...", quit_button=None)
            self.menu = [rumps.MenuItem("로딩 중..."), None,
                         rumps.MenuItem("종료", callback=rumps.quit_application)]
            threading.Thread(target=self._fetch, daemon=True).start()
            rumps.Timer(self._auto_refresh, REFRESH_SEC).start()
            # 에이전트 상태는 더 자주 갱신 (2초)
            rumps.Timer(self._refresh_state, 2).start()

        def _auto_refresh(self, _):
            threading.Thread(target=self._fetch, daemon=True).start()

        def _refresh_state(self, _):
            # 사용량 API 호출 없이 상태 파일만 읽어 메뉴/타이틀 갱신
            self._update()

        def _fetch(self):
            if not checker.token:
                checker.get_credentials_from_keychain()
            checker.fetch_usage()
            # AppKit 객체는 반드시 메인 스레드에서 수정해야 함.
            # rumps.Timer(interval=0) 은 다음 런루프 틱에 메인 스레드에서 콜백을 실행한다.
            t = rumps.Timer(lambda sender: (self._update(), sender.stop()), 0)
            t.start()

        def _update(self):
            sections = checker.get_usage_sections()
            # 제목은 five_hour / seven_day 두 핵심 항목만 표시
            priority = {"five_hour", "seven_day"}
            title_pcts = [d.get("utilization") or 0 for k, d, _ in sections if k in priority]
            if not title_pcts:
                title_pcts = [d.get("utilization") or 0 for _, d, _ in sections]
            agent_state = _aggregate_agent_state().get("state", "idle")
            prefix = _STATE_PREFIX_KO.get(agent_state, "☁")
            self.title = (f"{prefix} " + " | ".join(f"{int(p)}%" for p in title_pcts)) if title_pcts else f"{prefix} --"
            # clear() 없이 대입하면 rumps 내부 dict에 누적되므로 반드시 먼저 지움
            self.menu.clear()
            self.menu = _build_menu(
                lambda _: threading.Thread(target=self._fetch, daemon=True).start()
            )

    UsageMenuBar().run()


def _run_tray_windows(checker: ClaudeUsageChecker):
    try:
        import pystray
    except ImportError:
        print("pystray 미설치: pip install pystray pillow")
        sys.exit(1)
    try:
        from PIL import Image  # noqa: F401 — import check only
    except ImportError:
        print("Pillow 미설치: pip install pillow")
        sys.exit(1)

    # 작업표시줄에 'python' 대신 'AI 사용량'으로 표시되도록 콘솔 창 제목 변경
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW("AI 사용량")
    except Exception:
        pass

    import threading
    import os
    import subprocess
    from pathlib import Path

    _stop = threading.Event()
    _icon_holder: list = [None]

    # ── 시작 시 자동 실행 (시작 폴더 단축키 방식) ──
    _STARTUP_DIR = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    _SHORTCUT_PATH = _STARTUP_DIR / "AI 사용량.lnk"

    # PyInstaller로 패키징된 경우 sys.frozen=True — .exe 자체를 직접 가리킨다.
    # 개발 환경에서는 기존대로 Claude사용량.vbs(파이썬 호출 래퍼)를 사용.
    if getattr(sys, "frozen", False):
        _AUTOSTART_TARGET = Path(sys.executable).resolve()
        _AUTOSTART_ARGS = "--tray"
    else:
        _AUTOSTART_TARGET = Path(__file__).resolve().parent / "Claude사용량.vbs"
        _AUTOSTART_ARGS = ""

    def _is_autostart_enabled() -> bool:
        return _SHORTCUT_PATH.exists()

    def _set_autostart(enabled: bool):
        if enabled:
            if not _AUTOSTART_TARGET.exists():
                return
            _STARTUP_DIR.mkdir(parents=True, exist_ok=True)
            ps = (
                f'$s=(New-Object -ComObject WScript.Shell).CreateShortcut("{_SHORTCUT_PATH}"); '
                f'$s.TargetPath="{_AUTOSTART_TARGET}"; '
                f'$s.Arguments="{_AUTOSTART_ARGS}"; '
                f'$s.WorkingDirectory="{_AUTOSTART_TARGET.parent}"; '
                f'$s.WindowStyle=7; '
                f'$s.Description="Claude 사용량 트레이"; '
                f'$s.Save()'
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
        else:
            try:
                _SHORTCUT_PATH.unlink(missing_ok=True)
            except Exception:
                pass

    def _on_toggle_autostart(icon, item):
        _set_autostart(not _is_autostart_enabled())
        icon.update_menu()

    def _tooltip() -> str:
        # Windows 트레이 툴팁은 최대 128자 제한 — compact 포맷 + 안전 컷
        agent = _aggregate_agent_state()
        sections = checker.get_usage_sections()
        lines = []
        # 에이전트 상태가 있으면 첫 줄에 표시 (가장 눈에 띄도록)
        agent_line = _STATE_LABELS_KO.get(agent.get("state", "idle"))
        if agent_line:
            lines.append(agent_line)
        if sections:
            header = f"Claude {checker.plan_name or ''}".strip()
            lines.append(header)
            for _, d, label in sections:
                u = d.get("utilization") or 0
                lines.append(f"{_flag(u)} {_short_label(label)} {u:.1f}%")
        elif not lines:
            lines.append("Claude Code 사용량")
        text = "\n".join(lines)
        if len(text) > 127:
            text = text[:124] + "..."
        return text

    def _make_menu():
        items = []
        sections = checker.get_usage_sections()

        # ── 에이전트 작업 상태 섹션 ──
        agent = _aggregate_agent_state()
        for line in _agent_state_lines(agent):
            items.append(pystray.MenuItem(line, None, enabled=False))
        items.append(pystray.Menu.SEPARATOR)

        if checker.plan_name:
            items.append(pystray.MenuItem(f"  {checker.plan_name}", None, enabled=False))
            items.append(pystray.Menu.SEPARATOR)

        if sections:
            for _, d, label in sections:
                u    = d.get("utilization") or 0
                rst  = checker.format_reset_time(d.get("resets_at"))
                over = " 초과!" if u > 100 else ""
                items.append(pystray.MenuItem(
                    f"  {_flag(u)}  {_short_label(label)}   {_pct_bar(u)}  {u:.1f}%{over}",
                    None, enabled=False))
                items.append(pystray.MenuItem(
                    f"       리셋까지  {rst}", None, enabled=False))
                items.append(pystray.Menu.SEPARATOR)
        else:
            items.append(pystray.MenuItem("  데이터 없음", None, enabled=False))
            items.append(pystray.Menu.SEPARATOR)

        items.append(pystray.MenuItem("  ↺  새로고침", _on_refresh))
        items.append(pystray.MenuItem(
            "  시작 시 자동 실행",
            _on_toggle_autostart,
            checked=lambda _i: _is_autostart_enabled(),
        ))
        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("  종료", _on_quit))
        return pystray.Menu(*items)

    def _on_refresh(*_):
        threading.Thread(target=_fetch_and_update, daemon=True).start()

    def _on_quit(icon, *_):
        _stop.set()
        icon.stop()

    # 마지막으로 그린 아이콘 키 — 동일하면 재생성 생략 (CPU 절약)
    _last_render_key: list = [None]

    def _redraw_icon_if_changed():
        ic = _icon_holder[0]
        if ic is None:
            return
        sections = checker.get_usage_sections()
        pcts = [d.get("utilization") or 0 for _, d, _ in sections]
        pct_max = max(pcts) if pcts else 0
        agent = _aggregate_agent_state()
        agent_state = agent.get("state", "idle")
        # 변경 감지 키 — 사용률(정수)과 상태로 캐시
        key = (int(pct_max), agent_state)
        if key != _last_render_key[0]:
            ic.icon = _make_pil_icon(pct_max, agent_state=agent_state)
            _last_render_key[0] = key
        ic.title = _tooltip()
        ic.menu = _make_menu()

    def _fetch_and_update():
        if not checker.token:
            checker.get_credentials_from_keychain()
        checker.fetch_usage()
        _redraw_icon_if_changed()

    def _auto_refresh_loop():
        # 사용량 API 폴링 — 60초
        while not _stop.wait(60):
            _fetch_and_update()

    def _agent_state_loop():
        # 에이전트 상태 파일 폴링 — 2초 (mtime 기반 변경 감지)
        last_mtime = 0.0
        while not _stop.wait(2):
            try:
                mtime = os.path.getmtime(_AGENT_STATE_FILE) if os.path.exists(_AGENT_STATE_FILE) else 0.0
            except Exception:
                mtime = 0.0
            # 파일이 바뀌었거나, 시간이 지나 'idle'로 강등될 수도 있어 주기적으로 재계산
            if mtime != last_mtime:
                last_mtime = mtime
            _redraw_icon_if_changed()

    icon = pystray.Icon(
        "claude_usage",
        _make_pil_icon(0, agent_state="idle"),
        "Claude Code 사용량",
        pystray.Menu(pystray.MenuItem("로딩 중...", None, enabled=False)),
    )
    _icon_holder[0] = icon

    threading.Thread(target=_fetch_and_update, daemon=True).start()
    threading.Thread(target=_auto_refresh_loop, daemon=True).start()
    threading.Thread(target=_agent_state_loop, daemon=True).start()
    icon.run()


# ──────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────

# ──────────────────────────────────────────────
# 데스크탑 오크 위젯 — 항상 위로, 투명 배경, 상태별 애니메이션
# ──────────────────────────────────────────────

_ORC_W = 160
_ORC_H = 180

# 스프라이트 디렉토리 — 아래 파일명 규칙으로 두면 PIL 드로잉 대신 사용:
#   <state>.gif         → 애니메이션 (각 프레임 자체 duration 존중)
#   <state>_1.png, _2…  → 번호 시퀀스 (100ms 간격)
#   <state>.png         → 단일 정적 이미지
# state ∈ {idle, working, waiting, done}. 파일 없으면 PIL 도형 폴백.
_ORC_IMAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orc_images")
_FRAME_CACHE: dict = {}  # state -> [(PIL.Image, duration_ms), ...]

# 색 팔레트 — magenta(투명키)는 절대 쓰지 않음
# 워크래프트3 피온 스타일
_ORC_SKIN       = (140, 180, 90)
_ORC_SKIN_DARK  = (90, 130, 60)
_ORC_TUSK       = (250, 245, 220)
_ORC_EYE_W      = (240, 240, 240)
_ORC_INK        = (30, 30, 46)
_ORC_CLOTH      = (80, 60, 50)
_ORC_HOOD       = (110, 80, 55)    # 피온 후드 갈색
_ORC_HOOD_DARK  = (70, 48, 28)     # 후드 안쪽 그림자
_ORC_APRON      = (155, 105, 60)   # 가죽 앞치마
_ORC_APRON_DARK = (95, 60, 30)     # 허리띠
_ORC_BUCKLE     = (200, 170, 80)   # 벨트 버클(놋쇠)
_ORC_HAMMER_HEAD = (90, 95, 110)
_ORC_HAMMER_HANDLE = (140, 95, 50)


def _draw_orc(state: str, frame: int):
    """160x180 RGBA 워크래프트3 일꾼(피온) 초상화 — 얼굴 중심 클로즈업."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (_ORC_W, _ORC_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    bob = (frame % 2) * 2

    # ── 후드/헝겊 (얼굴 뒤에 펼쳐진 갈색 두건) ──
    hood_top = 4 + bob
    d.polygon([
        (45, hood_top - 2), (80, hood_top - 6), (115, hood_top - 2),
        (140, hood_top + 22), (150, hood_top + 70),
        (146, hood_top + 130), (130, hood_top + 154),
        (30, hood_top + 154), (14, hood_top + 130),
        (10, hood_top + 70), (20, hood_top + 22),
    ], fill=_ORC_HOOD, outline=_ORC_INK, width=2)
    # 후드 안쪽 그림자
    d.chord([24, hood_top + 6, 136, hood_top + 60],
            start=180, end=360, fill=_ORC_HOOD_DARK)

    # ── 얼굴 (큰 타원, 캔버스 점령) ──
    face_top = 22 + bob
    face_bot = 148 + bob
    d.ellipse([32, face_top, 128, face_bot],
              fill=_ORC_SKIN, outline=_ORC_SKIN_DARK, width=2)
    # 이마 그림자 (후드 안쪽 어둠)
    d.chord([32, face_top, 128, face_top + 26],
            start=180, end=360, fill=_ORC_SKIN_DARK)

    # ── 눈 (크게) ──
    eye_y = face_top + 28
    if state == "idle":
        d.arc([42, eye_y - 5, 68, eye_y + 7], start=0, end=180, fill=_ORC_INK, width=3)
        d.arc([92, eye_y - 5, 118, eye_y + 7], start=0, end=180, fill=_ORC_INK, width=3)
    else:
        d.ellipse([42, eye_y - 9, 68, eye_y + 9],
                  fill=_ORC_EYE_W, outline=_ORC_INK, width=2)
        d.ellipse([92, eye_y - 9, 118, eye_y + 9],
                  fill=_ORC_EYE_W, outline=_ORC_INK, width=2)
        if state == "waiting":
            px, py = 6, 2   # 옆을 흘끗
        elif state == "done":
            px, py = 0, -1
        else:  # working
            px, py = 2, 3
        d.ellipse([51 + px, eye_y - 4 + py, 59 + px, eye_y + 4 + py], fill=_ORC_INK)
        d.ellipse([101 + px, eye_y - 4 + py, 109 + px, eye_y + 4 + py], fill=_ORC_INK)

    # ── 큰 코 (얼굴 중앙 점령) ──
    nose_top = face_top + 42
    nose_bot = face_top + 96
    d.ellipse([56, nose_top, 104, nose_bot],
              fill=_ORC_SKIN, outline=_ORC_SKIN_DARK, width=2)
    # 콧등 하이라이트
    d.ellipse([64, nose_top + 8, 80, nose_top + 32], fill=(170, 210, 115))
    # 콧구멍
    d.ellipse([66, nose_bot - 14, 76, nose_bot - 5], fill=_ORC_INK)
    d.ellipse([84, nose_bot - 14, 94, nose_bot - 5], fill=_ORC_INK)

    # ── 입 + 큰 송곳니 ──
    mouth_y = face_top + 112
    # 입
    if state == "done":
        d.arc([60, mouth_y - 6, 100, mouth_y + 14], start=0, end=180, fill=_ORC_INK, width=3)
    elif state == "working":
        d.line([66, mouth_y + 4, 94, mouth_y + 6], fill=_ORC_INK, width=3)
    elif state == "waiting":
        # 멍하니 벌어진 입
        d.ellipse([66, mouth_y - 4, 94, mouth_y + 14], fill=_ORC_INK)
    else:  # idle
        d.arc([72, mouth_y, 88, mouth_y + 8], start=0, end=180, fill=_ORC_INK, width=2)

    # 송곳니 (위로 솟음, 매우 크게)
    if state == "waiting":
        # 입 벌렸을 때는 더 길게
        tusk_top_y = mouth_y - 30
    else:
        tusk_top_y = mouth_y - 22
    # 왼쪽
    d.polygon([
        (48, mouth_y + 14), (58, tusk_top_y), (68, mouth_y + 14)
    ], fill=_ORC_TUSK, outline=_ORC_INK, width=2)
    # 오른쪽
    d.polygon([
        (92, mouth_y + 14), (102, tusk_top_y), (112, mouth_y + 14)
    ], fill=_ORC_TUSK, outline=_ORC_INK, width=2)

    # ── 어깨/가슴 (살짝만) ──
    body_y = 152 + bob
    d.polygon([
        (8, body_y), (28, body_y - 6),
        (132, body_y - 6), (152, body_y),
        (152, _ORC_H), (8, _ORC_H)
    ], fill=_ORC_HOOD, outline=_ORC_INK, width=2)
    # 가죽 어깨끈
    d.rectangle([48, body_y, 112, body_y + 16],
                fill=_ORC_APRON, outline=_ORC_INK)
    # 버클
    d.rectangle([74, body_y + 3, 86, body_y + 13],
                fill=_ORC_BUCKLE, outline=_ORC_INK)

    # ── 상태별 ──
    if state == "working":
        # 망치 — 오른쪽에서 위아래 스윙
        swing = frame % 4
        if swing == 0:
            hx, hy = 148, 38
        elif swing == 1:
            hx, hy = 144, 80
        elif swing == 2:
            hx, hy = 148, 122
        else:
            hx, hy = 144, 80
        sx, sy = 132, body_y + 4
        d.line([sx, sy, hx, hy], fill=_ORC_HAMMER_HANDLE, width=6)
        d.rectangle([hx - 14, hy - 10, hx + 12, hy + 10],
                    fill=_ORC_HAMMER_HEAD, outline=_ORC_INK, width=2)
        d.rectangle([hx - 11, hy - 7, hx + 9, hy - 1],
                    fill=(125, 130, 145))
        if swing == 2:
            for sx2, sy2 in [(hx + 14, hy + 12), (hx - 24, hy + 14)]:
                _draw_sparkle(d, sx2, sy2, 4, (249, 226, 175, 255))

    elif state == "waiting":
        # 오른쪽 송곳니에 묶인 뼈 장식
        # 끈
        d.line([(102, tusk_top_y + 8), (108, tusk_top_y + 18)],
               fill=(245, 240, 220), width=2)
        d.line([(108, tusk_top_y + 18), (114, mouth_y + 6)],
               fill=(245, 240, 220), width=2)
        # T자 뼈 — 앞치마 위에 매달림
        bone_x, bone_y = 114, mouth_y + 10
        d.rectangle([bone_x - 8, bone_y, bone_x + 6, bone_y + 5],
                    fill=_ORC_TUSK, outline=_ORC_INK)
        d.rectangle([bone_x - 3, bone_y + 4, bone_x + 1, bone_y + 14],
                    fill=_ORC_TUSK, outline=_ORC_INK)

        # 말풍선 + ?  (우상단 — 후드 위로)
        bub_top = 0 - bob
        bub_left, bub_right = 112, 158
        d.ellipse([bub_left, bub_top, bub_right, bub_top + 28],
                  fill=(255, 255, 255), outline=_ORC_INK, width=2)
        d.polygon([(bub_left + 4, bub_top + 22),
                   (bub_left, bub_top + 36),
                   (bub_left + 14, bub_top + 24)],
                  fill=(255, 255, 255), outline=_ORC_INK)
        try:
            font = ImageFont.truetype("arial.ttf", 18)
        except Exception:
            font = ImageFont.load_default()
        d.text((bub_left + 16, bub_top + 4), "?", fill=_ORC_INK, font=font)

    elif state == "done":
        # 만세 팔 (양 옆 위로)
        d.line([24, body_y - 4, 8, 20], fill=_ORC_HOOD, width=10)
        d.ellipse([0, 12, 22, 34], fill=_ORC_SKIN, outline=_ORC_SKIN_DARK, width=2)
        d.line([136, body_y - 4, 152, 20], fill=_ORC_HOOD, width=10)
        d.ellipse([138, 12, 160, 34], fill=_ORC_SKIN, outline=_ORC_SKIN_DARK, width=2)
        sparkle_color = (249, 226, 175, 255)
        positions = [(2, 4), (158, 4), (78, 0)] if frame % 2 == 0 else [(8, 36), (152, 36), (80, 8)]
        for sx, sy in positions:
            _draw_sparkle(d, sx, sy, 5, sparkle_color)

    return img


def _draw_sparkle(draw, cx: int, cy: int, r: int, color):
    """4-점 별 — PIL 폴리곤."""
    pts = [
        (cx, cy - r),
        (cx + r // 2, cy - r // 2),
        (cx + r, cy),
        (cx + r // 2, cy + r // 2),
        (cx, cy + r),
        (cx - r // 2, cy + r // 2),
        (cx - r, cy),
        (cx - r // 2, cy - r // 2),
    ]
    draw.polygon(pts, fill=color)


def _draw_project_name(name: str):
    """160x16 RGBA — 프로젝트명(cwd 베이스네임) 작은 배지."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (_ORC_W, 16), (0, 0, 0, 0))
    if not name:
        return img
    if len(name) > 16:
        name = name[:14] + "…"
    d = ImageDraw.Draw(img)
    font = None
    for path in ("malgun.ttf", "AppleGothic.ttf", "NotoSansCJK-Regular.ttc"):
        try:
            font = ImageFont.truetype(path, 10)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    bbox = d.textbbox((0, 0), name, font=font)
    tw = bbox[2] - bbox[0]
    pad = 6
    cx = _ORC_W // 2
    bg_l = max(0, cx - tw // 2 - pad)
    bg_r = min(_ORC_W, cx + tw // 2 + pad)
    d.rounded_rectangle([bg_l, 1, bg_r, 14], radius=6,
                        fill=(40, 45, 60, 220), outline=(120, 125, 145, 255))
    d.text((cx - tw // 2, 1), name, fill=(220, 225, 230, 255), font=font)
    return img


def _draw_orc_label(state: str):
    """오크 아래에 그릴 상태 라벨 PIL 이미지 (160x24)."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (_ORC_W, 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 이모지 폰트 의존 제거 — 한글 폰트 안전 텍스트만 사용
    label = {
        "working": "열일 중...",
        "waiting": "컨펌 대기",
        "done":    "Jobs done!",
        "idle":    "z z z",
    }.get(state, "")
    color = {
        "working": (250, 179, 135),
        "waiting": (249, 226, 175),
        "done":    (166, 227, 161),
        "idle":    (180, 185, 200),
    }.get(state, (200, 200, 200))
    if not label:
        return img
    d.rounded_rectangle([10, 2, 150, 22], radius=10, fill=color + (240,), outline=(30, 30, 46, 255))
    font = None
    for path in ("malgun.ttf", "AppleGothic.ttf", "NotoSansCJK-Regular.ttc"):
        try:
            font = ImageFont.truetype(path, 12)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    bbox = d.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    d.text((_ORC_W // 2 - tw // 2, 5), label, fill=(30, 30, 46, 255), font=font)
    return img


def _fit_to_canvas(img):
    """이미지를 _ORC_W x _ORC_H 안에 들어가도록 비율 유지하며 리사이즈 (확대/축소 양방향)."""
    from PIL import Image
    iw, ih = img.size
    scale = min(_ORC_W / iw, _ORC_H / ih)
    if scale != 1.0:
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        img = img.resize((nw, nh), Image.LANCZOS)
    return img


def _load_state_frames(state: str):
    """상태별 스프라이트 프레임 로드. 반환: [(PIL.Image, duration_ms), ...]
    파일 없으면 빈 리스트 — 호출자가 PIL 폴백 사용."""
    from PIL import Image
    import glob

    if state in _FRAME_CACHE:
        return _FRAME_CACHE[state]

    frames: list = []
    if not os.path.isdir(_ORC_IMAGE_DIR):
        _FRAME_CACHE[state] = frames
        return frames

    # 1) GIF (애니메이션, 프레임별 duration 존중)
    gif_path = os.path.join(_ORC_IMAGE_DIR, f"{state}.gif")
    if os.path.exists(gif_path):
        try:
            img = Image.open(gif_path)
            n = getattr(img, "n_frames", 1)
            for i in range(n):
                img.seek(i)
                f = img.convert("RGBA").copy()
                f = _fit_to_canvas(f)
                dur = max(50, int(img.info.get("duration", 100)))
                frames.append((f, dur))
        except Exception as e:
            _log(f"_load_state_frames: GIF 로드 실패 {gif_path}: {e}")
            frames = []

    # 2) 번호 시퀀스 PNG
    if not frames:
        seq = sorted(glob.glob(os.path.join(_ORC_IMAGE_DIR, f"{state}_*.png")))
        for path in seq:
            try:
                f = Image.open(path).convert("RGBA")
                f = _fit_to_canvas(f)
                frames.append((f, 100))
            except Exception as e:
                _log(f"_load_state_frames: PNG 시퀀스 로드 실패 {path}: {e}")

    # 3) 단일 PNG
    if not frames:
        single = os.path.join(_ORC_IMAGE_DIR, f"{state}.png")
        if os.path.exists(single):
            try:
                f = Image.open(single).convert("RGBA")
                f = _fit_to_canvas(f)
                # 정적 이미지 — 큰 duration 으로 사실상 고정
                frames.append((f, 10_000))
            except Exception as e:
                _log(f"_load_state_frames: PNG 로드 실패 {single}: {e}")

    _FRAME_CACHE[state] = frames
    return frames


def run_orc_widget():
    """데스크탑 오크 위젯 — 항상 위로, 투명, 드래그 가능. 인증 불필요."""
    import tkinter as tk
    try:
        from PIL import Image, ImageTk
    except ImportError:
        print("Pillow 미설치: pip install pillow")
        sys.exit(1)

    TICK_MS = 250  # 애니메이션 간격
    TRANSP = "magenta"  # Windows 투명 처리용 컬러키

    root = tk.Tk()
    root.title("Claude Orc")
    root.overrideredirect(True)               # 창 테두리 제거
    root.attributes("-topmost", True)         # 항상 위

    # ── 플랫폼별 투명 배경 ──
    canvas_bg = TRANSP  # 기본값
    if sys.platform == "win32":
        # 컬러키 방식 — magenta 픽셀만 투명
        root.configure(bg=TRANSP)
        try:
            root.wm_attributes("-transparentcolor", TRANSP)
        except tk.TclError:
            pass
    elif sys.platform == "darwin":
        # macOS: Tk 8.6+ 의 실제 투명 윈도우
        applied_transparent = False
        try:
            root.wm_attributes("-transparent", True)
            root.configure(bg="systemTransparent")
            canvas_bg = "systemTransparent"
            applied_transparent = True
        except tk.TclError:
            pass
        if not applied_transparent:
            # 구버전 Tk — 알파 폴백
            root.configure(bg=TRANSP)
            try:
                root.attributes("-alpha", 0.92)
            except tk.TclError:
                pass
    else:
        # Linux 등 — 알파 폴백
        root.configure(bg=TRANSP)
        try:
            root.attributes("-alpha", 0.92)
        except tk.TclError:
            pass

    # 카드 = 프로젝트명(16) + 오크(180) + 상태라벨(24) — 세션 1개당
    PROJECT_H = 16
    LABEL_H = 24
    CARD_W = _ORC_W
    CARD_H = PROJECT_H + _ORC_H + LABEL_H  # 220
    GAP = 6
    MAX_SESSIONS = 5

    canvas = tk.Canvas(root, width=CARD_W, height=CARD_H,
                       bg=canvas_bg, highlightthickness=0, bd=0)
    canvas.pack()
    img_id = canvas.create_image(0, 0, anchor="nw")
    _photos: list = [None]

    # ── 드래그 ──
    def on_drag_start(e):
        root._dx, root._dy = e.x_root - root.winfo_x(), e.y_root - root.winfo_y()
    def on_drag_move(e):
        root.geometry(f"+{e.x_root - root._dx}+{e.y_root - root._dy}")
    canvas.bind("<ButtonPress-1>", on_drag_start)
    canvas.bind("<B1-Motion>", on_drag_move)

    # ── 우클릭 메뉴 ──
    _compact = [False]
    menu = tk.Menu(root, tearoff=0)
    def _toggle_compact():
        _compact[0] = not _compact[0]
    menu.add_command(label="컴팩트 모드 (라벨 숨김)", command=_toggle_compact)
    menu.add_separator()
    menu.add_command(label="종료", command=root.destroy)
    def on_right(e):
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()
    canvas.bind("<Button-3>", on_right)
    if sys.platform == "darwin":
        canvas.bind("<Button-2>", on_right)

    # ── 초기 위치: 화면 우하단 ──
    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"+{sw - CARD_W - 40}+{sh - CARD_H - 100}")

    widget_start = datetime.now()
    anims: dict = {}        # sid -> {state, index, elapsed}
    current_size = [CARD_W, CARD_H]

    def _render_card(state: str, project: str, anim: dict, compact: bool):
        """카드 한 장 PIL 이미지. compact 면 오크만, 아니면 프로젝트명+오크+라벨."""
        h = _ORC_H if compact else CARD_H
        card = Image.new("RGBA", (CARD_W, h), (0, 0, 0, 0))
        # 오크 프레임 결정
        anim["elapsed"] += TICK_MS
        sprite_frames = _load_state_frames(state)
        if sprite_frames:
            cur_img, cur_dur = sprite_frames[anim["index"]]
            if anim["elapsed"] >= cur_dur:
                anim["elapsed"] = 0
                anim["index"] = (anim["index"] + 1) % len(sprite_frames)
                cur_img, _ = sprite_frames[anim["index"]]
            blank = Image.new("RGBA", (_ORC_W, _ORC_H), (0, 0, 0, 0))
            cx = (_ORC_W - cur_img.width) // 2
            cy = (_ORC_H - cur_img.height) // 2
            blank.alpha_composite(cur_img, (cx, cy))
            orc_img = blank
        else:
            frame_n = int(anim["elapsed"] // 100) % 8
            orc_img = _draw_orc(state, frame_n)

        if compact:
            card.alpha_composite(orc_img, (0, 0))
        else:
            card.alpha_composite(_draw_project_name(project), (0, 0))
            card.alpha_composite(orc_img, (0, PROJECT_H))
            card.alpha_composite(_draw_orc_label(state), (0, PROJECT_H + _ORC_H))
        return card

    def tick():
        agent = _aggregate_agent_state(min_event_at=widget_start)
        all_sessions = agent.get("sessions") or []
        now = datetime.now()
        # 표시 조건: 위젯 시작 후 이벤트 있음 + idle 60초 미만 (idle 60초+ 는 세션 종료로 간주)
        # PID 기반 종료 감지는 제거 — 훅이 기록하는 claude_pid 가 중간 셸 PID 일 수 있어 신뢰 불가.
        fresh = []
        for s in all_sessions:
            try:
                ts = datetime.fromisoformat(s.get("updated_at", ""))
                if ts < widget_start:
                    continue
            except Exception:
                continue
            # idle 상태로 너무 오래 → 세션 종료로 간주
            age = (now - ts).total_seconds()
            if s.get("state") == "idle" and age > _ORPHAN_IDLE_SECONDS:
                continue
            fresh.append(s)
        if not fresh:
            fresh = [{"session_id": "__default__", "state": "idle",
                      "cwd": "", "tool": ""}]
        fresh = fresh[:MAX_SESSIONS]

        # 사라진 세션 anim 정리
        live_ids = {s["session_id"] for s in fresh}
        for sid in list(anims.keys()):
            if sid not in live_ids:
                del anims[sid]

        compact = _compact[0]
        n = len(fresh)
        card_h = _ORC_H if compact else CARD_H
        total_w = n * CARD_W + max(0, n - 1) * GAP

        composite = Image.new("RGBA", (total_w, card_h), (0, 0, 0, 0))
        for i, s in enumerate(fresh):
            sid = s["session_id"]
            state = s.get("state", "idle")
            project = os.path.basename(s.get("cwd") or "") or "(?)"
            anim = anims.setdefault(sid, {"state": None, "index": 0, "elapsed": 0})
            if anim["state"] != state:
                anim["state"] = state
                anim["index"] = 0
                anim["elapsed"] = 0
            card_img = _render_card(state, project, anim, compact)
            composite.alpha_composite(card_img, (i * (CARD_W + GAP), 0))

        # 캔버스 크기 갱신 (세션 수가 바뀌었거나 모드 토글)
        if (total_w, card_h) != tuple(current_size):
            canvas.config(width=total_w, height=card_h)
            current_size[0], current_size[1] = total_w, card_h

        _photos[0] = ImageTk.PhotoImage(composite)
        canvas.itemconfigure(img_id, image=_photos[0])

        root.after(TICK_MS, tick)

    tick()
    try:
        root.mainloop()
    except KeyboardInterrupt:
        root.destroy()


def main():
    mode = "--tray"    if "--tray"    in sys.argv else \
           "--desktop" if "--desktop" in sys.argv else \
           "--orc"     if "--orc"     in sys.argv else \
           "--graph"   if "--graph"   in sys.argv else "cli"

    # 오크 위젯은 인증 불필요 — 상태 파일만 읽음
    if mode == "--orc":
        run_orc_widget()
        return

    checker = ClaudeUsageChecker()
    if not checker.get_credentials_from_keychain():
        return

    if mode == "cli":
        if not checker.fetch_usage():
            print("API 호출 실패")
            return
        checker.print_usage()

    elif mode == "--graph":
        if not checker.fetch_usage():
            print("API 호출 실패")
            return
        run_graph(checker)

    elif mode == "--desktop":
        run_desktop_widget(checker)

    elif mode == "--tray":
        run_tray(checker)


if __name__ == "__main__":
    main()
