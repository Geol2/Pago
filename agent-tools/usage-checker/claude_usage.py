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
    API_URL = "https://api.anthropic.com/api/oauth/usage"
    KEYCHAIN_SERVICE = "Claude Code-credentials"

    def __init__(self):
        self.token: Optional[str] = None
        self.usage_data: Optional[Dict[str, Any]] = None

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

    def fetch_usage(self) -> bool:
        if not self.token:
            return False
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
            "anthropic-beta": "oauth-2025-04-20",
        }
        try:
            response = requests.get(self.API_URL, headers=headers, timeout=10)
            if response.status_code == 200:
                self.usage_data = response.json()
                return True
            return False
        except requests.exceptions.RequestException:
            return False

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
        if not self.usage_data:
            print("사용량 데이터가 없습니다.")
            return
        print("\n" + "=" * 60)
        print("Claude Code 사용량 현황")
        print("=" * 60)
        for key, label in [("five_hour", "5시간 Rolling Window"), ("seven_day", "7일 주간 한도")]:
            d = self.usage_data.get(key)
            if d:
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

    lbl_5h_pct, lbl_5h_bar, lbl_5h_rst = make_section(panel, "5시간 Rolling Window")
    tk.Frame(panel, bg=GRAY, height=1).pack(fill="x", padx=8)
    lbl_7d_pct, lbl_7d_bar, lbl_7d_rst = make_section(panel, "7일 주간 한도")
    tk.Frame(panel, bg=GRAY, height=1).pack(fill="x", padx=8)

    lbl_updated = tk.Label(panel, bg=BG, fg=GRAY, font=("Segoe UI", 7), anchor="e")
    lbl_updated.pack(fill="x", padx=10, pady=4)

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
        threading.Thread(target=_call, daemon=True).start()
        root.after(REFRESH_MS, fetch_api)

    # ── 화면 갱신 (1초마다) ──
    def tick():
        if checker.usage_data:
            fh = checker.usage_data.get("five_hour") or {}
            sd = checker.usage_data.get("seven_day") or {}
            u5 = fh.get("utilization", 0)
            u7 = sd.get("utilization", 0)

            # 미니뷰 수치
            lbl_mini.config(
                text=f"5h {u5:.0f}%  7d {u7:.0f}%",
                fg=pct_color(max(u5, u7))
            )

            # 펼쳐진 패널
            lbl_5h_pct.config(text=f"  {u5:.1f}%{'  초과' if u5 > 100 else ''}",
                               fg=pct_color(u5))
            lbl_5h_bar.config(text=f"  [{make_bar(u5)}]", fg=pct_color(u5))
            lbl_5h_rst.config(text=f"  리셋: {checker.format_reset_time(fh.get('resets_at'))}")

            lbl_7d_pct.config(text=f"  {u7:.1f}%{'  초과' if u7 > 100 else ''}",
                               fg=pct_color(u7))
            lbl_7d_bar.config(text=f"  [{make_bar(u7)}]", fg=pct_color(u7))
            lbl_7d_rst.config(text=f"  리셋: {checker.format_reset_time(sd.get('resets_at'))}")

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

    if sys.platform == "win32":
        plt.rcParams["font.family"] = "Malgun Gothic"
    elif sys.platform == "darwin":
        plt.rcParams["font.family"] = "AppleGothic"
    else:
        plt.rcParams["font.family"] = "NanumGothic"
    plt.rcParams["axes.unicode_minus"] = False

    data = checker.usage_data or {}
    fh = data.get("five_hour") or {}
    sd = data.get("seven_day") or {}
    u5 = fh.get("utilization", 0)
    u7 = sd.get("utilization", 0)
    r5_label = "리셋: " + checker.format_reset_time(fh.get("resets_at"))
    r7_label = "리셋: " + checker.format_reset_time(sd.get("resets_at"))

    def gauge_color(pct):
        if pct > 80: return "#f38ba8"
        if pct > 50: return "#f9e2af"
        return "#a6e3a1"

    def draw_gauge(ax, pct, title, reset_label):
        pct = min(pct, 100)
        color = gauge_color(pct)
        theta = np.linspace(np.pi, 0, 200)
        ax.plot(np.cos(theta), np.sin(theta), lw=18, color="#313244", solid_capstyle="round")
        ft = np.linspace(np.pi, np.pi - np.pi * (pct / 100), 200)
        ax.plot(np.cos(ft), np.sin(ft), lw=18, color=color, solid_capstyle="round")
        ax.set_xlim(-1.3, 1.3); ax.set_ylim(-0.3, 1.2)
        ax.set_aspect("equal"); ax.axis("off")
        ax.text(0, 0.22, f"{pct:.1f}%", ha="center", va="center",
                fontsize=22, fontweight="bold", color=color)
        ax.text(0, -0.05, title, ha="center", va="center", fontsize=11, color="#cdd6f4")
        ax.text(0, -0.22, reset_label, ha="center", va="center", fontsize=8, color="#6c7086")

    def draw_bar(ax):
        labels = ["5시간 Rolling", "7일 주간"]
        values = [min(u5, 100), min(u7, 100)]
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

    fig = plt.figure(figsize=(10, 5.5), facecolor="#1e1e2e")
    fig.suptitle("Claude Code 사용량 현황", color="#cdd6f4",
                 fontsize=15, fontweight="bold", y=0.97)
    fig.text(0.99, 0.01, f"갱신: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
             ha="right", va="bottom", color="#6c7086", fontsize=7)

    ax1 = fig.add_axes([0.02, 0.38, 0.44, 0.52])
    ax2 = fig.add_axes([0.54, 0.38, 0.44, 0.52])
    draw_gauge(ax1, u5, "5시간 Rolling Window", r5_label)
    draw_gauge(ax2, u7, "7일 주간 한도", r7_label)

    ax3 = fig.add_axes([0.08, 0.08, 0.84, 0.26])
    draw_bar(ax3)

    legend_elements = [
        mpatches.Patch(color="#a6e3a1", label="정상 (0~50%)"),
        mpatches.Patch(color="#f9e2af", label="주의 (50~80%)"),
        mpatches.Patch(color="#f38ba8", label="경고 (80%+)"),
    ]
    fig.legend(handles=legend_elements, loc="lower right",
               bbox_to_anchor=(0.99, 0.36), fontsize=8,
               facecolor="#313244", edgecolor="#6c7086",
               labelcolor="#cdd6f4", framealpha=0.9)
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
