#!/usr/bin/env python3
"""
Claude Code 사용량 체크 프로그램
Windows/macOS 모두 지원
"""

import subprocess
import json
import requests
import platform
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any


class ClaudeUsageChecker:
    """Claude Code 사용량을 체크하는 클래스"""
    
    API_URL = "https://api.anthropic.com/api/oauth/usage"
    KEYCHAIN_SERVICE = "Claude Code-credentials"
    
    def __init__(self):
        self.token: Optional[str] = None
        self.usage_data: Optional[Dict[str, Any]] = None
        self.os_type = platform.system()
    
    def get_windows_credentials(self) -> bool:
        """Windows에서 Claude Code 인증 정보 가져오기"""
        # Windows에서 Claude Code는 보통 %APPDATA%/Claude Code/credentials.json에 저장
        possible_paths = [
            Path(os.environ.get('APPDATA', '')) / 'Claude Code' / 'credentials.json',
            Path.home() / 'AppData' / 'Roaming' / 'Claude Code' / 'credentials.json',
            Path.home() / '.claude' / 'credentials.json',
        ]
        
        for cred_path in possible_paths:
            if cred_path.exists():
                try:
                    with open(cred_path, 'r', encoding='utf-8') as f:
                        credentials = json.load(f)
                    
                    if "claudeAiOauth" in credentials:
                        self.token = credentials["claudeAiOauth"]["accessToken"]
                        subscription_type = credentials["claudeAiOauth"].get("subscriptionType", "unknown")
                        print(f"✓ 인증 성공! (플랜: {subscription_type.upper()})")
                        print(f"  경로: {cred_path}")
                        return True
                except Exception as e:
                    print(f"  {cred_path} 읽기 실패: {e}")
                    continue
        
        print("✗ Windows에서 Claude Code 인증 정보를 찾을 수 없습니다.")
        print("  확인된 경로:")
        for path in possible_paths:
            print(f"    - {path} {'(존재함)' if path.exists() else '(없음)'}")
        return False
    
    def get_macos_credentials(self) -> bool:
        """macOS Keychain에서 Claude Code 인증 정보 가져오기"""
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", self.KEYCHAIN_SERVICE, "-w"],
                capture_output=True,
                text=True,
                check=True
            )
            
            credentials_json = result.stdout.strip()
            credentials = json.loads(credentials_json)
            
            if "claudeAiOauth" in credentials:
                self.token = credentials["claudeAiOauth"]["accessToken"]
                subscription_type = credentials["claudeAiOauth"].get("subscriptionType", "unknown")
                print(f"✓ 인증 성공! (플랜: {subscription_type.upper()})")
                return True
            else:
                print("✗ 인증 정보에서 OAuth 토큰을 찾을 수 없습니다.")
                return False
                
        except subprocess.CalledProcessError:
            print("✗ Keychain에서 Claude Code 인증 정보를 찾을 수 없습니다.")
            return False
        except json.JSONDecodeError:
            print("✗ 인증 정보 파싱 실패")
            return False
        except Exception as e:
            print(f"✗ 오류 발생: {e}")
            return False
    
    def get_credentials(self) -> bool:
        """운영체제에 맞는 방법으로 인증 정보 가져오기"""
        print(f"🖥️  운영체제: {self.os_type}")
        
        if self.os_type == "Windows":
            return self.get_windows_credentials()
        elif self.os_type == "Darwin":  # macOS
            return self.get_macos_credentials()
        else:  # Linux 등
            # Linux도 파일 기반으로 시도
            print("⚠️  Linux/기타 OS - Windows 방식으로 시도합니다.")
            return self.get_windows_credentials()
    
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
                print(f"  응답: {response.text[:200]}")
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
            utilization = five_hour.get("utilization", 0)
            resets_at = five_hour.get("resets_at")
            
            # 프로그레스 바 생성
            bar_length = 40
            filled = int(bar_length * utilization)
            bar = "█" * filled + "░" * (bar_length - filled)
            
            print(f"\n🕐 5시간 Rolling Window")
            print(f"   사용률: {utilization*100:.1f}%")
            print(f"   [{bar}]")
            print(f"   리셋: {self.format_reset_time(resets_at)}")
        else:
            print("\n🕐 5시간 Rolling Window: 정보 없음")
        
        # 7일 주간 한도
        seven_day = self.usage_data.get("seven_day")
        if seven_day:
            utilization = seven_day.get("utilization", 0)
            resets_at = seven_day.get("resets_at")
            
            # 프로그레스 바 생성
            bar_length = 40
            filled = int(bar_length * utilization)
            bar = "█" * filled + "░" * (bar_length - filled)
            
            print(f"\n📅 7일 주간 한도")
            print(f"   사용률: {utilization*100:.1f}%")
            print(f"   [{bar}]")
            print(f"   리셋: {self.format_reset_time(resets_at)}")
        else:
            print("\n📅 7일 주간 한도: 정보 없음")
        
        print("\n" + "="*60)
        
        # 경고 메시지
        if five_hour and five_hour.get("utilization", 0) > 0.8:
            print("⚠️  경고: 5시간 한도가 80%를 초과했습니다!")
        if seven_day and seven_day.get("utilization", 0) > 0.8:
            print("⚠️  경고: 주간 한도가 80%를 초과했습니다!")
    
    def show_troubleshooting(self):
        """문제 해결 가이드 출력"""
        print("\n" + "="*60)
        print("🔧 문제 해결 가이드")
        print("="*60)
        
        if self.os_type == "Windows":
            print("\n1. Claude Code가 설치되어 있나요?")
            print("   npm install -g @anthropic-ai/claude-code")
            print("\n2. 로그인이 되어 있나요?")
            print("   claude logout")
            print("   claude login")
            print("\n3. credentials.json 파일 위치 확인:")
            print("   %APPDATA%\\Claude Code\\credentials.json")
        else:
            print("\n1. Claude Code가 설치되어 있나요?")
            print("   npm install -g @anthropic-ai/claude-code")
            print("\n2. 로그인이 되어 있나요?")
            print("   claude logout")
            print("   claude login")
    
    def run(self):
        """프로그램 실행"""
        print("\n🤖 Claude Code 사용량 체커")
        print("-" * 60)
        
        # 1. 운영체제에 맞는 방법으로 인증 정보 가져오기
        if not self.get_credentials():
            self.show_troubleshooting()
            return
        
        # 2. API에서 사용량 가져오기
        print("\n📡 사용량 정보를 가져오는 중...")
        if not self.fetch_usage():
            return
        
        # 3. 사용량 출력
        self.display_usage()
        
        print("\n💡 Tip: 'claude /status' 명령어로도 터미널에서 확인 가능합니다.\n")


def main():
    """메인 함수"""
    checker = ClaudeUsageChecker()
    checker.run()


if __name__ == "__main__":
    main()
