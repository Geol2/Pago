# -*- coding: utf-8 -*-
"""
저녁 뭐 먹지? - 저녁 메뉴 추천 프로그램

표준 라이브러리만 사용합니다. 실행:
    python dinner.py            # 대화형 메뉴
    python dinner.py --pick     # 바로 하나 추천
    python dinner.py --category 한식
"""

import argparse
import json
import os
import random
import sys
import time

# ----------------------------------------------------------------------------
# 메뉴 데이터 (카테고리별)
# ----------------------------------------------------------------------------
MENUS = {
    "한식": [
        "김치찌개", "된장찌개", "비빔밥", "불고기", "제육볶음", "삼겹살",
        "갈비탕", "순두부찌개", "냉면", "칼국수", "보쌈", "찜닭", "닭갈비",
        "낙지볶음", "김치볶음밥", "돼지국밥", "설렁탕", "감자탕",
    ],
    "중식": [
        "짜장면", "짬뽕", "탕수육", "마라탕", "마라샹궈", "양꼬치",
        "볶음밥", "깐풍기", "고추잡채", "유산슬", "꿔바로우",
    ],
    "일식": [
        "초밥", "라멘", "돈카츠", "우동", "규동", "오야코동",
        "사케동", "텐동", "오코노미야키", "야키토리", "장어덮밥",
    ],
    "양식": [
        "파스타", "피자", "스테이크", "햄버거", "리조또", "샐러드",
        "오므라이스", "그라탕", "수제버거", "타코",
    ],
    "분식": [
        "떡볶이", "라면", "김밥", "순대", "튀김", "쫄면", "라볶이",
        "치즈김밥", "참치김밥", "어묵",
    ],
    "치킨/야식": [
        "후라이드치킨", "양념치킨", "간장치킨", "족발", "보쌈",
        "곱창", "막창", "닭발", "피자", "치즈볼",
    ],
    "아시안": [
        "쌀국수", "팟타이", "분짜", "나시고렝", "카오팟", "똠양꿍",
        "월남쌈", "반미", "커리", "비리야니",
    ],
    "회식": [
        "삼겹살", "소고기구이", "한우오마카세", "갈비", "곱창전골", "막창구이",
        "양꼬치", "닭갈비", "보쌈", "족발", "회", "물회", "장어구이",
        "샤브샤브", "전골", "부대찌개", "닭볶음탕", "오리주물럭", "낙지볶음",
        "해물찜", "아구찜", "감자탕", "매운탕", "한정식", "초밥집",
        "피자&맥주", "치킨&맥주", "이자카야", "고깃집", "포차",
    ],
}

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".dinner_history.json")
HISTORY_LIMIT = 5  # 최근 N개는 다시 잘 안 나오게


# ----------------------------------------------------------------------------
# 히스토리 (최근 먹은 메뉴 기억 -> 연속 중복 줄이기)
# ----------------------------------------------------------------------------
def load_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def save_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history[-50:], f, ensure_ascii=False, indent=2)
    except OSError:
        pass  # 히스토리 저장 실패는 치명적이지 않으므로 무시


def remember(menu):
    history = load_history()
    history.append(menu)
    save_history(history)


# ----------------------------------------------------------------------------
# 추천 로직
# ----------------------------------------------------------------------------
def all_menus(categories=None):
    if categories:
        pool = []
        for c in categories:
            pool.extend(MENUS.get(c, []))
        return pool
    return [m for items in MENUS.values() for m in items]


def weighted_pick(categories=None):
    """최근에 먹은 메뉴는 뽑힐 확률을 낮춰서 추천."""
    pool = all_menus(categories)
    if not pool:
        return None
    recent = set(load_history()[-HISTORY_LIMIT:])
    weights = [0.15 if m in recent else 1.0 for m in pool]
    return random.choices(pool, weights=weights, k=1)[0]


def roulette(categories=None, spins=18):
    """돌림판 애니메이션 후 최종 메뉴 반환."""
    pool = all_menus(categories)
    if not pool:
        print("해당 카테고리에 메뉴가 없어요.")
        return None

    final = weighted_pick(categories)
    delay = 0.03
    for i in range(spins):
        candidate = random.choice(pool)
        # 마지막 몇 번은 최종 결과로 수렴
        if i >= spins - 3:
            candidate = final
        sys.stdout.write("\r  🍽  " + candidate + "                    ")
        sys.stdout.flush()
        time.sleep(delay)
        delay *= 1.18  # 점점 느려지는 효과
    print()
    return final


def announce(menu):
    if not menu:
        return
    print("\n" + "=" * 34)
    print(f"  오늘 저녁은 👉  {menu}  👈")
    print("=" * 34 + "\n")
    remember(menu)


# ----------------------------------------------------------------------------
# 대화형 메뉴
# ----------------------------------------------------------------------------
def interactive():
    cats = list(MENUS.keys())
    while True:
        print("\n🌙  저녁 뭐 먹지?")
        print("-" * 30)
        print("  0. 🎲 아무거나 (전체에서 랜덤)")
        for i, c in enumerate(cats, start=1):
            print(f"  {i}. {c}")
        print("  h. 최근 먹은 메뉴 보기")
        print("  q. 종료")

        choice = input("\n선택 > ").strip().lower()

        if choice in ("q", "quit", "exit"):
            print("맛있게 드세요! 👋")
            return
        if choice == "h":
            history = load_history()[-10:]
            if history:
                print("\n최근 먹은 메뉴: " + ", ".join(history))
            else:
                print("\n아직 기록이 없어요.")
            continue
        if choice == "0":
            announce(roulette())
        elif choice.isdigit() and 1 <= int(choice) <= len(cats):
            cat = cats[int(choice) - 1]
            announce(roulette([cat]))
        else:
            print("⚠  올바른 번호를 입력하세요.")
            continue

        again = input("다시 돌릴까요? (y/n) > ").strip().lower()
        if again not in ("y", "yes", ""):
            print("맛있게 드세요! 👋")
            return


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="저녁 메뉴를 골라주는 프로그램")
    parser.add_argument("--pick", action="store_true", help="바로 메뉴 하나 추천하고 종료")
    parser.add_argument("--category", "-c", nargs="+", metavar="카테고리",
                        help="카테고리 지정 (예: 한식 중식)")
    parser.add_argument("--list", action="store_true", help="카테고리 목록 출력")
    args = parser.parse_args()

    if args.list:
        for c, items in MENUS.items():
            print(f"[{c}] {', '.join(items)}")
        return

    if args.pick or args.category:
        announce(roulette(args.category))
        return

    try:
        interactive()
    except (KeyboardInterrupt, EOFError):
        print("\n맛있게 드세요! 👋")


if __name__ == "__main__":
    main()
