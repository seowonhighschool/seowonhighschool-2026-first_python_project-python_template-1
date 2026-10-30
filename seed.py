# seed.py
import sqlite3
import os
from dotenv import load_dotenv

import database

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "database.db")

# ─── 또래 비교 기준 데이터 ──────────────────────────────────────────────────────
# KOSIS 가계동향조사 기반 + 합리적 근사값
# 단위: 원 (월 평균 개인 지출)
#
# income_group 기준 (월 소득 근사):
#   low      → ~150만원 이하  (학생·아르바이트·최저임금)
#   mid-low  → 150~300만원   (사회초년생·중소기업)
#   mid-high → 300~500만원   (중견기업·공기업)
#   high     → 500만원 이상  (대기업·전문직·자영업 고소득)

# 표 형태로 정렬해 읽기 쉽게 유지한다 (그래서 줄 길이 제한을 이 블록에서만 끈다)
# pylint: disable=line-too-long
PEER_DATA = {
    "10대": {
        "low":      {"food":  60000, "cafe":  15000, "transport":  20000, "shopping":  30000, "medical":  10000, "leisure":  20000, "etc": 0},
        "mid-low":  {"food":  80000, "cafe":  25000, "transport":  30000, "shopping":  50000, "medical":  15000, "leisure":  35000, "etc": 0},
        "mid-high": {"food": 100000, "cafe":  35000, "transport":  40000, "shopping":  80000, "medical":  20000, "leisure":  55000, "etc": 0},
        "high":     {"food": 130000, "cafe":  50000, "transport":  55000, "shopping": 120000, "medical":  30000, "leisure":  80000, "etc": 0},
    },
    "20대초반": {
        "low":      {"food": 120000, "cafe":  25000, "transport":  40000, "shopping":  50000, "medical":  12000, "leisure":  30000, "etc": 0},
        "mid-low":  {"food": 150000, "cafe":  40000, "transport":  55000, "shopping":  80000, "medical":  18000, "leisure":  50000, "etc": 0},
        "mid-high": {"food": 180000, "cafe":  55000, "transport":  65000, "shopping": 120000, "medical":  25000, "leisure":  75000, "etc": 0},
        "high":     {"food": 220000, "cafe":  75000, "transport":  80000, "shopping": 180000, "medical":  40000, "leisure": 120000, "etc": 0},
    },
    "20대후반": {
        "low":      {"food": 150000, "cafe":  30000, "transport":  45000, "shopping":  60000, "medical":  15000, "leisure":  35000, "etc": 0},
        "mid-low":  {"food": 190000, "cafe":  45000, "transport":  60000, "shopping":  90000, "medical":  22000, "leisure":  55000, "etc": 0},
        "mid-high": {"food": 230000, "cafe":  60000, "transport":  75000, "shopping": 140000, "medical":  30000, "leisure":  85000, "etc": 0},
        "high":     {"food": 280000, "cafe":  85000, "transport": 100000, "shopping": 220000, "medical":  50000, "leisure": 140000, "etc": 0},
    },
    "30대초반": {
        "low":      {"food": 160000, "cafe":  25000, "transport":  50000, "shopping":  55000, "medical":  18000, "leisure":  30000, "etc": 0},
        "mid-low":  {"food": 200000, "cafe":  40000, "transport":  70000, "shopping":  85000, "medical":  28000, "leisure":  50000, "etc": 0},
        "mid-high": {"food": 250000, "cafe":  60000, "transport": 100000, "shopping": 140000, "medical":  40000, "leisure":  80000, "etc": 0},
        "high":     {"food": 320000, "cafe":  90000, "transport": 150000, "shopping": 240000, "medical":  65000, "leisure": 140000, "etc": 0},
    },
    "30대후반": {
        "low":      {"food": 170000, "cafe":  20000, "transport":  55000, "shopping":  50000, "medical":  22000, "leisure":  28000, "etc": 0},
        "mid-low":  {"food": 210000, "cafe":  35000, "transport":  80000, "shopping":  80000, "medical":  35000, "leisure":  48000, "etc": 0},
        "mid-high": {"food": 260000, "cafe":  55000, "transport": 110000, "shopping": 130000, "medical":  50000, "leisure":  80000, "etc": 0},
        "high":     {"food": 340000, "cafe":  80000, "transport": 160000, "shopping": 230000, "medical":  80000, "leisure": 140000, "etc": 0},
    },
    "40대": {
        "low":      {"food": 160000, "cafe":  15000, "transport":  50000, "shopping":  45000, "medical":  30000, "leisure":  25000, "etc": 0},
        "mid-low":  {"food": 210000, "cafe":  28000, "transport":  75000, "shopping":  75000, "medical":  50000, "leisure":  45000, "etc": 0},
        "mid-high": {"food": 270000, "cafe":  45000, "transport": 110000, "shopping": 130000, "medical":  75000, "leisure":  80000, "etc": 0},
        "high":     {"food": 350000, "cafe":  65000, "transport": 160000, "shopping": 230000, "medical": 120000, "leisure": 150000, "etc": 0},
    },
    "50대": {
        "low":      {"food": 140000, "cafe":  10000, "transport":  45000, "shopping":  40000, "medical":  45000, "leisure":  20000, "etc": 0},
        "mid-low":  {"food": 180000, "cafe":  20000, "transport":  65000, "shopping":  65000, "medical":  75000, "leisure":  40000, "etc": 0},
        "mid-high": {"food": 240000, "cafe":  35000, "transport":  95000, "shopping": 110000, "medical": 110000, "leisure":  70000, "etc": 0},
        "high":     {"food": 310000, "cafe":  50000, "transport": 140000, "shopping": 190000, "medical": 170000, "leisure": 130000, "etc": 0},
    },
    "60대이상": {
        "low":      {"food": 110000, "cafe":   8000, "transport":  30000, "shopping":  30000, "medical":  60000, "leisure":  15000, "etc": 0},
        "mid-low":  {"food": 150000, "cafe":  15000, "transport":  45000, "shopping":  50000, "medical": 100000, "leisure":  30000, "etc": 0},
        "mid-high": {"food": 200000, "cafe":  25000, "transport":  65000, "shopping":  85000, "medical": 150000, "leisure":  55000, "etc": 0},
        "high":     {"food": 260000, "cafe":  40000, "transport": 100000, "shopping": 150000, "medical": 220000, "leisure": 100000, "etc": 0},
    },
}


def seed():
    # app.py를 한 번도 띄우지 않은 상태에서 실행해도 되도록 테이블을 먼저 보장한다
    database.init_db()

    conn = sqlite3.connect(DB_PATH)
    rows = [
        (age_group, income_group, category, avg_amount)
        for age_group, income_groups in PEER_DATA.items()
        for income_group, categories in income_groups.items()
        for category, avg_amount in categories.items()
    ]

    conn.executemany(
        """
        INSERT OR REPLACE INTO peer_averages (age_group, income_group, category, avg_amount)
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()
    print(f"[seed] {len(rows)}개 데이터 삽입 완료 "
          f"({len(PEER_DATA)}개 나이 그룹 × 4개 소득 그룹 × 7개 카테고리)")


if __name__ == "__main__":
    seed()
