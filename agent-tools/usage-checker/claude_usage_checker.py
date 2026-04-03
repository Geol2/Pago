#!/usr/bin/env python3
"""
Claude Code 사용량 체크 프로그램
macOS Keychain에서 토큰을 가져와 사용량을 확인합니다.
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


class ClaudeUsageChecker:
    """Claude Code 사용량을 체크하는 클래스"""
    
    API_URL = "https://api.anthropic.com/api/oauth/usage"
    KEYCHAIN_SERVICE = "Claude Code-credentials"
    
    def __init__(self):
        self.token: Optional[str] = None
        self.usage_data: Optional[Dict[str, Any]] = None
    
    def get_credentials_from_keychain(self) -> bool:
        """OS에 맞는 방법으로 Claude Code 인증 정보 가져오기"""
        if sys.platform == "win32":
            return self._get_credentials_windows()
        return self._get_credentials_macos()

    def _get_credentials_windows(self) -> bool:
        """Windows: ~/.claude/credentials.json 에서 직접 읽기"""
        candidates = [
            os.path.join(os.path.expanduser("~"), ".claude", ".credentials.json"),
            os.path.join(os.path.expanduser("~"), ".claude", "credentials.json"),
            os.path.join(os.environ.get("APPDATA", ""), "Claude Code", "credentials.json"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return self._parse_credentials_file(path)

        print("✗ Windows에서 Claude Code 인증 정보를 찾을 수 없습니다.")
        print("  확인된 경로:")
        for p in candidates:
            print(f"    - {p} ({'있음' if os.path.exists(p) else '없음'})")
        return False

    def _get_credentials_macos(self) -> bool:
        """macOS: Keychain에서 읽기"""
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", self.KEYCHAIN_SERVICE, "-w"],
                capture_output=True, text=True, check=True
            )
            return self._parse_credentials_json(result.stdout.strip())
        except subprocess.CalledProcessError:
            print("✗ Keychain에서 Claude Code 인증 정보를 찾을 수 없습니다.")
            print("  먼저 'claude login' 명령어로 로그인하세요.")
            return False
        except Exception as e:
            print(f"✗ 오류 발생: {e}")
            return False

    def _parse_credentials_file(self, path: str) -> bool:
        """credentials.json 파일을 읽어 토큰을 추출한다."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return self._parse_credentials_json(f.read())
        except Exception as e:
            print(f"✗ 파일 읽기 실패 ({path}): {e}")
            return False

    def _parse_credentials_json(self, raw: str) -> bool:
        """JSON 문자열에서 OAuth 토큰을 추출한다."""
        try:
            credentials = json.loads(raw)
            if "claudeAiOauth" in credentials:
                self.token = credentials["claudeAiOauth"]["accessToken"]
                subscription_type = credentials["claudeAiOauth"].get("subscriptionType", "unknown")
                print(f"✓ 인증 성공! (플랜: {subscription_type.upper()})")
                return True
            else:
                print("✗ 인증 정보에서 OAuth 토큰을 찾을 수 없습니다.")
                return False
        except json.JSONDecodeError:
            print("✗ 인증 정보 파싱 실패")
            return False
    
    def fetch_usage(self) -> bool:
        """API를 통해 사용량 정보 가져오기"""
        if not self.token:
            print("✗ 토큰이 없습니다. 먼저 인증을 완료하세요.")
            return False
        
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "User-Agent": "claude-code-usage-checker/1.0",
            "Authorization": f"Bearer {self.token}",
            "anthropic-beta": "oauth-2025-04-20",
            "Accept-Encoding": "gzip, compress, deflate, br"
        }
        
        try:
            response = requests.get(self.API_URL, headers=headers, timeout=10)
            
            if response.status_code == 200:
                self.usage_data = response.json()
                return True
            elif response.status_code == 401:
                print("✗ 인증 실패. 토큰이 만료되었을 수 있습니다.")
                print("  'claude logout' 후 'claude login'으로 다시 로그인하세요.")
                return False
            else:
                print(f"✗ API 오류: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            print("✗ API 요청 시간 초과")
            return False
        except requests.exceptions.RequestException as e:
            print(f"✗ 네트워크 오류: {e}")
            return False
    
    def format_reset_time(self, reset_time_str: Optional[str]) -> str:
        """리셋 시간을 읽기 쉬운 형식으로 변환"""
        if not reset_time_str:
            return "정보 없음"
        
        try:
            # ISO 8601 형식 파싱
            reset_time = datetime.fromisoformat(reset_time_str.replace('Z', '+00:00'))
            now = datetime.now(reset_time.tzinfo)
            
            time_diff = reset_time - now
            
            if time_diff.total_seconds() < 0:
                return "리셋 완료"
            
            hours = int(time_diff.total_seconds() // 3600)
            minutes = int((time_diff.total_seconds() % 3600) // 60)
            
            if hours > 0:
                return f"{hours}시간 {minutes}분 후"
            else:
                return f"{minutes}분 후"
                
        except Exception:
            return reset_time_str
    
    def display_usage(self):
        """사용량 정보를 보기 좋게 출력"""
        if not self.usage_data:
            print("✗ 사용량 데이터가 없습니다.")
            return
        
        print("\n" + "="*60)
        print("📊 Claude Code 사용량 현황")
        print("="*60)
        
        # 5시간 rolling window
        five_hour = self.usage_data.get("five_hour")
        if five_hour:
            utilization = five_hour.get("utilization", 0)  # 이미 퍼센트 값 (57.0 = 57%)
            resets_at = five_hour.get("resets_at")
            bar_length = 40
            filled = min(bar_length, int(bar_length * utilization / 100))
            bar = "█" * filled + "░" * (bar_length - filled)
            over = " ⚠ 초과" if utilization > 100 else ""
            print(f"\n🕐 5시간 Rolling Window")
            print(f"   사용률: {utilization:.1f}%{over}")
            print(f"   [{bar}]")
            print(f"   리셋: {self.format_reset_time(resets_at)}")
        else:
            print("\n🕐 5시간 Rolling Window: 정보 없음")

        # 7일 주간 한도
        seven_day = self.usage_data.get("seven_day")
        if seven_day:
            utilization = seven_day.get("utilization", 0)  # 이미 퍼센트 값
            resets_at = seven_day.get("resets_at")
            bar_length = 40
            filled = min(bar_length, int(bar_length * utilization / 100))
            bar = "█" * filled + "░" * (bar_length - filled)
            over = " ⚠ 초과" if utilization > 100 else ""
            print(f"\n📅 7일 주간 한도")
            print(f"   사용률: {utilization:.1f}%{over}")
            print(f"   [{bar}]")
            print(f"   리셋: {self.format_reset_time(resets_at)}")
        else:
            print("\n📅 7일 주간 한도: 정보 없음")

        print("\n" + "="*60)

        # 경고 메시지
        if five_hour and five_hour.get("utilization", 0) > 80:
            print("⚠️  경고: 5시간 한도가 80%를 초과했습니다!")
        if seven_day and seven_day.get("utilization", 0) > 80:
            print("⚠️  경고: 주간 한도가 80%를 초과했습니다!")
    
    def run(self):
        """프로그램 실행"""
        print("\n🤖 Claude Code 사용량 체커")
        print("-" * 60)
        
        # 1. Keychain에서 인증 정보 가져오기
        if not self.get_credentials_from_keychain():
            return
        
        # 2. API에서 사용량 가져오기
        print("\n📡 사용량 정보를 가져오는 중...")
        if not self.fetch_usage():
            return
        
        # 3. 사용량 출력
        self.display_usage()
        
        print("\n💡 Tip: 'claude /status' 명령어로도 터미널에서 확인 가능합니다.\n")


def run_desktop_widget(checker: "ClaudeUsageChecker"):
    """tkinter 기반 항상-위 데스크탑 위젯. 60초마다 자동 갱신."""
    import tkinter as tk

    REFRESH_MS  = 60_000  # API 갱신: 1분
    TICK_MS     = 1_000   # 화면 갱신: 1초
    BG = "#1e1e2e"
    FG = "#cdd6f4"
    GREEN = "#a6e3a1"
    YELLOW = "#f9e2af"
    RED = "#f38ba8"
    GRAY = "#6c7086"

    root = tk.Tk()
    root.title("Claude 사용량")
    root.configure(bg=BG)
    root.attributes("-topmost", True)
    root.resizable(False, False)

    # 드래그 이동
    def on_drag_start(e):
        root._drag_x, root._drag_y = e.x, e.y
    def on_drag_move(e):
        dx, dy = e.x - root._drag_x, e.y - root._drag_y
        root.geometry(f"+{root.winfo_x()+dx}+{root.winfo_y()+dy}")
    root.bind("<ButtonPress-1>", on_drag_start)
    root.bind("<B1-Motion>", on_drag_move)

    def make_bar(pct: float, width: int = 28) -> str:
        # pct는 이미 퍼센트 값 (57.0 = 57%)
        filled = min(width, int(width * pct / 100))
        return "█" * filled + "░" * (width - filled)

    def pct_color(pct: float) -> str:
        if pct > 100: return RED
        if pct > 80: return YELLOW
        return GREEN

    lbl_title = tk.Label(root, text="⬡ Claude Code 사용량", bg=BG, fg=FG,
                         font=("Segoe UI", 10, "bold"), pady=6)
    lbl_title.pack(fill="x", padx=10)

    tk.Frame(root, bg=GRAY, height=1).pack(fill="x", padx=10)

    lbl_5h_title = tk.Label(root, text="🕐 5시간 Rolling Window", bg=BG, fg=FG,
                             font=("Segoe UI", 9), anchor="w")
    lbl_5h_title.pack(fill="x", padx=14, pady=(8, 0))
    lbl_5h_pct  = tk.Label(root, bg=BG, fg=GREEN, font=("Consolas", 9), anchor="w")
    lbl_5h_pct.pack(fill="x", padx=14)
    lbl_5h_bar  = tk.Label(root, bg=BG, fg=GREEN, font=("Consolas", 9), anchor="w")
    lbl_5h_bar.pack(fill="x", padx=14)
    lbl_5h_rst  = tk.Label(root, bg=BG, fg=GRAY, font=("Segoe UI", 8), anchor="w")
    lbl_5h_rst.pack(fill="x", padx=14, pady=(0, 6))

    tk.Frame(root, bg=GRAY, height=1).pack(fill="x", padx=10)

    lbl_7d_title = tk.Label(root, text="📅 7일 주간 한도", bg=BG, fg=FG,
                             font=("Segoe UI", 9), anchor="w")
    lbl_7d_title.pack(fill="x", padx=14, pady=(8, 0))
    lbl_7d_pct  = tk.Label(root, bg=BG, fg=GREEN, font=("Consolas", 9), anchor="w")
    lbl_7d_pct.pack(fill="x", padx=14)
    lbl_7d_bar  = tk.Label(root, bg=BG, fg=GREEN, font=("Consolas", 9), anchor="w")
    lbl_7d_bar.pack(fill="x", padx=14)
    lbl_7d_rst  = tk.Label(root, bg=BG, fg=GRAY, font=("Segoe UI", 8), anchor="w")
    lbl_7d_rst.pack(fill="x", padx=14, pady=(0, 6))

    tk.Frame(root, bg=GRAY, height=1).pack(fill="x", padx=10)

    lbl_updated = tk.Label(root, bg=BG, fg=GRAY, font=("Segoe UI", 7), anchor="e")
    lbl_updated.pack(fill="x", padx=10, pady=4)

    def fetch_api():
        """API 호출 (60초마다). 백그라운드 스레드에서 실행."""
        import threading
        def _call():
            if not checker.token:
                checker.get_credentials_from_keychain()
            checker.fetch_usage()
        threading.Thread(target=_call, daemon=True).start()
        root.after(REFRESH_MS, fetch_api)

    def tick():
        """초마다 화면 갱신 — API 재호출 없이 로컬 계산."""
        if checker.usage_data:
            fh = checker.usage_data.get("five_hour") or {}
            sd = checker.usage_data.get("seven_day") or {}

            u5 = fh.get("utilization", 0)
            lbl_5h_pct.config(text=f"  {u5:.1f}%{'  ⚠ 초과' if u5 > 100 else ''}",
                               fg=pct_color(u5))
            lbl_5h_bar.config(text=f"  [{make_bar(u5)}]", fg=pct_color(u5))
            lbl_5h_rst.config(text=f"  리셋: {checker.format_reset_time(fh.get('resets_at'))}")

            u7 = sd.get("utilization", 0)
            lbl_7d_pct.config(text=f"  {u7:.1f}%{'  ⚠ 초과' if u7 > 100 else ''}",
                               fg=pct_color(u7))
            lbl_7d_bar.config(text=f"  [{make_bar(u7)}]", fg=pct_color(u7))
            lbl_7d_rst.config(text=f"  리셋: {checker.format_reset_time(sd.get('resets_at'))}")

        now = datetime.now().strftime("%H:%M:%S")
        lbl_updated.config(text=f"갱신: {now}  ")
        root.after(TICK_MS, tick)

    fetch_api()
    tick()
    try:
        root.mainloop()
    except KeyboardInterrupt:
        root.destroy()


def main():
    """메인 함수"""
    import sys as _sys
    if "--desktop" in _sys.argv:
        checker = ClaudeUsageChecker()
        run_desktop_widget(checker)
    else:
        checker = ClaudeUsageChecker()
        checker.run()


if __name__ == "__main__":
    main()
