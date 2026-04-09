#!/usr/bin/env python3
"""
Claude Code 사용량 체커 (통합본)
  --desktop  : 접기/펴기 데스크탑 위젯
  --graph    : matplotlib 게이지 그래프
  (인수 없음): 터미널 텍스트 출력
"""

import subprocess
import json
import os
import sys
import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from datetime import datetime
from typing import Optional, Dict, Any


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
                return self._parse_credentials_file(path)
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
        if not self.token:
            return False
        try:
            response = requests.get(self.API_URL, headers=self._auth_headers(), timeout=10)
            if response.status_code == 200:
                self.usage_data = response.json()
                self.plan_name = self._extract_plan(self.usage_data)
                if not self.plan_name:
                    self._fetch_plan_from_account()
                return True
            return False
        except requests.exceptions.RequestException:
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
            u = d.get("utilization", 0)
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
            pcts = [d.get("utilization", 0) for _, d, _ in sections]
            if pcts:
                lbl_mini.config(
                    text="  ".join(f"{label.split()[0]} {u:.0f}%" for _, d, label in sections
                                   for u in [d.get("utilization", 0)]),
                    fg=pct_color(max(pcts))
                )
            for key, d, label in sections:
                if key not in _section_labels:
                    continue
                u = d.get("utilization", 0)
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
        values = [min(d.get("utilization", 0), 100) for _, d, _ in sections]
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
            u = d.get("utilization", 0)
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

    timer_check.start()
    plt.show()


# ──────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────

def main():
    mode = "--desktop" if "--desktop" in sys.argv else \
           "--graph"   if "--graph"   in sys.argv else "cli"

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


if __name__ == "__main__":
    main()
