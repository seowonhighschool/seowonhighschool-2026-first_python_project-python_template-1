import hashlib
import hmac
import os
import random
import secrets
import sqlite3
from contextlib import closing
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv


# ============================================================
# Life of Booster - 건강 습관 코칭 앱
#
# 실행: streamlit run app.py
#
# 화면 구성 (서비스 흐름도 기준)
#   1. 인증 및 온보딩 : 가입/로그인 → 건강 데이터 동의 → 건강 프로필 → 맞춤 시작 계획
#   2. 홈 및 목표 관리 : 홈 대시보드(연속 달성 · 목표 진행률 · 맞춤 추천 수락/거절) · 목표 설정 · 알림함
#   3. 생활 데이터 기록 : 수면 · 운동(계획 → 실천 가이드 → 기록) · 식단 · 기기 연동 (최근 7일 수정)
#   4. 게임화 및 보상 : 목표 달성 보상 · 차감 안내 · 유예권 · 포인트 상점 · 보상/배지 이력
#      카메라 챌린지 : 푸시업·스쿼트 개수 자동 인식 · 주간 랭킹 · 도전장 대결
#   5. 주간 리포트 : 기본 리포트 · 심화 리포트(유료)
#   6. 구독 및 결제 : 구독 안내 → 결제 → 성공/실패 · 구독 관리/해지
#   7. 설정 : 알림(방해 금지 시간) · 프로필 수정 · 동의 내역/철회 · 보상 설정
#   + 관리자 : 핵심 지표 (.env의 ADMIN_EMAILS에 등록된 계정만)
# ============================================================

st.set_page_config(
    page_title="Life of Booster",
    page_icon="🚀",
    layout="wide"
)

BASE_DIR = Path(__file__).resolve().parent

# 어느 폴더에서 실행하든 app.py 옆의 .env / DB 파일을 사용
load_dotenv(BASE_DIR / ".env")

DB_PATH = BASE_DIR / "life_of_booster.db"

DISCLAIMER = (
    "⚠️ Life of Booster의 추천은 일반적인 생활 습관 안내이며 "
    "의학적 진단이나 치료를 대신하지 않습니다. "
    "질환이 있거나 몸에 이상이 느껴지면 전문가와 상담하세요."
)


# ============================================================
# 기준 데이터
# ============================================================

GENDERS = ["선택 안 함", "여성", "남성"]

ACTIVITY_LEVELS = ["거의 앉아서 지내요", "가끔 움직여요", "자주 움직여요"]

GOAL_TYPES = [
    "체중·식단 관리",
    "운동 습관·체력 향상",
    "건강관리 처음 시작",
    "생활 활력 찾기"
]

MEAL_TYPES = ["아침", "점심", "저녁", "간식"]

INTENSITIES = ["가볍게", "보통", "힘들게"]

DEVICE_TYPES = ["휴대폰 만보기", "스마트워치", "스마트 밴드"]

# (항목 코드, 이름, 필수 여부, 설명)
CONSENT_ITEMS = [
    (
        "terms",
        "서비스 이용약관 동의",
        True,
        "Life of Booster 서비스를 이용하기 위한 기본 약관입니다."
    ),
    (
        "health_data",
        "건강·생활 데이터 수집 및 이용 동의",
        True,
        "신체 정보, 수면·운동·식사·걸음 수 기록을 맞춤 추천과 리포트에만 사용합니다."
    ),
    (
        "ai_transfer",
        "AI 분석을 위한 외부 전송 동의",
        False,
        "AI 코칭을 받을 때 이름·이메일·메모를 뺀 '수치 요약'만 외부 AI 서비스로 보냅니다."
    ),
    (
        "marketing",
        "혜택·이벤트 알림 수신 동의",
        False,
        "새 기능이나 이벤트 소식을 알려 드립니다."
    )
]

REQUIRED_CONSENTS = [item[0] for item in CONSENT_ITEMS if item[2]]

EXERCISES = {
    "walk": {
        "name": "🚶 빠르게 걷기",
        "base": 20,
        "guide": [
            "허리를 펴고 시선은 정면을 봐요.",
            "팔을 가볍게 흔들며 평소보다 조금 빠르게 걸어요.",
            "숨이 약간 차지만 대화는 할 수 있는 속도를 유지해요.",
            "마지막 3분은 천천히 걸으며 정리해요."
        ]
    },
    "jog": {
        "name": "🏃 가벼운 달리기",
        "base": 20,
        "guide": [
            "5분 동안 걸으며 몸을 데워요.",
            "보폭을 작게 하고 천천히 달리기 시작해요.",
            "숨이 너무 차면 걷기로 바꿔도 괜찮아요.",
            "마지막 5분은 걸으면서 숨을 고르세요."
        ]
    },
    "bodyweight": {
        "name": "💪 맨몸 근력 운동",
        "base": 15,
        "guide": [
            "스쿼트 15회: 의자에 앉듯이 천천히 앉았다 일어나요.",
            "팔굽혀펴기 10회: 힘들면 무릎을 대거나 벽을 짚고 해요.",
            "플랭크 20~30초: 머리부터 발끝까지 일직선을 유지해요.",
            "위 동작을 2~3번 반복하고, 사이에 1분씩 쉬어요."
        ]
    },
    "stretch": {
        "name": "🧘 전신 스트레칭",
        "base": 10,
        "guide": [
            "목을 천천히 좌우로 기울이며 10초씩 늘려요.",
            "팔을 머리 위로 뻗어 옆구리를 늘려요.",
            "다리를 앞으로 뻗고 허리를 숙여 허벅지 뒤를 늘려요.",
            "반동 없이 천천히, 아프지 않을 만큼만 해요."
        ]
    },
    "stairs": {
        "name": "🏢 계단 오르기",
        "base": 10,
        "guide": [
            "난간을 잡을 수 있는 계단을 골라요.",
            "한 계단씩 발 전체로 디디며 올라가요.",
            "내려올 때는 무릎에 무리가 가지 않게 천천히 내려와요.",
            "숨이 차면 층마다 잠깐 쉬어요."
        ]
    }
}

WORKOUT_PLANS = {
    "체중·식단 관리": ["walk", "bodyweight", "stretch"],
    "운동 습관·체력 향상": ["jog", "bodyweight", "stretch"],
    "건강관리 처음 시작": ["walk", "stretch"],
    "생활 활력 찾기": ["walk", "stairs", "stretch"]
}

MEAL_PLANS = {
    "체중·식단 관리": {
        "아침": "그릭요거트 + 과일 + 견과류 한 줌",
        "점심": "잡곡밥 반 공기 + 생선이나 닭가슴살 + 나물 반찬",
        "저녁": "두부 채소 샐러드 + 삶은 달걀",
        "간식": "방울토마토나 오이"
    },
    "운동 습관·체력 향상": {
        "아침": "통곡물 빵 + 달걀 2개 + 우유",
        "점심": "잡곡밥 + 소고기나 닭고기 + 채소",
        "저녁": "현미밥 + 연어나 두부 + 채소",
        "간식": "바나나 + 우유나 두유"
    },
    "건강관리 처음 시작": {
        "아침": "거르지 않기! 바나나 + 우유 한 잔",
        "점심": "평소 식사에 채소 반찬 하나 더",
        "저녁": "밥은 평소보다 조금 적게, 국물은 덜 먹기",
        "간식": "과자 대신 과일 한 조각"
    },
    "생활 활력 찾기": {
        "아침": "오트밀 + 베리류 + 견과류",
        "점심": "채소가 많은 비빔밥 한 그릇",
        "저녁": "생선구이 + 된장국 + 나물",
        "간식": "견과류 한 줌 + 물 한 잔"
    }
}

# 시연용 예시 가격 (계획서에 가격이 없어 임시로 정함)
SUBSCRIPTION_PLANS = {
    "monthly": {"name": "월간 구독", "price": 4900, "days": 30},
    "yearly": {"name": "연간 구독", "price": 49000, "days": 365},
    # 포인트 상점 체험권 (결제 상품 아님)
    "trial": {"name": "7일 체험권", "price": 0, "days": 7}
}

PAID_PLANS = [key for key, plan in SUBSCRIPTION_PLANS.items() if plan["price"] > 0]

PREMIUM_BENEFITS = [
    "📈 심화 주간 리포트 (지난주 비교, 습관별 달성률, 요일별 흐름)",
    "😴 수면과 기분의 관계 분석",
    "🤖 AI 심화 코칭",
    "🏅 구독자 전용 배지"
]

LEVELS = [
    (1, "🌱 새싹", 0),
    (2, "🌿 성장 중", 100),
    (3, "🌳 습관 형성", 250),
    (4, "🚀 부스터", 500),
    (5, "🏆 생활의 달인", 1000)
]

HABIT_LABELS = {
    "steps": "🚶 걸음 수",
    "sleep_hours": "😴 수면",
    "water_ml": "💧 물 섭취",
    "exercise_min": "🏃 운동",
    "meals": "🥗 식사 기록",
    "mood": "🙂 기분"
}

SCORE_WEIGHTS = {
    "steps": 0.20,
    "sleep_hours": 0.20,
    "water_ml": 0.10,
    "exercise_min": 0.25,
    "meals": 0.15,
    "mood": 0.10
}

# 생활 점수가 이 점수 이상이면 '목표 달성일'
ACHIEVED_SCORE = 60

WORKOUT_MISS_PENALTY = 10

WEEKDAYS_KO = "월화수목금토일"

# 기록은 최근 7일 안에서만 입력·수정 가능
EDIT_WINDOW_DAYS = 7

# 실천 알림은 하루 최대 5번, 방해 금지 시간에는 보내지 않음
MAX_REMINDERS_PER_DAY = 5

# 포인트 상점
SHOP_ITEMS = {
    "grace": {
        "name": "🛡️ 유예권",
        "price": 100,
        "description": "목표를 못 지킨 날, 연속 달성 기록을 지켜 주고 포인트 차감도 막아 줘요."
    },
    "premium_trial": {
        "name": "💎 부스터 플러스 7일 체험권",
        "price": 500,
        "description": "심화 리포트와 AI 심화 코칭을 7일 동안 써 볼 수 있어요."
    }
}

RECOMMENDATION_REJECT_REASONS = [
    "선택 안 함",
    "시간이 없어요",
    "너무 힘들어요",
    "너무 쉬워요",
    "지금 목표가 좋아요",
    "기타"
]

# 카메라 챌린지
CHALLENGE_EXERCISES = {
    "pushup": {
        "name": "💪 푸시업",
        "how": "카메라 옆쪽에서 몸 전체(머리~발)가 옆모습으로 보이게 엎드려 주세요."
    },
    "squat": {
        "name": "🦵 스쿼트",
        "how": "카메라에서 2~3걸음 떨어져, 몸 전체가 옆모습이나 정면으로 보이게 서 주세요."
    }
}

CHALLENGE_DURATIONS = [30, 60]

DUEL_DAYS = 7


# ============================================================
# 데이터베이스
# ============================================================

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def fetch_one(sql, params=()):
    with closing(connect()) as conn:
        return conn.execute(sql, params).fetchone()


def fetch_all(sql, params=()):
    with closing(connect()) as conn:
        return conn.execute(sql, params).fetchall()


def execute(sql, params=()):
    """실행 후 바뀐 행 수를 돌려준다."""
    with closing(connect()) as conn, conn:
        return conn.execute(sql, params).rowcount


def read_df(sql, params=()):
    with closing(connect()) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def initialize_database():

    with closing(connect()) as conn, conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS consents (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                item TEXT NOT NULL,
                agreed INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, item)
            );

            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                gender TEXT NOT NULL,
                birth_year INTEGER NOT NULL,
                height_cm REAL NOT NULL,
                weight_kg REAL NOT NULL,
                activity_level TEXT NOT NULL,
                goal_type TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS goals (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                steps INTEGER NOT NULL,
                sleep_hours REAL NOT NULL,
                water_ml INTEGER NOT NULL,
                exercise_min INTEGER NOT NULL,
                meals INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS daily_status (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                log_date TEXT NOT NULL,
                steps INTEGER,
                water_ml INTEGER NOT NULL DEFAULT 0,
                mood INTEGER,
                PRIMARY KEY (user_id, log_date)
            );

            CREATE TABLE IF NOT EXISTS sleep_logs (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                log_date TEXT NOT NULL,
                bed_time TEXT NOT NULL,
                wake_time TEXT NOT NULL,
                hours REAL NOT NULL,
                quality INTEGER NOT NULL,
                PRIMARY KEY (user_id, log_date)
            );

            CREATE TABLE IF NOT EXISTS workout_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                log_date TEXT NOT NULL,
                kind TEXT NOT NULL,
                minutes INTEGER NOT NULL,
                intensity TEXT NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS meal_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                log_date TEXT NOT NULL,
                meal_type TEXT NOT NULL,
                menu TEXT NOT NULL,
                calories INTEGER,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reward_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                event_date TEXT NOT NULL,
                code TEXT NOT NULL,
                title TEXT NOT NULL,
                xp INTEGER NOT NULL,
                points INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (user_id, event_date, code)
            );

            CREATE TABLE IF NOT EXISTS user_badges (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                badge_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                earned_date TEXT NOT NULL,
                PRIMARY KEY (user_id, badge_id)
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                plan TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                canceled_at TEXT
            );

            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                plan TEXT NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                notify_enabled INTEGER NOT NULL DEFAULT 1,
                remind_time TEXT NOT NULL DEFAULT '21:00',
                remind_sleep INTEGER NOT NULL DEFAULT 1,
                remind_workout INTEGER NOT NULL DEFAULT 1,
                remind_meal INTEGER NOT NULL DEFAULT 1,
                penalty_enabled INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS devices (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                device_type TEXT NOT NULL,
                connected INTEGER NOT NULL,
                last_sync TEXT
            );

            CREATE TABLE IF NOT EXISTS activity_events (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                event TEXT NOT NULL,
                event_date TEXT NOT NULL,
                PRIMARY KEY (user_id, event, event_date)
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                kind TEXT NOT NULL,
                message TEXT NOT NULL,
                target TEXT NOT NULL,
                notify_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS user_items (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                item TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, item)
            );

            CREATE TABLE IF NOT EXISTS grace_used (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                used_date TEXT NOT NULL,
                PRIMARY KEY (user_id, used_date)
            );

            CREATE TABLE IF NOT EXISTS recommendation_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                feedback_date TEXT NOT NULL,
                title TEXT NOT NULL,
                action TEXT NOT NULL,
                reason TEXT
            );

            CREATE TABLE IF NOT EXISTS challenge_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                exercise TEXT NOT NULL,
                duration INTEGER NOT NULL,
                reps INTEGER NOT NULL,
                record_date TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS duels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                to_user INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                exercise TEXT NOT NULL,
                duration INTEGER NOT NULL,
                target_reps INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                result_reps INTEGER,
                created_at TEXT NOT NULL,
                resolved_at TEXT
            );
        """)

        # 이전 버전 DB에 새 설정 칸 추가
        ensure_column(conn, "user_settings", "quiet_start", "TEXT NOT NULL DEFAULT '23:00'")
        ensure_column(conn, "user_settings", "quiet_end", "TEXT NOT NULL DEFAULT '07:00'")
        ensure_column(conn, "user_settings", "auto_grace", "INTEGER NOT NULL DEFAULT 1")
        ensure_column(conn, "user_settings", "show_in_ranking", "INTEGER NOT NULL DEFAULT 1")


def ensure_column(conn, table, column, definition):

    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}

    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


initialize_database()


def today_str():
    return date.today().isoformat()


def now_str():
    return datetime.now().isoformat(timespec="seconds")


# ============================================================
# 화면 공통
# ============================================================

st.markdown("""
<style>
div[data-testid="stMetric"] {
    border: 1px solid rgba(128, 128, 128, 0.25);
    padding: 15px;
    border-radius: 15px;
}
</style>
""", unsafe_allow_html=True)


def flash(message, kind="success"):
    """st.rerun()이나 화면 이동 뒤에도 보이도록 메시지를 저장해 둔다."""
    st.session_state["flash"] = (kind, message)


def show_flash():
    kind, message = st.session_state.pop("flash", (None, None))
    if message:
        getattr(st, kind)(message)


# ============================================================
# 회원 · 로그인
# ============================================================

def admin_emails():
    return {
        email.strip().lower()
        for email in os.getenv("ADMIN_EMAILS", "").split(",")
        if email.strip()
    }


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        200_000
    ).hex()


def create_user(name, email, password):

    salt = secrets.token_hex(16)

    with closing(connect()) as conn, conn:
        cursor = conn.execute("""
            INSERT INTO users (email, name, password_hash, salt, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (email, name, hash_password(password, salt), salt, now_str()))

    return cursor.lastrowid


def authenticate(email, password):

    user = fetch_one(
        "SELECT * FROM users WHERE email = ?",
        (email.strip().lower(),)
    )

    if user is None:
        return None

    if not hmac.compare_digest(
        user["password_hash"],
        hash_password(password, user["salt"])
    ):
        return None

    return user


def get_user(user_id):
    return fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))


def current_user():

    user_id = st.session_state.get("user_id")

    if user_id is None:
        return None

    user = get_user(user_id)

    if user is None:
        st.session_state.clear()

    return user


def is_admin(user):
    return user["email"] in admin_emails()


def log_event(user_id, event):
    """오늘 처음 남긴 기록이면 True."""
    return execute("""
        INSERT OR IGNORE INTO activity_events (user_id, event, event_date)
        VALUES (?, ?, ?)
    """, (user_id, event, today_str())) == 1


def login(user_id):
    st.session_state.clear()
    st.session_state["user_id"] = user_id
    log_event(user_id, "login")


def logout():
    st.session_state.clear()
    st.rerun()


# ============================================================
# 동의
# ============================================================

def get_consents(user_id):

    rows = fetch_all(
        "SELECT item, agreed, updated_at FROM consents WHERE user_id = ?",
        (user_id,)
    )

    return {row["item"]: row for row in rows}


def has_consent(user_id, item):
    row = get_consents(user_id).get(item)
    return row is not None and row["agreed"] == 1


def required_consents_ok(user_id):
    return all(has_consent(user_id, item) for item in REQUIRED_CONSENTS)


def save_consent(user_id, item, agreed):
    execute("""
        INSERT INTO consents (user_id, item, agreed, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, item)
        DO UPDATE SET agreed = excluded.agreed, updated_at = excluded.updated_at
    """, (user_id, item, int(agreed), now_str()))


def delete_health_data(user_id):
    """필수 동의 철회 시 건강·생활 데이터를 모두 지운다."""

    with closing(connect()) as conn, conn:
        for table in [
            "profiles",
            "goals",
            "daily_status",
            "sleep_logs",
            "workout_logs",
            "meal_logs",
            "devices",
            "challenge_records",
            "grace_used",
            "recommendation_feedback"
        ]:
            conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))

        conn.execute(
            "DELETE FROM duels WHERE from_user = ? OR to_user = ?",
            (user_id, user_id)
        )


# ============================================================
# 프로필 · 목표
# ============================================================

def get_profile(user_id):
    return fetch_one("SELECT * FROM profiles WHERE user_id = ?", (user_id,))


def save_profile(user_id, profile):
    execute("""
        INSERT INTO profiles
        (user_id, gender, birth_year, height_cm, weight_kg,
         activity_level, goal_type, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            gender = excluded.gender,
            birth_year = excluded.birth_year,
            height_cm = excluded.height_cm,
            weight_kg = excluded.weight_kg,
            activity_level = excluded.activity_level,
            goal_type = excluded.goal_type,
            updated_at = excluded.updated_at
    """, (
        user_id,
        profile["gender"],
        profile["birth_year"],
        profile["height_cm"],
        profile["weight_kg"],
        profile["activity_level"],
        profile["goal_type"],
        now_str()
    ))


def starter_goals(profile):
    """건강 프로필로 맞춤 시작 목표를 만든다."""

    steps = {
        ACTIVITY_LEVELS[0]: 5000,
        ACTIVITY_LEVELS[1]: 7000,
        ACTIVITY_LEVELS[2]: 9000
    }[profile["activity_level"]]

    exercise = {
        "체중·식단 관리": 30,
        "운동 습관·체력 향상": 40,
        "건강관리 처음 시작": 15,
        "생활 활력 찾기": 20
    }[profile["goal_type"]]

    # 평소 거의 안 움직이면 부담 없게 시작
    if profile["activity_level"] == ACTIVITY_LEVELS[0]:
        exercise = max(10, exercise - 10)

    age = date.today().year - profile["birth_year"]

    if age < 18:
        sleep_hours = 8.5
    elif age < 65:
        sleep_hours = 7.5
    else:
        sleep_hours = 7.0

    water = round(profile["weight_kg"] * 30 / 100) * 100
    water = max(1200, min(3000, water))

    return {
        "steps": steps,
        "sleep_hours": sleep_hours,
        "water_ml": water,
        "exercise_min": exercise,
        "meals": 3
    }


DEFAULT_GOALS = {
    "steps": 7000,
    "sleep_hours": 7.5,
    "water_ml": 1500,
    "exercise_min": 20,
    "meals": 3
}


def get_goals(user_id):

    row = fetch_one("SELECT * FROM goals WHERE user_id = ?", (user_id,))

    if row is None:
        return dict(DEFAULT_GOALS)

    return {key: row[key] for key in DEFAULT_GOALS}


def save_goals(user_id, goals):
    execute("""
        INSERT INTO goals
        (user_id, steps, sleep_hours, water_ml, exercise_min, meals, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            steps = excluded.steps,
            sleep_hours = excluded.sleep_hours,
            water_ml = excluded.water_ml,
            exercise_min = excluded.exercise_min,
            meals = excluded.meals,
            updated_at = excluded.updated_at
    """, (
        user_id,
        goals["steps"],
        goals["sleep_hours"],
        goals["water_ml"],
        goals["exercise_min"],
        goals["meals"],
        now_str()
    ))


def get_settings(user_id):

    execute(
        "INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)",
        (user_id,)
    )

    return fetch_one("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))


# ============================================================
# 생활 기록
# ============================================================

def update_daily_status(user_id, log_date, **fields):

    execute("""
        INSERT OR IGNORE INTO daily_status (user_id, log_date)
        VALUES (?, ?)
    """, (user_id, str(log_date)))

    columns = ", ".join(f"{name} = ?" for name in fields)

    execute(
        f"UPDATE daily_status SET {columns} WHERE user_id = ? AND log_date = ?",
        (*fields.values(), user_id, str(log_date))
    )


def add_water(user_id, amount):

    execute("""
        INSERT OR IGNORE INTO daily_status (user_id, log_date)
        VALUES (?, ?)
    """, (user_id, today_str()))

    execute("""
        UPDATE daily_status
        SET water_ml = water_ml + ?
        WHERE user_id = ? AND log_date = ?
    """, (amount, user_id, today_str()))


def get_daily_status(user_id, log_date):
    return fetch_one(
        "SELECT * FROM daily_status WHERE user_id = ? AND log_date = ?",
        (user_id, str(log_date))
    )


def sleep_duration(bed_time, wake_time):
    """취침·기상 시각으로 수면 시간을 계산 (자정을 넘겨도 계산됨)."""

    bed = bed_time.hour * 60 + bed_time.minute
    wake = wake_time.hour * 60 + wake_time.minute

    return round(((wake - bed) % (24 * 60)) / 60, 1)


def save_sleep(user_id, log_date, bed_time, wake_time, quality):
    execute("""
        INSERT INTO sleep_logs
        (user_id, log_date, bed_time, wake_time, hours, quality)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, log_date)
        DO UPDATE SET
            bed_time = excluded.bed_time,
            wake_time = excluded.wake_time,
            hours = excluded.hours,
            quality = excluded.quality
    """, (
        user_id,
        str(log_date),
        bed_time.strftime("%H:%M"),
        wake_time.strftime("%H:%M"),
        sleep_duration(bed_time, wake_time),
        quality
    ))


def editable_dates():
    """기록을 입력·수정할 수 있는 날짜 범위 (최근 7일)."""
    return date.today() - timedelta(days=EDIT_WINDOW_DAYS - 1), date.today()


def date_picker(label, key):

    first, last = editable_dates()

    return st.date_input(
        label,
        value=last,
        min_value=first,
        max_value=last,
        key=key,
        help=f"기록은 최근 {EDIT_WINDOW_DAYS}일 안에서만 입력·수정할 수 있어요."
    )


def add_workout(user_id, log_date, kind, minutes, intensity, note):
    execute("""
        INSERT INTO workout_logs
        (user_id, log_date, kind, minutes, intensity, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, str(log_date), kind, minutes, intensity, note, now_str()))


def workout_minutes(user_id, log_date):

    row = fetch_one("""
        SELECT COALESCE(SUM(minutes), 0) AS total
        FROM workout_logs
        WHERE user_id = ? AND log_date = ?
    """, (user_id, str(log_date)))

    return row["total"]


def add_meal(user_id, log_date, meal_type, menu, calories):
    execute("""
        INSERT INTO meal_logs
        (user_id, log_date, meal_type, menu, calories, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, str(log_date), meal_type, menu, calories, now_str()))


# ============================================================
# 생활 점수 · 일별 요약
# ============================================================

def clamp(value):
    return max(0, min(100, value))


def habit_rates(day, goals):
    """습관별 목표 달성률 (0~100)."""

    sleep = day["sleep_hours"]
    mood = day["mood"]

    if pd.isna(mood):
        mood = 3

    return {
        "steps": clamp(day["steps"] / goals["steps"] * 100),
        # 수면은 목표보다 적어도, 지나치게 많아도 감점 (기록 없으면 0)
        "sleep_hours": clamp(100 - abs(sleep - goals["sleep_hours"]) * 25) if sleep > 0 else 0,
        "water_ml": clamp(day["water_ml"] / goals["water_ml"] * 100),
        "exercise_min": clamp(day["exercise_min"] / goals["exercise_min"] * 100),
        "meals": clamp(day["meals"] / goals["meals"] * 100),
        "mood": clamp(mood / 5 * 100)
    }


def calculate_score(day, goals):

    rates = habit_rates(day, goals)

    return round(sum(rates[key] * weight for key, weight in SCORE_WEIGHTS.items()), 1)


def daily_summary(user_id, start, end, goals):
    """start~end 날짜별로 모든 기록을 합친 표 (기록 없는 날도 포함)."""

    where = "WHERE user_id = ? AND log_date BETWEEN ? AND ?"
    params = (user_id, str(start), str(end))

    parts = [
        read_df(
            f"SELECT log_date, steps, water_ml, mood FROM daily_status {where}",
            params
        ),
        read_df(
            f"SELECT log_date, hours AS sleep_hours, quality AS sleep_quality "
            f"FROM sleep_logs {where}",
            params
        ),
        read_df(
            f"SELECT log_date, SUM(minutes) AS exercise_min "
            f"FROM workout_logs {where} GROUP BY log_date",
            params
        ),
        read_df(
            f"SELECT log_date, COUNT(DISTINCT meal_type) AS meals "
            f"FROM meal_logs {where} GROUP BY log_date",
            params
        )
    ]

    df = pd.DataFrame({
        "log_date": [day.isoformat() for day in pd.date_range(start, end).date]
    })

    recorded = set()

    for part in parts:
        recorded.update(part["log_date"])
        df = df.merge(part, on="log_date", how="left")

    df["recorded"] = df["log_date"].isin(recorded)

    for column in ["steps", "water_ml", "sleep_hours", "exercise_min", "meals"]:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    for column in ["mood", "sleep_quality"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df["score"] = [calculate_score(day, goals) for day in df.to_dict("records")]

    df["log_date"] = pd.to_datetime(df["log_date"])

    return df


def today_summary(user_id, goals):
    return daily_summary(user_id, date.today(), date.today(), goals).iloc[0].to_dict()


def get_streak(user_id, goals, until=None):
    """생활 점수 60점 이상인 날(또는 유예권을 쓴 날)이 이어진 일수.
    until을 주지 않으면 오늘 기준이며, 오늘 아직 달성 전이면 어제까지의 연속 기록을 유지한다."""

    end = until or date.today()

    df = daily_summary(user_id, end - timedelta(days=365), end, goals)

    achieved = set(df.loc[df["score"] >= ACHIEVED_SCORE, "log_date"].dt.date)

    achieved.update(
        date.fromisoformat(row["used_date"])
        for row in fetch_all(
            "SELECT used_date FROM grace_used WHERE user_id = ?", (user_id,)
        )
    )

    current = end

    if until is None and current not in achieved:
        current -= timedelta(days=1)

    streak = 0

    while current in achieved:
        streak += 1
        current -= timedelta(days=1)

    return streak


# ============================================================
# 보상 · 차감 · 레벨 · 배지
# ============================================================

def get_progress(user_id):

    row = fetch_one("""
        SELECT COALESCE(SUM(xp), 0) AS xp, COALESCE(SUM(points), 0) AS points
        FROM reward_events
        WHERE user_id = ?
    """, (user_id,))

    return row["xp"], row["points"]


def give_reward(user_id, code, title, xp, points, event_date=None):
    """같은 날 같은 보상은 한 번만 지급. 새로 지급했으면 True."""

    return execute("""
        INSERT OR IGNORE INTO reward_events
        (user_id, event_date, code, title, xp, points, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        str(event_date or date.today()),
        code,
        title,
        xp,
        points,
        now_str()
    )) == 1


def apply_penalty(user_id, code, title, points, event_date):
    """포인트 차감 (0점 아래로는 내려가지 않음). 새로 차감했으면 차감한 점수."""

    _, total_points = get_progress(user_id)

    amount = min(points, total_points)

    if give_reward(user_id, code, title, 0, -amount, event_date):
        return amount

    return None


def get_item(user_id, item):

    row = fetch_one(
        "SELECT quantity FROM user_items WHERE user_id = ? AND item = ?",
        (user_id, item)
    )

    return row["quantity"] if row else 0


def change_item(user_id, item, amount):
    execute("""
        INSERT INTO user_items (user_id, item, quantity)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, item)
        DO UPDATE SET quantity = quantity + excluded.quantity
    """, (user_id, item, amount))


def settle_yesterday(user_id, goals, settings):
    """하루 한 번, 어제 결과를 정산한다.
    - 어제 목표 미달성 + 지킬 연속 기록이 있으면 → 유예권 자동 사용 (차감도 면제)
    - 그렇지 않고 운동 목표를 못 채웠으면 → 포인트 조금 차감 (설정에서 끌 수 있음)"""

    if not log_event(user_id, "settle"):
        return

    yesterday = date.today() - timedelta(days=1)

    joined = datetime.fromisoformat(get_user(user_id)["created_at"]).date()

    if joined > yesterday:
        return

    day = daily_summary(user_id, yesterday, yesterday, goals).iloc[0]

    if (
        day["score"] < ACHIEVED_SCORE
        and settings["auto_grace"]
        and get_item(user_id, "grace") > 0
        and get_streak(user_id, goals, until=yesterday - timedelta(days=1)) > 0
    ):
        change_item(user_id, "grace", -1)

        execute(
            "INSERT OR IGNORE INTO grace_used (user_id, used_date) VALUES (?, ?)",
            (user_id, yesterday.isoformat())
        )

        notify(
            user_id,
            "grace",
            f"🛡️ {yesterday:%m월 %d일} 목표를 놓쳤지만 유예권 1장으로 연속 달성 기록을 지켰어요.",
            "rewards"
        )
        return

    if not settings["penalty_enabled"]:
        return

    if workout_minutes(user_id, yesterday) >= goals["exercise_min"]:
        return

    amount = apply_penalty(
        user_id,
        "workout_miss",
        "😢 운동 목표 미달성",
        WORKOUT_MISS_PENALTY,
        yesterday
    )

    if amount:
        notify(
            user_id,
            "penalty",
            f"😢 {yesterday:%m월 %d일} 운동 목표를 놓쳐서 포인트 {amount}점이 차감됐어요. "
            "포인트 상점의 유예권이 있으면 다음부터 막을 수 있어요.",
            "rewards"
        )


def buy_item(user_id, item_key):
    """포인트로 상점 물건을 산다. 성공하면 True."""

    item = SHOP_ITEMS[item_key]

    _, points = get_progress(user_id)

    if points < item["price"]:
        return False

    give_reward(
        user_id,
        f"shop_{item_key}_{secrets.token_hex(4)}",
        f"🛒 구매: {item['name']}",
        0,
        -item["price"]
    )

    if item_key == "premium_trial":
        extend_premium(user_id, SUBSCRIPTION_PLANS["trial"]["days"])
    else:
        change_item(user_id, item_key, 1)

    return True


# ============================================================
# 알림 (앱 안 알림함 · 휴대폰 알림 흉내)
# ============================================================

def notify(user_id, kind, message, target="home"):
    execute("""
        INSERT INTO notifications
        (user_id, kind, message, target, notify_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, kind, message, target, today_str(), now_str()))


def unread_count(user_id):
    return fetch_one(
        "SELECT COUNT(*) AS n FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,)
    )["n"]


def in_quiet_hours(settings, moment):
    """방해 금지 시간인지 (자정을 넘기는 시간대도 처리)."""

    start = time.fromisoformat(settings["quiet_start"])
    end = time.fromisoformat(settings["quiet_end"])

    if start <= end:
        return start <= moment < end

    return moment >= start or moment < end


def generate_reminders(user_id, settings, goals):
    """알림 시각이 지났는데 기록이 비어 있으면 실천 알림을 보낸다.
    종류마다 하루 한 번, 전체 하루 최대 5번, 방해 금지 시간에는 보내지 않는다."""

    if not settings["notify_enabled"]:
        return

    now = datetime.now()

    if in_quiet_hours(settings, now.time()):
        return

    if now.time() < time.fromisoformat(settings["remind_time"]):
        return

    sent = {
        row["kind"]
        for row in fetch_all(
            "SELECT kind FROM notifications WHERE user_id = ? AND notify_date = ? AND kind LIKE 'remind_%'",
            (user_id, today_str())
        )
    }

    today = today_summary(user_id, goals)

    candidates = [
        (
            "remind_sleep",
            settings["remind_sleep"] and today["sleep_hours"] == 0,
            "😴 어젯밤 수면 기록이 아직 비어 있어요.",
            "sleep"
        ),
        (
            "remind_workout",
            settings["remind_workout"] and today["exercise_min"] < goals["exercise_min"],
            f"🏃 오늘 운동 목표까지 {goals['exercise_min'] - today['exercise_min']:.0f}분 남았어요. 10분만 움직여 볼까요?",
            "workout"
        ),
        (
            "remind_meal",
            settings["remind_meal"] and today["meals"] == 0,
            "🥗 오늘 식사 기록이 아직 없어요.",
            "meal"
        )
    ]

    new_messages = []

    for kind, needed, message, target in candidates:

        if len(sent) >= MAX_REMINDERS_PER_DAY:
            break

        if needed and kind not in sent:
            notify(user_id, kind, message, target)
            sent.add(kind)
            new_messages.append(message)

    # 휴대폰 알림처럼 화면 구석에 잠깐 띄움
    for message in new_messages:
        st.toast(message, icon="🔔")


def check_perfect_day(user_id, goals):
    """오늘 모든 목표를 채우면 추가 보상."""

    rates = habit_rates(today_summary(user_id, goals), goals)

    keys = ["steps", "sleep_hours", "water_ml", "exercise_min", "meals"]

    if all(rates[key] >= 100 for key in keys):
        if give_reward(user_id, "perfect_day", "🌟 모든 목표 달성", 30, 50):
            st.balloons()


def get_level(xp):
    """(레벨, 이름, 현재 레벨 시작 경험치, 다음 레벨 경험치 또는 None)"""

    for index in range(len(LEVELS) - 1, -1, -1):

        level, name, start_xp = LEVELS[index]

        if xp >= start_xp:
            next_xp = LEVELS[index + 1][2] if index + 1 < len(LEVELS) else None
            return level, name, start_xp, next_xp

    return LEVELS[0][0], LEVELS[0][1], 0, LEVELS[1][2]


def show_level_progress(xp):

    level, level_name, start_xp, next_xp = get_level(xp)

    if next_xp is None:
        st.progress(1.0, text=f"{level_name} · 최고 레벨에 도달했어요!")
        return

    st.progress(
        (xp - start_xp) / (next_xp - start_xp),
        text=f"{level_name} · 다음 레벨까지 경험치 {next_xp - xp}"
    )


def count_rewards(user_id, code):
    return fetch_one(
        "SELECT COUNT(*) AS n FROM reward_events WHERE user_id = ? AND code = ?",
        (user_id, code)
    )["n"]


def update_badges(user_id):

    goals = get_goals(user_id)
    xp, _ = get_progress(user_id)
    streak = get_streak(user_id, goals)

    record_count = fetch_one("""
        SELECT
            (SELECT COUNT(*) FROM daily_status WHERE user_id = :u)
            + (SELECT COUNT(*) FROM sleep_logs WHERE user_id = :u)
            + (SELECT COUNT(*) FROM workout_logs WHERE user_id = :u)
            + (SELECT COUNT(*) FROM meal_logs WHERE user_id = :u) AS n
    """, {"u": user_id})["n"]

    subscribed = fetch_one(
        "SELECT 1 FROM payments WHERE user_id = ? AND status = 'success'", (user_id,)
    ) is not None

    workout_goals = count_rewards(user_id, "workout_goal")

    challenge = fetch_one("""
        SELECT COUNT(*) AS plays, COALESCE(SUM(reps), 0) AS reps
        FROM challenge_records
        WHERE user_id = ?
    """, (user_id,))

    duel_wins = fetch_one("""
        SELECT COUNT(*) AS n FROM duels
        WHERE (to_user = ? AND status = 'won') OR (from_user = ? AND status = 'lost')
    """, (user_id, user_id))["n"]

    champion = fetch_one(
        "SELECT 1 FROM reward_events WHERE user_id = ? AND code LIKE 'champion_%'",
        (user_id,)
    ) is not None

    rules = [
        (record_count >= 1, "first_record", "🌱 첫 기록", "첫 번째 생활 기록을 남겼어요."),
        (count_rewards(user_id, "daily_mission") >= 1, "first_mission", "🎯 첫 미션", "오늘의 미션을 처음 완료했어요."),
        (workout_goals >= 1, "workout_1", "🏃 첫 운동 목표 달성", "하루 운동 목표를 처음 채웠어요."),
        (workout_goals >= 5, "workout_5", "💪 운동 목표 5회", "운동 목표를 5번 달성했어요."),
        (count_rewards(user_id, "perfect_day") >= 1, "perfect_day", "🌟 완벽한 하루", "하루 목표를 모두 채웠어요."),
        (streak >= 3, "streak_3", "📅 3일 연속 달성", "3일 연속으로 목표를 달성했어요."),
        (streak >= 7, "streak_7", "🗓️ 7일 연속 달성", "7일 연속으로 목표를 달성했어요."),
        (xp >= 500, "xp_500", "⭐ 경험치 500", "경험치 500을 모았어요."),
        (xp >= 1000, "xp_1000", "🏆 경험치 1000", "경험치 1000을 모았어요."),
        (subscribed, "premium", "💎 부스터 플러스", "유료 구독을 시작했어요."),
        (challenge["plays"] >= 1, "challenge_1", "📸 첫 카메라 챌린지", "카메라 챌린지에 처음 도전했어요."),
        (challenge["reps"] >= 100, "challenge_100", "💯 누적 100회", "카메라 챌린지에서 모두 100회를 해냈어요."),
        (duel_wins >= 1, "duel_win", "⚔️ 첫 대결 승리", "도전장 대결에서 처음 이겼어요."),
        (champion, "champion", "👑 주간 챔피언", "주간 랭킹 1위를 차지했어요.")
    ]

    with closing(connect()) as conn, conn:
        for earned, badge_id, name, description in rules:
            if earned:
                conn.execute("""
                    INSERT OR IGNORE INTO user_badges
                    (user_id, badge_id, name, description, earned_date)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, badge_id, name, description, today_str()))


def after_record(user_id):
    """기록을 저장할 때마다 공통으로 처리."""

    check_perfect_day(user_id, get_goals(user_id))
    update_badges(user_id)


# ============================================================
# 오늘의 미션 · 맞춤 추천
# ============================================================

def get_today_mission(today, goals):

    if today["sleep_hours"] == 0:
        return "😴 수면 기록하기", "어젯밤 몇 시간 잤는지 기록해 보세요.", 20, 40

    if today["steps"] < goals["steps"]:
        return "🚶 10분 걷기", "가볍게 10분 정도 걸어 보세요.", 50, 100

    if today["water_ml"] < goals["water_ml"]:
        return "💧 물 마시기", "물 한 잔을 더 마셔 보세요.", 30, 70

    if today["exercise_min"] < goals["exercise_min"]:
        return "🏃 10분 움직이기", "오늘의 운동 계획에서 하나를 골라 해 보세요.", 50, 100

    if today["meals"] < goals["meals"]:
        return "🥗 식사 기록하기", "오늘 먹은 끼니를 기록해 보세요.", 30, 60

    if not pd.isna(today["mood"]) and today["mood"] <= 2:
        return "🙂 기분 전환", "좋아하는 활동으로 기분을 전환해 보세요.", 30, 70

    return "🎉 오늘의 목표 달성!", "오늘 생활 습관 목표를 잘 달성했어요.", 20, 50


def build_recommendation(recent, goals):
    """최근 7일 기록으로 맞춤 추천을 만든다.
    (제목, 설명, 바꿀 목표 또는 None)"""

    days = recent[recent["recorded"]]

    if days.empty:
        return (
            "첫 기록부터 시작해요",
            "수면·운동·식사 중 하나만 기록해도 맞춤 추천이 시작돼요.",
            None
        )

    average = days[["steps", "sleep_hours", "water_ml", "exercise_min", "meals"]].mean()

    proposed = dict(goals)
    changes = []
    tips = []

    if average["exercise_min"] < goals["exercise_min"] * 0.5 and goals["exercise_min"] > 10:
        proposed["exercise_min"] = max(10, int(round(average["exercise_min"] * 1.2 / 5) * 5))
        changes.append(
            f"운동 목표를 {proposed['exercise_min']}분으로 낮춰서 "
            "성공하는 경험부터 쌓아 봐요."
        )
    elif average["exercise_min"] >= goals["exercise_min"] * 1.1 and len(days) >= 3:
        proposed["exercise_min"] = goals["exercise_min"] + 5
        changes.append(
            f"운동 목표를 꾸준히 넘기고 있어요! "
            f"{proposed['exercise_min']}분으로 한 단계 올려 볼까요?"
        )

    if average["steps"] < goals["steps"] * 0.6 and goals["steps"] > 3000:
        proposed["steps"] = max(3000, int(round(average["steps"] * 1.1, -2)))
        changes.append(f"걸음 목표를 {proposed['steps']:,}걸음으로 조정해 봐요.")
    elif average["steps"] >= goals["steps"] * 1.1 and len(days) >= 3:
        proposed["steps"] = goals["steps"] + 1000
        changes.append(f"걸음 목표를 {proposed['steps']:,}걸음으로 올려 볼까요?")

    if 0 < average["sleep_hours"] < goals["sleep_hours"] - 1:
        tips.append("잠자리에 드는 시간을 30분 앞당겨 보세요.")

    if average["water_ml"] < goals["water_ml"] * 0.6:
        tips.append("식사 때마다 물 한 컵씩 마셔 보세요.")

    if average["meals"] < goals["meals"] * 0.7:
        tips.append("끼니를 거르지 않도록 식단 계획을 확인해 보세요.")

    if changes:
        return "목표를 조정해 볼까요?", " ".join(changes + tips), proposed

    if tips:
        return "이번 주 실천 팁", " ".join(tips), None

    return "아주 잘하고 있어요!", "지금 흐름을 그대로 이어 가세요. 🔥", None


def todays_workout_plan(goal_type, exercise_goal):
    """목표 유형에 맞는 운동을 골라 하루 목표 시간에 맞게 나눈다."""

    keys = WORKOUT_PLANS[goal_type]
    base_total = sum(EXERCISES[key]["base"] for key in keys)

    return [
        (key, max(5, round(EXERCISES[key]["base"] * exercise_goal / base_total / 5) * 5))
        for key in keys
    ]


# ============================================================
# AI 코칭 (선택 기능)
# .env에 OPENAI_API_KEY가 있고, 사용자가 'AI 외부 전송'에 동의했을 때만 동작.
# 이름·이메일·메모는 보내지 않고 수치 요약만 보낸다.
# ============================================================

COACH_RULES = (
    "너는 친절한 생활 습관 코치야. 사용자의 생활 기록 요약을 보고 "
    "실천할 수 있는 작고 구체적인 행동 3가지를 한국어로 제안해. "
    "무리한 운동이나 극단적인 식단은 권하지 말고, 의학적 진단은 하지 마. "
    "각 항목은 한두 문장으로 짧게 써."
)


def ai_key_set():
    key = os.getenv("OPENAI_API_KEY", "").strip()
    return bool(key) and key != "여기에_API_KEY_입력"


def ask_ai(instructions, summary):

    from openai import OpenAI

    response = OpenAI().responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
        instructions=instructions,
        input=summary
    )

    return response.output_text


def summary_for_ai(days, goals, goal_type):

    if days.empty:
        return f"목표 유형: {goal_type}\n아직 기록이 없음"

    return (
        f"목표 유형: {goal_type}\n"
        f"기록 일수: {len(days)}일\n"
        f"평균 걸음 수: {days['steps'].mean():.0f} (목표 {goals['steps']})\n"
        f"평균 수면: {days['sleep_hours'].mean():.1f}시간 (목표 {goals['sleep_hours']})\n"
        f"평균 물 섭취: {days['water_ml'].mean():.0f}mL (목표 {goals['water_ml']})\n"
        f"평균 운동: {days['exercise_min'].mean():.0f}분 (목표 {goals['exercise_min']})\n"
        f"평균 식사 기록: {days['meals'].mean():.1f}끼 (목표 {goals['meals']})\n"
        f"평균 기분(1~5): {days['mood'].mean():.1f}\n"
        f"평균 생활 점수: {days['score'].mean():.0f}"
    )


def ai_coach_box(user_id, key, instructions, summary):

    if not ai_key_set():
        st.caption(
            "AI 코칭을 쓰려면 .env 파일에 OPENAI_API_KEY를 넣고 앱을 다시 실행하세요."
        )
        return

    if not has_consent(user_id, "ai_transfer"):
        st.caption(
            "AI 코칭을 쓰려면 ⚙️ 설정 → 동의 내역에서 "
            "'AI 분석을 위한 외부 전송'에 동의해 주세요."
        )
        return

    state_key = f"ai_{key}"

    if st.button("🤖 AI 코치에게 물어보기", key=f"ai_button_{key}", width="stretch"):

        with st.spinner("AI 코치가 기록을 살펴보고 있어요..."):

            try:
                st.session_state[state_key] = ask_ai(instructions, summary)
            except Exception as error:
                st.session_state.pop(state_key, None)
                st.error(f"AI 코칭을 가져오지 못했어요: {error}")

    if state_key in st.session_state:
        st.info(st.session_state[state_key])
        st.caption(DISCLAIMER)


# ============================================================
# 구독
# ============================================================

def get_subscription(user_id):
    return fetch_one("SELECT * FROM subscriptions WHERE user_id = ?", (user_id,))


def is_premium(user_id):
    """해지를 요청했어도 만료일까지는 이용 가능."""
    sub = get_subscription(user_id)
    return sub is not None and sub["expires_at"] >= today_str()


def start_subscription(user_id, plan_key):

    plan = SUBSCRIPTION_PLANS[plan_key]

    execute("""
        INSERT INTO subscriptions (user_id, plan, status, started_at, expires_at, canceled_at)
        VALUES (?, ?, 'active', ?, ?, NULL)
        ON CONFLICT(user_id)
        DO UPDATE SET
            plan = excluded.plan,
            status = 'active',
            started_at = excluded.started_at,
            expires_at = excluded.expires_at,
            canceled_at = NULL
    """, (
        user_id,
        plan_key,
        today_str(),
        (date.today() + timedelta(days=plan["days"])).isoformat()
    ))


def extend_premium(user_id, days):
    """체험권: 구독 중이면 만료일을 늘리고, 아니면 체험 구독을 시작한다."""

    if is_premium(user_id):
        sub = get_subscription(user_id)
        new_end = date.fromisoformat(sub["expires_at"]) + timedelta(days=days)
        execute(
            "UPDATE subscriptions SET expires_at = ? WHERE user_id = ?",
            (new_end.isoformat(), user_id)
        )
    else:
        start_subscription(user_id, "trial")


def record_payment(user_id, plan_key, status):
    execute("""
        INSERT INTO payments (user_id, plan, amount, status, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, plan_key, SUBSCRIPTION_PLANS[plan_key]["price"], status, now_str()))


# ============================================================
# 입력 양식 (온보딩과 설정에서 같이 사용)
# ============================================================

def profile_inputs(defaults):

    col1, col2 = st.columns(2)

    with col1:

        gender = st.selectbox(
            "성별",
            GENDERS,
            index=GENDERS.index(defaults["gender"])
        )

        birth_year = st.number_input(
            "태어난 해",
            min_value=1920,
            max_value=date.today().year,
            value=int(defaults["birth_year"]),
            step=1
        )

        height = st.number_input(
            "키 (cm)",
            min_value=100.0,
            max_value=230.0,
            value=float(defaults["height_cm"]),
            step=0.5
        )

        weight = st.number_input(
            "몸무게 (kg)",
            min_value=25.0,
            max_value=250.0,
            value=float(defaults["weight_kg"]),
            step=0.5
        )

    with col2:

        activity = st.selectbox(
            "평소 활동량",
            ACTIVITY_LEVELS,
            index=ACTIVITY_LEVELS.index(defaults["activity_level"])
        )

        goal_type = st.selectbox(
            "가장 이루고 싶은 목표",
            GOAL_TYPES,
            index=GOAL_TYPES.index(defaults["goal_type"])
        )

    return {
        "gender": gender,
        "birth_year": int(birth_year),
        "height_cm": float(height),
        "weight_kg": float(weight),
        "activity_level": activity,
        "goal_type": goal_type
    }


DEFAULT_PROFILE = {
    "gender": GENDERS[0],
    "birth_year": 2000,
    "height_cm": 165.0,
    "weight_kg": 60.0,
    "activity_level": ACTIVITY_LEVELS[1],
    "goal_type": GOAL_TYPES[2]
}


def show_goal_table(goals):

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("🚶 걸음", f"{goals['steps']:,}")
    col2.metric("😴 수면", f"{goals['sleep_hours']}시간")
    col3.metric("💧 물", f"{goals['water_ml']:,}mL")
    col4.metric("🏃 운동", f"{goals['exercise_min']}분")
    col5.metric("🥗 식사", f"{goals['meals']}끼")


# ============================================================
# 1. 인증 및 온보딩
# ============================================================

def page_auth():

    st.title("🚀 Life of Booster")
    st.caption("운동·식사·수면 습관을 함께 만들어 가는 건강 습관 코치")

    login_tab, signup_tab = st.tabs(["로그인", "회원가입"])

    with login_tab:

        with st.form("login_form"):

            email = st.text_input("이메일")
            password = st.text_input("비밀번호", type="password")

            submitted = st.form_submit_button("로그인", width="stretch")

        if submitted:

            user = authenticate(email, password)

            if user is None:
                st.error("이메일 또는 비밀번호가 맞지 않아요.")
            else:
                login(user["id"])
                st.rerun()

    with signup_tab:

        with st.form("signup_form"):

            name = st.text_input("이름 (별명도 괜찮아요)")
            email = st.text_input("이메일", key="signup_email")
            password = st.text_input("비밀번호 (8자 이상)", type="password", key="signup_password")
            password_check = st.text_input("비밀번호 확인", type="password")

            submitted = st.form_submit_button("가입하기", width="stretch")

        if submitted:

            email = email.strip().lower()

            if not name.strip():
                st.error("이름을 입력해 주세요.")
            elif "@" not in email or "." not in email.split("@")[-1]:
                st.error("이메일 형식이 올바르지 않아요.")
            elif len(password) < 8:
                st.error("비밀번호는 8자 이상이어야 해요.")
            elif password != password_check:
                st.error("비밀번호 확인이 일치하지 않아요.")
            elif fetch_one("SELECT 1 FROM users WHERE email = ?", (email,)):
                st.error("이미 가입된 이메일이에요. 로그인해 주세요.")
            else:
                user_id = create_user(name.strip(), email, password)
                login(user_id)
                st.rerun()


def page_consent():

    user = current_user()

    if st.session_state.get("consent_refused"):

        st.title("🙏 동의 거부 안내")

        st.warning(
            "필수 항목에 동의하지 않으면 Life of Booster를 이용할 수 없어요."
        )

        st.write(
            "Life of Booster는 수면·운동·식사 기록을 바탕으로 맞춤 목표와 "
            "리포트를 만들어요. 그래서 건강·생활 데이터 이용 동의가 꼭 필요해요.\n\n"
            "동의한 뒤에도 언제든 ⚙️ 설정 → 동의 내역에서 철회할 수 있고, "
            "철회하면 기록한 건강 데이터는 모두 삭제돼요."
        )

        col1, col2 = st.columns(2)

        if col1.button("다시 동의하기", width="stretch"):
            st.session_state.pop("consent_refused")
            st.rerun()

        if col2.button("로그아웃", width="stretch"):
            logout()

        return

    st.title("📄 건강 데이터 이용 동의")
    st.caption(f"{user['name']}님, 시작하기 전에 아래 내용을 확인해 주세요.")

    saved = get_consents(user["id"])
    checks = {}

    with st.form("consent_form"):

        for item, label, required, description in CONSENT_ITEMS:

            tag = "[필수]" if required else "[선택]"

            checks[item] = st.checkbox(
                f"{tag} {label}",
                value=bool(saved.get(item) and saved[item]["agreed"])
            )

            st.caption(description)

        submitted = st.form_submit_button("동의하고 계속하기", width="stretch")

    if submitted:

        if not all(checks[item] for item in REQUIRED_CONSENTS):
            st.session_state["consent_refused"] = True
            st.rerun()

        for item, agreed in checks.items():
            save_consent(user["id"], item, agreed)

        st.rerun()


def page_profile_onboarding():

    user = current_user()

    st.title("👤 건강 프로필 입력")
    st.caption("입력한 정보로 나에게 맞는 시작 목표를 만들어 드려요.")

    with st.form("profile_onboarding_form"):

        profile = profile_inputs(DEFAULT_PROFILE)

        submitted = st.form_submit_button("저장하고 맞춤 계획 받기", width="stretch")

    if submitted:

        save_profile(user["id"], profile)
        save_goals(user["id"], starter_goals(profile))

        st.session_state["show_starter_plan"] = True

        st.rerun()

    st.caption(DISCLAIMER)


def page_starter_plan():

    user = current_user()
    profile = get_profile(user["id"])
    goals = get_goals(user["id"])

    st.title("🎉 나만의 시작 계획이 준비됐어요")
    st.caption(f"목표 유형: {profile['goal_type']} · 평소 활동량: {profile['activity_level']}")

    st.subheader("🎯 하루 목표")
    show_goal_table(goals)

    st.subheader("🏃 오늘의 운동 계획")

    for key, minutes in todays_workout_plan(profile["goal_type"], goals["exercise_min"]):
        st.write(f"- {EXERCISES[key]['name']} {minutes}분")

    st.subheader("🥗 추천 식단")

    for meal, menu in MEAL_PLANS[profile["goal_type"]].items():
        st.write(f"- **{meal}**: {menu}")

    st.info("목표는 언제든 🎯 목표 설정에서 바꿀 수 있어요. 처음에는 가볍게 시작해 보세요!")

    ai_coach_box(
        user["id"],
        "starter",
        COACH_RULES + " 이 사용자는 오늘 앱을 처음 시작했어.",
        f"목표 유형: {profile['goal_type']}\n"
        f"평소 활동량: {profile['activity_level']}\n"
        f"하루 목표: 걸음 {goals['steps']}, 수면 {goals['sleep_hours']}시간, "
        f"물 {goals['water_ml']}mL, 운동 {goals['exercise_min']}분"
    )

    if st.button("🚀 시작하기", type="primary", width="stretch"):
        st.session_state.pop("show_starter_plan")
        update_badges(user["id"])
        st.rerun()


# ============================================================
# 2. 홈 및 목표 관리
# ============================================================

def show_inbox_preview(user_id):
    """읽지 않은 알림을 홈 위쪽에 보여 준다."""

    rows = fetch_all("""
        SELECT message FROM notifications
        WHERE user_id = ? AND is_read = 0
        ORDER BY id DESC
        LIMIT 3
    """, (user_id,))

    if not rows:
        return

    with st.container(border=True):

        for row in rows:
            st.write(f"🔔 {row['message']}")

        st.page_link(
            PAGES["inbox"],
            label=f"알림함에서 모두 보기 ({unread_count(user_id)})",
            icon="📬"
        )


def save_recommendation_feedback(user_id, title, action, reason=None):
    execute("""
        INSERT INTO recommendation_feedback (user_id, feedback_date, title, action, reason)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, today_str(), title, action, reason))


def recommendation_answered_today(user_id, title):
    return fetch_one("""
        SELECT action FROM recommendation_feedback
        WHERE user_id = ? AND feedback_date = ? AND title = ?
        ORDER BY id DESC
    """, (user_id, today_str(), title))


def page_home():

    user = current_user()
    user_id = user["id"]
    goals = get_goals(user_id)
    profile = get_profile(user_id)
    settings = get_settings(user_id)

    today = today_summary(user_id, goals)
    xp, points = get_progress(user_id)
    level, _, _, _ = get_level(xp)
    streak = get_streak(user_id, goals)

    st.title(f"🚀 {user['name']}님의 오늘")
    st.caption("완벽할 필요는 없어요. 작은 습관을 하나씩 채워 보세요. 🌱")

    show_flash()
    show_inbox_preview(user_id)

    if get_item(user_id, "grace") and settings["auto_grace"]:
        st.caption(f"🛡️ 유예권 {get_item(user_id, 'grace')}장 보유 중 · 목표를 놓친 날 자동으로 사용돼요.")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("🔥 연속 달성", f"{streak}일")
    col2.metric("⭐ 오늘 생활 점수", f"{today['score']:.0f}")
    col3.metric("🏆 레벨", f"{level}")
    col4.metric("💰 포인트", f"{points:,}")

    st.caption(f"연속 달성: 생활 점수 {ACHIEVED_SCORE}점 이상인 날이 이어진 일수")

    ranking = my_ranking_summary(user_id)

    with st.container(border=True):

        col1, col2 = st.columns([3, 1])

        if ranking:
            my_rank, players, my_total = ranking
            col1.markdown(
                f"🏆 **이번 주 카메라 챌린지 종합 {my_rank}위** "
                f"({players}명 중 · 누적 {my_total}개)"
            )
        else:
            col1.markdown("🏆 이번 주 카메라 챌린지 순위에 아직 없어요. 도전해서 이름을 올려 보세요!")

        with col2:
            st.page_link(PAGES["ranking"], label="순위표", icon="👉")

    # 오늘의 목표 진행률

    st.subheader("🎯 오늘의 목표 진행률")

    rates = habit_rates(today, goals)

    progress_rows = [
        ("steps", f"{today['steps']:,.0f} / {goals['steps']:,} 걸음"),
        ("sleep_hours", f"{today['sleep_hours']} / {goals['sleep_hours']} 시간"),
        ("water_ml", f"{today['water_ml']:,.0f} / {goals['water_ml']:,} mL"),
        ("exercise_min", f"{today['exercise_min']:.0f} / {goals['exercise_min']} 분"),
        ("meals", f"{today['meals']:.0f} / {goals['meals']} 끼")
    ]

    for key, text in progress_rows:
        st.progress(rates[key] / 100, text=f"{HABIT_LABELS[key]} · {text}")

    col1, col2, col3 = st.columns(3)

    col1.page_link(PAGES["sleep"], label="수면 기록", icon="😴")
    col2.page_link(PAGES["workout"], label="운동 계획 확인", icon="🏃")
    col3.page_link(PAGES["meal"], label="식단 계획", icon="🥗")

    with st.expander("✏️ 걸음 수 · 물 · 기분 빠르게 기록"):

        status = get_daily_status(user_id, date.today())

        col1, col2 = st.columns(2)

        if col1.button("💧 물 한 컵 (+250mL)", width="stretch"):
            add_water(user_id, 250)
            after_record(user_id)
            st.rerun()

        if col2.button("💧 물병 하나 (+500mL)", width="stretch"):
            add_water(user_id, 500)
            after_record(user_id)
            st.rerun()

        with st.form("quick_form"):

            steps = st.number_input(
                "🚶 오늘 걸음 수",
                min_value=0,
                max_value=100000,
                value=int(status["steps"] or 0) if status else 0,
                step=500
            )

            mood = st.slider(
                "🙂 오늘의 기분",
                min_value=1,
                max_value=5,
                value=int(status["mood"] or 3) if status else 3
            )

            submitted = st.form_submit_button("저장", width="stretch")

        if submitted:
            update_daily_status(user_id, date.today(), steps=steps, mood=mood)
            after_record(user_id)
            flash("✅ 저장했어요!")
            st.rerun()

    # 맞춤 추천 카드

    st.subheader("🤖 맞춤 추천")

    recent = daily_summary(user_id, date.today() - timedelta(days=6), date.today(), goals)

    title, message, proposed = build_recommendation(recent, goals)

    with st.container(border=True):

        st.markdown(f"**{title}**")

        answered = recommendation_answered_today(user_id, title) if proposed else None

        if answered and answered["action"] == "rejected":

            st.caption("오늘은 이 추천을 거절했어요. 내일 새 기록으로 다시 추천해 드릴게요.")

        else:

            st.write(message)
            st.caption("근거: 최근 7일 기록의 평균을 지금 목표와 비교했어요.")

        if proposed and not answered:

            col1, col2 = st.columns(2)

            if col1.button("👍 수락하고 목표 조정하기", width="stretch"):
                save_recommendation_feedback(user_id, title, "accepted")
                st.session_state["pending_goals"] = proposed
                st.switch_page(PAGES["goals"])

            with col2.popover("✕ 거절하기", width="stretch"):

                reason = st.selectbox("거절하는 이유 (선택)", RECOMMENDATION_REJECT_REASONS)

                if st.button("거절", key="reject_recommendation"):
                    save_recommendation_feedback(
                        user_id,
                        title,
                        "rejected",
                        None if reason == RECOMMENDATION_REJECT_REASONS[0] else reason
                    )
                    flash("알겠어요! 의견은 다음 추천을 더 좋게 만드는 데 쓸게요.", "info")
                    st.rerun()

        ai_coach_box(
            user_id,
            "home",
            COACH_RULES,
            summary_for_ai(recent[recent["recorded"]], goals, profile["goal_type"])
        )

    # 오늘의 미션

    st.subheader("🎯 오늘의 미션")

    mission_title, mission_text, mission_xp, mission_points = get_today_mission(today, goals)

    with st.container(border=True):

        st.markdown(f"### {mission_title}")
        st.write(mission_text)
        st.caption(f"보상: 경험치 +{mission_xp} · 포인트 +{mission_points}")

        if fetch_one(
            "SELECT 1 FROM reward_events WHERE user_id = ? AND code = 'daily_mission' AND event_date = ?",
            (user_id, today_str())
        ):
            st.success("🎉 오늘의 미션을 이미 완료했어요!")

        elif st.button("🎯 미션 완료하기", width="stretch"):

            if give_reward(
                user_id,
                "daily_mission",
                f"🎯 미션 완료: {mission_title}",
                mission_xp,
                mission_points
            ):
                update_badges(user_id)
                flash(f"🎉 미션 완료! 경험치 +{mission_xp} · 포인트 +{mission_points}")

            st.rerun()


def page_goals():

    user = current_user()
    user_id = user["id"]

    current = get_goals(user_id)
    pending = st.session_state.get("pending_goals")
    defaults = pending or current

    st.title("🎯 목표 설정")
    st.caption("나에게 맞는 하루 목표를 정하면 생활 점수와 미션이 그에 맞게 바뀌어요.")

    if pending:
        st.info("🤖 맞춤 추천으로 바뀐 목표를 미리 채워 두었어요. 확인하고 저장해 주세요.")

    st.markdown("**지금 목표**")
    show_goal_table(current)

    with st.form("goal_form"):

        col1, col2 = st.columns(2)

        with col1:

            steps = st.number_input(
                "🚶 하루 걸음 수",
                min_value=1000,
                max_value=30000,
                value=int(defaults["steps"]),
                step=500
            )

            sleep_hours = st.number_input(
                "😴 수면 시간",
                min_value=4.0,
                max_value=12.0,
                value=float(defaults["sleep_hours"]),
                step=0.5
            )

            water = st.number_input(
                "💧 물 섭취량 (mL)",
                min_value=500,
                max_value=5000,
                value=int(defaults["water_ml"]),
                step=100
            )

        with col2:

            exercise = st.number_input(
                "🏃 운동 시간 (분)",
                min_value=5,
                max_value=180,
                value=int(defaults["exercise_min"]),
                step=5
            )

            meals = st.number_input(
                "🥗 식사 기록 (끼)",
                min_value=1,
                max_value=4,
                value=int(defaults["meals"]),
                step=1
            )

        submitted = st.form_submit_button("💾 목표 저장", width="stretch")

    if submitted:

        save_goals(user_id, {
            "steps": steps,
            "sleep_hours": sleep_hours,
            "water_ml": water,
            "exercise_min": exercise,
            "meals": meals
        })

        st.session_state.pop("pending_goals", None)

        flash("✅ 목표를 저장했어요!")

        st.switch_page(PAGES["home"])

    if pending and st.button("추천 취소", width="stretch"):
        st.session_state.pop("pending_goals")
        st.rerun()

    if st.button("↩️ 프로필 기준 추천 목표로 되돌리기"):
        st.session_state["pending_goals"] = starter_goals(get_profile(user_id))
        st.rerun()


# ============================================================
# 3. 생활 데이터 기록
# ============================================================

def page_sleep():

    user = current_user()
    user_id = user["id"]

    st.title("😴 수면 기록")
    st.caption(
        f"일어난 날짜 기준으로 기록해요. 최근 {EDIT_WINDOW_DAYS}일 기록은 "
        "같은 날짜로 다시 저장하면 고쳐져요."
    )

    show_flash()

    with st.form("sleep_form"):

        log_date = date_picker("일어난 날짜", "sleep_date")

        col1, col2 = st.columns(2)

        bed_time = col1.time_input("잠든 시각", value=time(23, 0), step=600)
        wake_time = col2.time_input("일어난 시각", value=time(7, 0), step=600)

        quality = st.slider("잠의 질 (1: 나쁨 ~ 5: 아주 좋음)", 1, 5, 3)

        submitted = st.form_submit_button("💾 수면 기록 저장", width="stretch")

    if submitted:

        hours = sleep_duration(bed_time, wake_time)

        if hours == 0:
            st.error("잠든 시각과 일어난 시각이 같아요. 다시 확인해 주세요.")
        else:
            save_sleep(user_id, log_date, bed_time, wake_time, quality)

            if log_date == date.today():
                give_reward(user_id, "sleep_log", "😴 수면 기록", 10, 20)

            after_record(user_id)

            flash(f"✅ 수면 {hours}시간을 기록했어요!")

            st.switch_page(PAGES["home"])

    st.subheader("최근 수면 기록")

    recent = read_df("""
        SELECT log_date AS 날짜, bed_time AS 잠든시각, wake_time AS 일어난시각,
               hours AS 수면시간, quality AS 잠의질
        FROM sleep_logs
        WHERE user_id = ?
        ORDER BY log_date DESC
        LIMIT 14
    """, (user_id,))

    if recent.empty:
        st.info("아직 수면 기록이 없어요.")
    else:
        st.dataframe(recent, width="stretch", hide_index=True)


def pick_recent_record(rows, label, key):
    """최근 7일 기록 중 하나를 고르게 한다."""

    options = {row["id"]: label(row) for row in rows}

    selected = st.selectbox(
        "고칠 기록",
        list(options),
        format_func=options.get,
        key=key
    )

    return next(row for row in rows if row["id"] == selected)


def edit_recent_workouts(user_id):

    first, _ = editable_dates()

    rows = fetch_all("""
        SELECT * FROM workout_logs
        WHERE user_id = ? AND log_date >= ?
        ORDER BY log_date DESC, id DESC
    """, (user_id, first.isoformat()))

    with st.expander(f"✏️ 최근 {EDIT_WINDOW_DAYS}일 운동 기록 고치기 · 지우기"):

        if not rows:
            st.caption("고칠 기록이 없어요.")
            return

        row = pick_recent_record(
            rows,
            lambda r: f"{r['log_date']} · {r['kind']} {r['minutes']}분",
            "edit_workout_pick"
        )

        with st.form(f"edit_workout_{row['id']}"):

            minutes = st.number_input(
                "운동 시간 (분)",
                min_value=1,
                max_value=300,
                value=int(row["minutes"])
            )

            intensity = st.radio(
                "강도",
                INTENSITIES,
                index=INTENSITIES.index(row["intensity"]) if row["intensity"] in INTENSITIES else 1,
                horizontal=True
            )

            note = st.text_input("메모", value=row["note"] or "", max_chars=100)

            col1, col2 = st.columns(2)

            save = col1.form_submit_button("💾 고치기", width="stretch")
            delete = col2.form_submit_button("🗑️ 지우기", width="stretch")

        if save:
            execute("""
                UPDATE workout_logs SET minutes = ?, intensity = ?, note = ?
                WHERE id = ? AND user_id = ?
            """, (minutes, intensity, note.strip(), row["id"], user_id))
            after_record(user_id)
            flash("✅ 운동 기록을 고쳤어요.")
            st.rerun()

        if delete:
            execute(
                "DELETE FROM workout_logs WHERE id = ? AND user_id = ?",
                (row["id"], user_id)
            )
            flash("🗑️ 운동 기록을 지웠어요.", "info")
            st.rerun()


def edit_recent_meals(user_id):

    first, _ = editable_dates()

    rows = fetch_all("""
        SELECT * FROM meal_logs
        WHERE user_id = ? AND log_date >= ?
        ORDER BY log_date DESC, id DESC
    """, (user_id, first.isoformat()))

    with st.expander(f"✏️ 최근 {EDIT_WINDOW_DAYS}일 식사 기록 고치기 · 지우기"):

        if not rows:
            st.caption("고칠 기록이 없어요.")
            return

        row = pick_recent_record(
            rows,
            lambda r: f"{r['log_date']} · {r['meal_type']} · {r['menu']}",
            "edit_meal_pick"
        )

        with st.form(f"edit_meal_{row['id']}"):

            meal_type = st.radio(
                "끼니",
                MEAL_TYPES,
                index=MEAL_TYPES.index(row["meal_type"]),
                horizontal=True
            )

            menu = st.text_input("먹은 음식", value=row["menu"], max_chars=100)

            calories = st.number_input(
                "열량 (kcal, 모르면 0)",
                min_value=0,
                max_value=5000,
                value=int(row["calories"] or 0),
                step=50
            )

            col1, col2 = st.columns(2)

            save = col1.form_submit_button("💾 고치기", width="stretch")
            delete = col2.form_submit_button("🗑️ 지우기", width="stretch")

        if save:

            if not menu.strip():
                st.error("먹은 음식을 입력해 주세요.")
            else:
                execute("""
                    UPDATE meal_logs SET meal_type = ?, menu = ?, calories = ?
                    WHERE id = ? AND user_id = ?
                """, (meal_type, menu.strip(), calories or None, row["id"], user_id))
                after_record(user_id)
                flash("✅ 식사 기록을 고쳤어요.")
                st.rerun()

        if delete:
            execute(
                "DELETE FROM meal_logs WHERE id = ? AND user_id = ?",
                (row["id"], user_id)
            )
            flash("🗑️ 식사 기록을 지웠어요.", "info")
            st.rerun()


@st.fragment(run_every=1)
def workout_timer(started_at):
    elapsed = int((datetime.now() - started_at).total_seconds())
    minutes, seconds = divmod(elapsed, 60)
    st.metric("⏱️ 운동 시간", f"{minutes:02d}:{seconds:02d}")


def set_workout_stage(stage, **values):
    st.session_state["workout_stage"] = stage
    st.session_state.update({f"workout_{key}": value for key, value in values.items()})
    st.rerun()


def page_workout():

    user = current_user()
    user_id = user["id"]
    goals = get_goals(user_id)
    profile = get_profile(user_id)

    stage = st.session_state.get("workout_stage", "plan")

    # 운동 계획 확인 ------------------------------------------------

    if stage == "plan":

        st.title("🏃 오늘의 운동 계획")

        show_flash()

        done = workout_minutes(user_id, date.today())

        st.progress(
            min(done / goals["exercise_min"], 1.0),
            text=f"오늘 운동 {done} / {goals['exercise_min']} 분"
        )

        for key, minutes in todays_workout_plan(profile["goal_type"], goals["exercise_min"]):

            with st.container(border=True):

                col1, col2 = st.columns([3, 1])

                col1.markdown(f"**{EXERCISES[key]['name']}** · {minutes}분")
                col1.caption(EXERCISES[key]["guide"][0])

                if col2.button("▶️ 운동 시작", key=f"start_{key}", width="stretch"):
                    set_workout_stage(
                        "guide",
                        key=key,
                        planned=minutes,
                        started=datetime.now()
                    )

        if st.button("✏️ 계획 없이 바로 기록하기", width="stretch"):
            set_workout_stage("record", key=None, minutes=goals["exercise_min"])

        st.subheader("오늘 한 운동")

        logs = read_df("""
            SELECT kind AS 운동, minutes AS 시간_분, intensity AS 강도, note AS 메모
            FROM workout_logs
            WHERE user_id = ? AND log_date = ?
            ORDER BY id
        """, (user_id, today_str()))

        if logs.empty:
            st.info("아직 오늘 운동 기록이 없어요.")
        else:
            st.dataframe(logs, width="stretch", hide_index=True)

        edit_recent_workouts(user_id)

        st.page_link(PAGES["challenge"], label="카메라로 푸시업·스쿼트 대결하기", icon="📸")

        st.caption(DISCLAIMER)

    # 운동 실천 가이드 ----------------------------------------------

    elif stage == "guide":

        exercise = EXERCISES[st.session_state["workout_key"]]

        st.title(f"{exercise['name']}")
        st.caption(f"계획: {st.session_state['workout_planned']}분")

        workout_timer(st.session_state["workout_started"])

        st.subheader("📖 따라 하기")

        for number, step in enumerate(exercise["guide"], start=1):
            st.write(f"{number}. {step}")

        st.warning("가슴 통증, 어지럼증, 심한 숨참이 느껴지면 바로 멈추고 쉬세요.")

        col1, col2 = st.columns(2)

        if col1.button("⏹️ 운동 종료", type="primary", width="stretch"):

            elapsed = (datetime.now() - st.session_state["workout_started"]).total_seconds()

            set_workout_stage(
                "record",
                minutes=max(1, round(elapsed / 60))
            )

        if col2.button("취소", width="stretch"):
            set_workout_stage("plan")

    # 운동 기록 입력 ------------------------------------------------

    elif stage == "record":

        st.title("✏️ 운동 기록 입력")

        names = [exercise["name"] for exercise in EXERCISES.values()] + ["기타 운동"]

        selected = st.session_state.get("workout_key")
        default_index = names.index(EXERCISES[selected]["name"]) if selected else 0

        with st.form("workout_form"):

            kind = st.selectbox("운동 종류", names, index=default_index)

            log_date = date_picker("운동한 날짜", "workout_date")

            minutes = st.number_input(
                "운동 시간 (분)",
                min_value=1,
                max_value=300,
                value=int(st.session_state.get("workout_minutes", 10)),
                step=1
            )

            intensity = st.radio("강도", INTENSITIES, index=1, horizontal=True)

            note = st.text_input("메모 (선택)", max_chars=100)

            submitted = st.form_submit_button("💾 운동 기록 저장", width="stretch")

        if submitted:

            add_workout(user_id, log_date, kind, minutes, intensity, note.strip())

            give_reward(user_id, "workout_log", "🏃 운동 기록", 10, 20, log_date)

            total = workout_minutes(user_id, log_date)
            achieved = total >= goals["exercise_min"]

            new_reward = achieved and give_reward(
                user_id,
                "workout_goal",
                "🏃 운동 목표 달성",
                50,
                100,
                log_date
            )

            after_record(user_id)

            set_workout_stage(
                "reward" if achieved else "penalty",
                total=total,
                new_reward=new_reward
            )

        if st.button("취소", width="stretch"):
            set_workout_stage("plan")

    # 운동 목표 달성 → 보상 화면 ------------------------------------

    elif stage == "reward":

        st.title("🎉 운동 목표 달성!")

        if st.session_state.get("workout_new_reward"):
            st.balloons()
            st.success("보상을 받았어요! 경험치 +50 · 포인트 +100")
        else:
            st.info("오늘 운동 목표 보상은 이미 받았어요. 추가로 움직인 것도 멋져요!")

        st.metric("오늘 운동", f"{st.session_state['workout_total']}분")

        col1, col2 = st.columns(2)

        if col1.button("🏠 홈으로", width="stretch"):
            st.session_state["workout_stage"] = "plan"
            st.switch_page(PAGES["home"])

        if col2.button("🏆 보상 이력 보기", width="stretch"):
            st.session_state["workout_stage"] = "plan"
            st.switch_page(PAGES["rewards"])

    # 운동 목표 미달성 → 차감 안내 화면 -----------------------------

    elif stage == "penalty":

        settings = get_settings(user_id)
        remaining = goals["exercise_min"] - st.session_state["workout_total"]

        st.title("💪 조금만 더 힘내요!")

        st.info(
            f"기록은 저장됐어요. 오늘 운동 목표까지 **{remaining}분** 남았어요."
        )

        st.subheader("📌 차감 규칙 안내")

        if settings["penalty_enabled"]:
            st.write(
                f"오늘 운동 목표를 채우지 못하면 내일 앱을 열 때 "
                f"**포인트 {WORKOUT_MISS_PENALTY}점**이 차감돼요. "
                "포인트는 0점 아래로 내려가지 않아요."
            )
        else:
            st.write("차감 규칙이 꺼져 있어요. ⚙️ 설정에서 다시 켤 수 있어요.")

        st.caption("몸이 좋지 않은 날은 쉬는 것도 좋은 선택이에요. 무리하지 마세요.")

        st.subheader("🔁 남은 시간 채우기 추천")
        st.write(f"- 🚶 가볍게 걷기 {max(5, remaining)}분")
        st.write("- 🧘 자기 전 스트레칭 10분")

        col1, col2 = st.columns(2)

        if col1.button("🏃 운동 계획으로", width="stretch"):
            set_workout_stage("plan")

        if col2.button("🏠 홈으로", width="stretch"):
            st.session_state["workout_stage"] = "plan"
            st.switch_page(PAGES["home"])


def page_meal():

    user = current_user()
    user_id = user["id"]
    profile = get_profile(user_id)

    st.title("🥗 식단")

    show_flash()

    plan_tab, record_tab = st.tabs(["🍽️ 끼니별 식단 계획", "✏️ 식사 기록 입력"])

    with plan_tab:

        st.caption(f"목표 유형 '{profile['goal_type']}'에 맞춘 추천이에요.")

        for meal, menu in MEAL_PLANS[profile["goal_type"]].items():

            with st.container(border=True):
                st.markdown(f"**{meal}**")
                st.write(menu)

        st.caption(DISCLAIMER)

    with record_tab:

        with st.form("meal_form"):

            meal_type = st.radio("끼니", MEAL_TYPES, horizontal=True)

            log_date = date_picker("먹은 날짜", "meal_date")

            menu = st.text_input(
                "먹은 음식",
                placeholder="예: 잡곡밥, 된장국, 계란말이",
                max_chars=100
            )

            calories = st.number_input(
                "열량 (kcal, 모르면 0)",
                min_value=0,
                max_value=5000,
                value=0,
                step=50
            )

            submitted = st.form_submit_button("💾 식사 기록 저장", width="stretch")

        if submitted:

            if not menu.strip():
                st.error("먹은 음식을 입력해 주세요.")
            else:
                add_meal(user_id, log_date, meal_type, menu.strip(), calories or None)

                give_reward(user_id, f"meal_{meal_type}", f"🥗 {meal_type} 기록", 5, 10, log_date)

                after_record(user_id)

                flash(f"✅ {meal_type} 식사를 기록했어요!")

                st.switch_page(PAGES["home"])

        st.subheader("💧 물 마시기")

        col1, col2 = st.columns(2)

        if col1.button("+250mL", width="stretch"):
            add_water(user_id, 250)
            after_record(user_id)
            st.rerun()

        if col2.button("+500mL", width="stretch"):
            add_water(user_id, 500)
            after_record(user_id)
            st.rerun()

        status = get_daily_status(user_id, date.today())
        st.caption(f"오늘 마신 물: {status['water_ml'] if status else 0:,} mL")

        st.subheader("오늘 먹은 식사")

        meals = read_df("""
            SELECT meal_type AS 끼니, menu AS 음식, calories AS 열량
            FROM meal_logs
            WHERE user_id = ? AND log_date = ?
            ORDER BY id
        """, (user_id, today_str()))

        if meals.empty:
            st.info("아직 오늘 식사 기록이 없어요.")
        else:
            st.dataframe(meals, width="stretch", hide_index=True)

        edit_recent_meals(user_id)


def page_device():

    user = current_user()
    user_id = user["id"]

    device = fetch_one("SELECT * FROM devices WHERE user_id = ?", (user_id,))

    st.title("⌚ 기기 데이터 연동")

    st.info(
        "시연용 기능이에요. 실제 기기와 연결하지 않고, "
        "연동한 것처럼 걸음 수를 가져와요."
    )

    show_flash()

    device_type = st.selectbox(
        "연동할 기기",
        DEVICE_TYPES,
        index=DEVICE_TYPES.index(device["device_type"]) if device else 0
    )

    connected = st.toggle("기기 연동 활성화", value=bool(device and device["connected"]))

    if device is None or connected != bool(device["connected"]) or device_type != device["device_type"]:

        execute("""
            INSERT INTO devices (user_id, device_type, connected, last_sync)
            VALUES (?, ?, ?, NULL)
            ON CONFLICT(user_id)
            DO UPDATE SET device_type = excluded.device_type, connected = excluded.connected
        """, (user_id, device_type, int(connected)))

        device = fetch_one("SELECT * FROM devices WHERE user_id = ?", (user_id,))

    if connected:

        st.caption(f"마지막 동기화: {device['last_sync'] or '아직 없음'}")

        if st.button("🔄 지금 걸음 수 가져오기", width="stretch"):

            # 시연용: 날짜와 사용자마다 일정한 가짜 걸음 수
            rng = random.Random(f"{user_id}-{today_str()}")
            hour_ratio = min(1.0, max(0.2, datetime.now().hour / 21))
            steps = int(rng.randint(6000, 12000) * hour_ratio)

            update_daily_status(user_id, date.today(), steps=steps)

            execute(
                "UPDATE devices SET last_sync = ? WHERE user_id = ?",
                (now_str(), user_id)
            )

            after_record(user_id)

            flash(f"✅ {device_type}에서 걸음 수 {steps:,}걸음을 가져왔어요.")

            st.rerun()

    st.subheader("✏️ 직접 입력")

    status = get_daily_status(user_id, date.today())

    with st.form("manual_steps"):

        log_date = date_picker("날짜", "steps_date")

        steps = st.number_input(
            "걸음 수",
            min_value=0,
            max_value=100000,
            value=int(status["steps"] or 0) if status else 0,
            step=500
        )

        submitted = st.form_submit_button("저장", width="stretch")

    if submitted:
        update_daily_status(user_id, log_date, steps=steps)
        after_record(user_id)
        flash("✅ 걸음 수를 저장했어요.")
        st.rerun()


# ============================================================
# 4. 게임화 및 보상
# ============================================================

def page_rewards():

    user = current_user()
    user_id = user["id"]

    update_badges(user_id)

    xp, points = get_progress(user_id)
    level, level_name, _, _ = get_level(xp)

    st.title("🏆 보상 · 성취 이력")

    show_flash()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("🏆 레벨", f"{level}")
    col2.metric("✨ 경험치", f"{xp:,}")
    col3.metric("💰 포인트", f"{points:,}")
    col4.metric("🛡️ 유예권", f"{get_item(user_id, 'grace')}장")

    st.subheader(level_name)
    show_level_progress(xp)

    badge_tab, history_tab, shop_tab = st.tabs(["🎖️ 배지", "📜 보상 이력", "🛒 포인트 상점"])

    with badge_tab:
        show_badges(user_id)

    with history_tab:
        show_reward_history(user_id)

    with shop_tab:

        st.caption("모은 포인트로 필요한 것을 살 수 있어요.")

        for item_key, item in SHOP_ITEMS.items():

            with st.container(border=True):

                col1, col2 = st.columns([3, 1])

                col1.markdown(f"**{item['name']}** · {item['price']:,} 포인트")
                col1.caption(item["description"])

                if col2.button(
                    "구매",
                    key=f"buy_{item_key}",
                    disabled=points < item["price"],
                    width="stretch"
                ):
                    if buy_item(user_id, item_key):
                        update_badges(user_id)
                        flash(f"🛒 {item['name']}을(를) 샀어요!")
                    st.rerun()

        if points < min(item["price"] for item in SHOP_ITEMS.values()):
            st.caption("포인트가 모자라요. 미션과 목표 달성으로 포인트를 모아 보세요!")


def show_badges(user_id):

    badges = fetch_all("""
        SELECT name, description, earned_date
        FROM user_badges
        WHERE user_id = ?
        ORDER BY earned_date DESC, name
    """, (user_id,))

    if not badges:
        st.info("아직 획득한 배지가 없어요. 첫 기록부터 시작해 보세요!")
    else:
        columns = st.columns(3)

        for index, badge in enumerate(badges):
            with columns[index % 3].container(border=True):
                st.markdown(f"### {badge['name']}")
                st.write(badge["description"])
                st.caption(f"획득일: {badge['earned_date']}")


def show_reward_history(user_id):

    history = read_df("""
        SELECT event_date AS 날짜, title AS 내용, xp AS 경험치, points AS 포인트
        FROM reward_events
        WHERE user_id = ?
        ORDER BY event_date DESC, id DESC
    """, (user_id,))

    if history.empty:
        st.info("아직 받은 보상이 없어요.")
    else:
        history.insert(
            1,
            "구분",
            ["차감" if value < 0 else "보상" for value in history["포인트"]]
        )

        st.dataframe(history, width="stretch", hide_index=True)


# ============================================================
# 5. 주간 리포트
# ============================================================

def page_report():

    user = current_user()
    user_id = user["id"]
    goals = get_goals(user_id)
    profile = get_profile(user_id)

    log_event(user_id, "report_view")

    today = date.today()
    monday = today - timedelta(days=today.weekday())

    st.title("📊 주간 리포트")
    st.caption(f"{monday:%m월 %d일} ~ {today:%m월 %d일}")

    summary = daily_summary(user_id, monday, today, goals)
    week = summary[summary["recorded"]]

    if week.empty:
        st.warning("이번 주 기록이 아직 없어요.")
        st.page_link(PAGES["home"], label="홈에서 기록 시작하기", icon="🏠")
        return

    average_score = round(week["score"].mean(), 1)

    st.subheader("🌟 이번 주 생활 점수")

    st.metric("평균 점수", f"{average_score} / 100")
    st.progress(average_score / 100)

    if average_score >= 85:
        st.success("🏆 정말 좋은 한 주였어요!")
    elif average_score >= 70:
        st.success("🔥 좋은 흐름이에요! 계속 유지해 보세요.")
    elif average_score >= 50:
        st.info("🌱 잘하고 있어요. 작은 습관부터 꾸준히!")
    else:
        st.info("💪 기록을 시작한 것 자체가 좋은 출발이에요.")

    st.subheader("📌 이번 주 평균")

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("🚶 걸음", f"{week['steps'].mean():,.0f}")
    col2.metric("😴 수면", f"{week['sleep_hours'].mean():.1f}시간")
    col3.metric("💧 물", f"{week['water_ml'].mean():,.0f}mL")
    col4.metric("🏃 운동", f"{week['exercise_min'].mean():.0f}분")
    col5.metric("🥗 식사", f"{week['meals'].mean():.1f}끼")

    st.subheader("📈 일별 생활 점수")

    chart = summary.copy()
    chart["요일"] = [f"{WEEKDAYS_KO[day.weekday()]} ({day:%m/%d})" for day in chart["log_date"]]

    st.bar_chart(chart.set_index("요일")[["score"]].rename(columns={"score": "생활 점수"}))

    rates = pd.DataFrame([habit_rates(day, goals) for day in week.to_dict("records")]).mean()
    rates = rates.drop("mood")

    best = rates.idxmax()
    worst = rates.idxmin()

    st.subheader("🌟 이번 주 가장 돋보인 습관")
    st.success(f"**{HABIT_LABELS[best]}** 목표를 평균 {rates[best]:.0f}% 채웠어요!")

    st.subheader("🎯 다음 주 추천")

    title, message, proposed = build_recommendation(week, goals)

    st.info(f"**{HABIT_LABELS[worst]}** 습관을 조금 더 신경 써 보세요. {message}")

    if st.button("🎯 다음 주 목표 설정하기", width="stretch"):
        if proposed:
            st.session_state["pending_goals"] = proposed
        st.switch_page(PAGES["goals"])

    st.subheader("📝 이번 주 요약")

    st.write(
        f"이번 주에는 **{len(week)}일** 동안 기록했어요. "
        f"평균 생활 점수는 **{average_score}점**이고, "
        f"가장 잘 지킨 습관은 **{HABIT_LABELS[best]}**이에요. "
        "다음 주에도 완벽하게 하려고 하기보다 작은 행동을 꾸준히 이어 가 보세요. 🌱"
    )

    st.divider()

    # 유료 구독자 → 심화 리포트 / 무료 → 구독 안내

    if is_premium(user_id):
        show_deep_report(user_id, goals, profile, week, rates, monday)
    else:
        with st.container(border=True):
            st.subheader("💎 심화 리포트는 부스터 플러스 전용이에요")

            for benefit in PREMIUM_BENEFITS:
                st.write(f"- {benefit}")

            if st.button("구독 안내 보기", type="primary", width="stretch"):
                st.session_state["sub_stage"] = "info"
                st.switch_page(PAGES["subscription"])


def show_deep_report(user_id, goals, profile, week, rates, monday):

    st.header("💎 심화 리포트")

    last = daily_summary(user_id, monday - timedelta(days=7), monday - timedelta(days=1), goals)
    last = last[last["recorded"]]

    st.subheader("📊 지난주와 비교")

    def delta(column, digits=0):
        if last.empty:
            return None
        return round(week[column].mean() - last[column].mean(), digits)

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("생활 점수", f"{week['score'].mean():.1f}", delta("score", 1))
    col2.metric("걸음 수", f"{week['steps'].mean():,.0f}", delta("steps"))
    col3.metric("수면 (시간)", f"{week['sleep_hours'].mean():.1f}", delta("sleep_hours", 1))
    col4.metric("운동 (분)", f"{week['exercise_min'].mean():.0f}", delta("exercise_min"))

    if last.empty:
        st.caption("지난주 기록이 없어서 비교할 수 없어요.")

    st.subheader("🎯 습관별 목표 달성률 (%)")

    st.bar_chart(
        pd.DataFrame({
            "달성률": [rates[key] for key in rates.index]
        }, index=[HABIT_LABELS[key] for key in rates.index])
    )

    st.subheader("🏃 운동 종류별 시간")

    kinds = read_df("""
        SELECT kind AS 운동, SUM(minutes) AS 시간
        FROM workout_logs
        WHERE user_id = ? AND log_date >= ?
        GROUP BY kind
        ORDER BY 시간 DESC
    """, (user_id, monday.isoformat()))

    if kinds.empty:
        st.info("이번 주 운동 기록이 없어요.")
    else:
        st.bar_chart(kinds.set_index("운동"))

    st.subheader("😴 수면과 기분")

    paired = week[(week["sleep_hours"] > 0) & week["mood"].notna()]

    if len(paired) < 3:
        st.info("수면과 기분을 함께 기록한 날이 3일 이상이면 관계를 분석해 드려요.")
    else:
        relation = paired["sleep_hours"].corr(paired["mood"])

        if pd.isna(relation):
            st.info("이번 주에는 수면 시간이나 기분 변화가 거의 없었어요.")
        elif relation >= 0.3:
            st.success("잠을 충분히 잔 날 기분도 좋았어요. 수면 목표를 꼭 지켜 보세요!")
        elif relation <= -0.3:
            st.info("잠을 많이 잔 날 오히려 기분이 낮았어요. 잠의 질이나 기상 시간을 살펴보세요.")
        else:
            st.info("이번 주에는 수면 시간과 기분 사이에 뚜렷한 관계가 보이지 않았어요.")

    st.subheader("📅 요일별 흐름")

    best_day = week.loc[week["score"].idxmax()]
    worst_day = week.loc[week["score"].idxmin()]

    st.write(
        f"가장 좋았던 날은 **{WEEKDAYS_KO[best_day['log_date'].weekday()]}요일** "
        f"({best_day['score']:.0f}점), "
        f"아쉬웠던 날은 **{WEEKDAYS_KO[worst_day['log_date'].weekday()]}요일** "
        f"({worst_day['score']:.0f}점)이에요."
    )

    st.subheader("🤖 AI 심화 코칭")

    ai_coach_box(
        user_id,
        "deep_report",
        COACH_RULES + " 지난주와 비교해서 좋아진 점을 먼저 칭찬해 줘.",
        summary_for_ai(week, goals, profile["goal_type"])
        + "\n\n[지난주]\n"
        + summary_for_ai(last, goals, profile["goal_type"])
    )


# ============================================================
# 6. 구독 및 결제
# ============================================================

def page_subscription():

    user = current_user()
    user_id = user["id"]

    sub = get_subscription(user_id)

    show_flash()

    # 구독 관리 (구독 중) --------------------------------------------

    if is_premium(user_id) and not st.session_state.get("sub_upgrade"):

        plan = SUBSCRIPTION_PLANS[sub["plan"]]

        st.title("💎 구독 관리")

        col1, col2 = st.columns(2)

        col1.metric("이용 중인 상품", plan["name"])
        col2.metric("이용 기간", f"{sub['expires_at']}까지")

        if sub["plan"] == "trial":

            st.info("포인트 상점 체험권으로 이용 중이에요. 기간이 끝나면 자동으로 무료로 바뀌어요.")

            if st.button("정식 구독으로 바꾸기", width="stretch"):
                st.session_state["sub_upgrade"] = True
                st.session_state["sub_stage"] = "pay"
                st.rerun()

        elif sub["status"] == "canceled":

            st.info(
                f"해지가 요청된 상태예요. {sub['expires_at']}까지는 "
                "계속 이용할 수 있고, 그 뒤에는 자동으로 무료로 바뀌어요."
            )

            if st.button("해지 취소하기", width="stretch"):
                execute(
                    "UPDATE subscriptions SET status = 'active', canceled_at = NULL WHERE user_id = ?",
                    (user_id,)
                )
                flash("✅ 해지를 취소했어요. 계속 이용해 주셔서 고마워요!")
                st.rerun()

        else:

            st.success("부스터 플러스를 이용 중이에요.")

            with st.expander("구독 해지 요청"):

                agree = st.checkbox("해지해도 만료일까지는 이용할 수 있다는 것을 확인했어요.")

                if st.button("구독 해지 요청", disabled=not agree, width="stretch"):
                    execute(
                        "UPDATE subscriptions SET status = 'canceled', canceled_at = ? WHERE user_id = ?",
                        (now_str(), user_id)
                    )
                    flash("구독 해지가 요청됐어요.", "info")
                    st.rerun()

        st.subheader("결제 내역")

        payments = read_df("""
            SELECT created_at AS 일시, plan AS 상품, amount AS 금액, status AS 결과
            FROM payments
            WHERE user_id = ?
            ORDER BY id DESC
        """, (user_id,))

        payments["상품"] = [SUBSCRIPTION_PLANS[key]["name"] for key in payments["상품"]]
        payments["결과"] = ["성공" if value == "success" else "실패" for value in payments["결과"]]

        st.dataframe(payments, width="stretch", hide_index=True)

        return

    stage = st.session_state.get("sub_stage", "info")

    # 구독 안내 ------------------------------------------------------

    if stage == "info":

        st.title("💎 부스터 플러스")
        st.caption("더 정교한 분석과 코칭이 필요할 때")

        for benefit in PREMIUM_BENEFITS:
            st.write(f"- {benefit}")

        st.caption("기본 기록 · 목표 · 보상 · 기본 주간 리포트는 계속 무료예요.")

        col1, col2 = st.columns(2)

        for column, key in zip([col1, col2], PAID_PLANS):

            plan = SUBSCRIPTION_PLANS[key]

            with column.container(border=True):
                st.markdown(f"**{plan['name']}**")
                st.markdown(f"### {plan['price']:,}원")
                st.caption(f"{plan['days']}일 이용 · 시연용 예시 가격")

        if st.button("구독 신청하기", type="primary", width="stretch"):
            st.session_state["sub_stage"] = "pay"
            st.rerun()

    # 구독 신청 · 결제 -----------------------------------------------

    elif stage == "pay":

        st.title("💳 구독 신청 · 결제")

        st.warning(
            "시연용 가상 결제예요. 실제로 돈이 나가지 않고, "
            "카드 정보도 입력받지 않아요."
        )

        with st.form("payment_form"):

            plan_key = st.radio(
                "상품 선택",
                PAID_PLANS,
                format_func=lambda key: (
                    f"{SUBSCRIPTION_PLANS[key]['name']} · "
                    f"{SUBSCRIPTION_PLANS[key]['price']:,}원"
                )
            )

            simulate_fail = st.checkbox("결제 실패 상황 시험해 보기")

            submitted = st.form_submit_button("결제하기", type="primary", width="stretch")

        if submitted:

            if simulate_fail:
                record_payment(user_id, plan_key, "failed")
                st.session_state["sub_stage"] = "fail"
                st.rerun()

            record_payment(user_id, plan_key, "success")
            start_subscription(user_id, plan_key)
            update_badges(user_id)

            st.session_state.pop("sub_stage", None)
            st.session_state.pop("sub_upgrade", None)

            notify(user_id, "subscription", "💎 부스터 플러스 구독이 시작됐어요!", "subscription")

            flash("🎉 부스터 플러스 구독이 시작됐어요! 주간 리포트에서 심화 분석을 확인해 보세요.")

            st.switch_page(PAGES["home"])

        if st.button("뒤로", width="stretch"):
            st.session_state["sub_stage"] = "info"
            st.session_state.pop("sub_upgrade", None)
            st.rerun()

    # 결제 실패 안내 -------------------------------------------------

    elif stage == "fail":

        st.title("😥 결제에 실패했어요")

        st.error("결제가 완료되지 않았어요. 돈은 빠져나가지 않았어요.")

        st.write("잠시 후 다시 시도하거나, 다른 결제 수단을 선택해 주세요.")

        col1, col2 = st.columns(2)

        if col1.button("다시 결제하기", type="primary", width="stretch"):
            st.session_state["sub_stage"] = "pay"
            st.rerun()

        if col2.button("홈으로", width="stretch"):
            st.session_state.pop("sub_stage", None)
            st.session_state.pop("sub_upgrade", None)
            st.switch_page(PAGES["home"])


# ============================================================
# 7. 설정
# ============================================================

def page_settings():

    user = current_user()
    user_id = user["id"]

    settings = get_settings(user_id)

    st.title("⚙️ 설정")

    show_flash()

    notify_tab, profile_tab, consent_tab, game_tab, account_tab = st.tabs([
        "🔔 알림",
        "👤 프로필 수정",
        "📄 동의 내역",
        "🎮 보상 설정",
        "🙋 계정"
    ])

    # 알림 설정 ------------------------------------------------------

    with notify_tab:

        st.caption(
            "알림 시각이 지나도 기록이 비어 있으면 알림함으로 알려 드려요. "
            f"하루 최대 {MAX_REMINDERS_PER_DAY}번이고, 방해 금지 시간에는 보내지 않아요. "
            "(시연용: 실제 휴대폰 알림은 보내지 않아요)"
        )

        with st.form("notify_form"):

            enabled = st.toggle("알림 받기", value=bool(settings["notify_enabled"]))

            remind_time = st.time_input(
                "알림 시각",
                value=time.fromisoformat(settings["remind_time"]),
                step=1800
            )

            remind_sleep = st.checkbox("수면 기록 알림", value=bool(settings["remind_sleep"]))
            remind_workout = st.checkbox("운동 알림", value=bool(settings["remind_workout"]))
            remind_meal = st.checkbox("식사 기록 알림", value=bool(settings["remind_meal"]))

            st.markdown("**🌙 방해 금지 시간**")

            col1, col2 = st.columns(2)

            quiet_start = col1.time_input(
                "시작",
                value=time.fromisoformat(settings["quiet_start"]),
                step=1800
            )

            quiet_end = col2.time_input(
                "끝",
                value=time.fromisoformat(settings["quiet_end"]),
                step=1800
            )

            submitted = st.form_submit_button("💾 알림 설정 저장", width="stretch")

        if submitted:
            execute("""
                UPDATE user_settings
                SET notify_enabled = ?, remind_time = ?,
                    remind_sleep = ?, remind_workout = ?, remind_meal = ?,
                    quiet_start = ?, quiet_end = ?
                WHERE user_id = ?
            """, (
                int(enabled),
                remind_time.strftime("%H:%M"),
                int(remind_sleep),
                int(remind_workout),
                int(remind_meal),
                quiet_start.strftime("%H:%M"),
                quiet_end.strftime("%H:%M"),
                user_id
            ))
            flash("✅ 알림 설정을 저장했어요.")
            st.rerun()

        if st.button("🔔 알림 미리보기"):
            st.toast("오늘 운동 기록이 아직 비어 있어요. 10분만 움직여 볼까요?", icon="🔔")

    # 프로필 수정 ----------------------------------------------------

    with profile_tab:

        profile = get_profile(user_id)

        with st.form("profile_edit_form"):

            new_profile = profile_inputs(dict(profile))

            submitted = st.form_submit_button("💾 프로필 저장", width="stretch")

        if submitted:
            save_profile(user_id, new_profile)
            flash("✅ 프로필을 저장했어요. 목표도 바꾸고 싶다면 🎯 목표 설정에서 조정해 보세요.")
            st.switch_page(PAGES["home"])

    # 동의 내역 확인 · 철회 ------------------------------------------

    with consent_tab:

        consents = get_consents(user_id)

        for item, label, required, description in CONSENT_ITEMS:

            row = consents.get(item)
            agreed = bool(row and row["agreed"])

            with st.container(border=True):

                tag = "필수" if required else "선택"
                state = "✅ 동의함" if agreed else "⬜ 동의 안 함"

                st.markdown(f"**[{tag}] {label}** · {state}")
                st.caption(description)

                if row:
                    st.caption(f"변경일: {row['updated_at']}")

                if not required:

                    label_text = "동의 철회" if agreed else "동의하기"

                    if st.button(label_text, key=f"consent_{item}"):
                        save_consent(user_id, item, not agreed)
                        flash("✅ 동의 내역을 바꿨어요.")
                        st.rerun()

        with st.expander("⚠️ 필수 동의 철회 요청"):

            st.write(
                "필수 동의를 철회하면 **건강 프로필, 목표, 수면·운동·식사·걸음 기록이 "
                "모두 삭제**되고 서비스를 이용할 수 없어요. "
                "다시 이용하려면 동의와 프로필 입력부터 새로 해야 해요."
            )

            confirm = st.checkbox("위 내용을 확인했고, 데이터 삭제에 동의해요.")

            if st.button("필수 동의 철회", disabled=not confirm, type="primary"):

                delete_health_data(user_id)

                for item in REQUIRED_CONSENTS:
                    save_consent(user_id, item, False)

                st.session_state.clear()
                st.session_state["user_id"] = user_id

                st.rerun()

    # 보상 설정 ------------------------------------------------------

    with game_tab:

        st.write(
            f"운동 목표를 놓친 다음 날 포인트 {WORKOUT_MISS_PENALTY}점을 차감하는 규칙이에요. "
            "부담스럽다면 꺼도 괜찮아요."
        )

        penalty = st.toggle("차감 규칙 사용", value=bool(settings["penalty_enabled"]))

        auto_grace = st.toggle(
            "🛡️ 목표를 놓친 날 유예권 자동 사용",
            value=bool(settings["auto_grace"]),
            help="유예권은 🏆 보상 · 성취 → 포인트 상점에서 살 수 있어요."
        )

        show_in_ranking = st.toggle(
            "📸 카메라 챌린지 랭킹에 내 이름 보이기",
            value=bool(settings["show_in_ranking"]),
            help="끄면 랭킹에 '익명 부스터'로 나오고, 다른 사람이 나에게 도전장을 보낼 수 없어요."
        )

        changes = {
            "penalty_enabled": penalty,
            "auto_grace": auto_grace,
            "show_in_ranking": show_in_ranking
        }

        for column, value in changes.items():
            if value != bool(settings[column]):
                execute(
                    f"UPDATE user_settings SET {column} = ? WHERE user_id = ?",
                    (int(value), user_id)
                )
                st.rerun()

    # 계정 -----------------------------------------------------------

    with account_tab:

        st.write(f"**이름**: {user['name']}")
        st.write(f"**이메일**: {user['email']}")
        st.write(f"**가입일**: {user['created_at'][:10]}")

        st.page_link(PAGES["subscription"], label="구독 관리", icon="💎")
        st.page_link(PAGES["device"], label="기기 데이터 연동", icon="⌚")
        st.page_link(PAGES["goals"], label="목표 설정", icon="🎯")

        if st.button("로그아웃", width="stretch"):
            logout()


# ============================================================
# 관리자 - 핵심 지표
# ============================================================

def page_inbox():

    user = current_user()
    user_id = user["id"]

    st.title("🔔 알림함")
    st.caption("실천 알림, 보상·차감 소식, 도전장이 여기에 모여요.")

    rows = fetch_all("""
        SELECT * FROM notifications
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 50
    """, (user_id,))

    if not rows:
        st.info("아직 받은 알림이 없어요.")
        return

    if unread_count(user_id) and st.button("모두 읽음으로 표시"):
        execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
        st.rerun()

    for row in rows:

        with st.container(border=True):

            col1, col2 = st.columns([4, 1])

            mark = "🔵 " if not row["is_read"] else ""

            col1.write(f"{mark}{row['message']}")
            col1.caption(row["created_at"].replace("T", " "))

            if row["target"] in PAGES and col2.button(
                "보러 가기",
                key=f"notification_{row['id']}",
                width="stretch"
            ):
                execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (row["id"],))
                st.switch_page(PAGES[row["target"]])


# ============================================================
# 카메라 챌린지 (푸시업 · 스쿼트 개수 세기 + 대결)
#
# 브라우저에서 MediaPipe 자세 인식 도구로 관절 각도를 재서 개수를 센다.
# 영상은 서버로 보내지도, 저장하지도 않고 '개수'만 저장한다.
#   - 스쿼트: 엉덩이-무릎-발목 각도가 100도 아래로 내려갔다가 160도 위로 올라오면 1회
#   - 푸시업: 몸이 엎드린 자세이고, 어깨-팔꿈치-손목 각도가 90도 아래 → 150도 위면 1회
# ============================================================

REP_COUNTER_HTML = """
<div class="rc">
  <div class="rc-stage">
    <video class="rc-video" playsinline muted></video>
    <canvas class="rc-canvas"></canvas>
    <div class="rc-top">
      <div class="rc-count">0</div>
      <div class="rc-timer"></div>
    </div>
    <div class="rc-msg"></div>
  </div>
  <div class="rc-buttons">
    <button class="rc-btn rc-camera">📷 카메라 켜기</button>
    <button class="rc-btn rc-start" disabled>▶️ 시작</button>
    <button class="rc-btn rc-cancel" disabled>⏹️ 그만두기</button>
  </div>
  <div class="rc-hint"></div>
</div>
"""

REP_COUNTER_CSS = """
.rc { font-family: inherit; color: var(--st-text-color, #222); }
.rc-stage {
  position: relative;
  width: 100%;
  max-width: 640px;
  aspect-ratio: 4 / 3;
  margin: 0 auto;
  background: #111;
  border-radius: 16px;
  overflow: hidden;
}
.rc-video, .rc-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  transform: scaleX(-1);
}
.rc-top {
  position: absolute;
  top: 12px;
  left: 16px;
  right: 16px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  color: #fff;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.8);
  pointer-events: none;
}
.rc-count { font-size: 64px; font-weight: 800; line-height: 1; }
.rc-timer { font-size: 28px; font-weight: 700; }
.rc-msg {
  position: absolute;
  left: 50%;
  bottom: 16px;
  transform: translateX(-50%);
  max-width: 90%;
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.65);
  color: #fff;
  font-size: 16px;
  text-align: center;
}
.rc-msg[hidden] { display: none; }
.rc-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  max-width: 640px;
  margin: 12px auto 0;
}
.rc-btn {
  flex: 1 1 140px;
  padding: 10px 12px;
  border: 1px solid rgba(128, 128, 128, 0.4);
  border-radius: 10px;
  background: var(--st-secondary-background-color, #f0f2f6);
  color: inherit;
  font-size: 15px;
  cursor: pointer;
}
.rc-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.rc-start:not(:disabled) {
  background: var(--st-primary-color, #ff4b4b);
  border-color: transparent;
  color: #fff;
}
.rc-hint {
  max-width: 640px;
  margin: 8px auto 0;
  font-size: 14px;
  opacity: 0.75;
}
"""

REP_COUNTER_JS = """
const VISION_URL = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14";
const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task";

// 관절 번호: 11/12 어깨, 13/14 팔꿈치, 15/16 손목, 23/24 엉덩이, 25/26 무릎, 27/28 발목
const RULES = {
  squat: { sides: [[23, 25, 27], [24, 26, 28]], down: 100, up: 160, lying: false },
  pushup: { sides: [[11, 13, 15], [12, 14, 16]], down: 90, up: 150, lying: true },
};

const BONES = [
  [11, 12], [11, 13], [13, 15], [12, 14], [14, 16], [11, 23], [12, 24],
  [23, 24], [23, 25], [25, 27], [24, 26], [26, 28],
];

// 다시 그려져도 카메라가 두 번 켜지지 않도록 화면 전체에서 하나만 관리
window.__boosterRepCounters = window.__boosterRepCounters || new Map();
window.__boosterLandmarker = window.__boosterLandmarker || null;

function loadLandmarker() {
  if (!window.__boosterLandmarker) {
    window.__boosterLandmarker = (async () => {
      const vision = await import(`${VISION_URL}/vision_bundle.mjs`);
      const fileset = await vision.FilesetResolver.forVisionTasks(`${VISION_URL}/wasm`);
      const options = (delegate) => ({
        baseOptions: { modelAssetPath: MODEL_URL, delegate },
        runningMode: "VIDEO",
        numPoses: 1,
      });
      try {
        return await vision.PoseLandmarker.createFromOptions(fileset, options("GPU"));
      } catch (error) {
        return await vision.PoseLandmarker.createFromOptions(fileset, options("CPU"));
      }
    })();
    window.__boosterLandmarker.catch(() => {
      window.__boosterLandmarker = null;
    });
  }
  return window.__boosterLandmarker;
}

function seen(points, ids) {
  return ids.every((i) => points[i] && (points[i].visibility ?? 1) > 0.5);
}

function confidence(points, ids) {
  return ids.reduce((sum, i) => sum + (points[i].visibility ?? 1), 0);
}

function jointAngle(a, b, c, aspect) {
  const abx = (a.x - b.x) * aspect;
  const aby = a.y - b.y;
  const cbx = (c.x - b.x) * aspect;
  const cby = c.y - b.y;
  const size = Math.hypot(abx, aby) * Math.hypot(cbx, cby);
  if (!size) return 180;
  const cos = Math.max(-1, Math.min(1, (abx * cbx + aby * cby) / size));
  return (Math.acos(cos) * 180) / Math.PI;
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  const root = parentElement.querySelector(".rc");
  if (!root) return;

  const instance = data?.instance || "default";
  const previous = window.__boosterRepCounters.get(instance);
  if (previous) previous();

  const exercise = data?.exercise in RULES ? data.exercise : "squat";
  const duration = Number(data?.duration) || 30;
  const rule = RULES[exercise];

  const pick = (selector) => root.querySelector(selector);
  const video = pick(".rc-video");
  const canvas = pick(".rc-canvas");
  const ctx = canvas.getContext("2d");
  const countEl = pick(".rc-count");
  const timerEl = pick(".rc-timer");
  const msgEl = pick(".rc-msg");
  const cameraBtn = pick(".rc-camera");
  const startBtn = pick(".rc-start");
  const cancelBtn = pick(".rc-cancel");

  pick(".rc-hint").textContent = data?.how || "";

  let stream = null;
  let landmarker = null;
  let frame = 0;
  let alive = true;
  let phase = "idle"; // idle → ready → countdown → running → done
  let count = 0;
  let pose = "up";
  let smooth = null;
  let endAt = 0;
  let lastVideoTime = -1;
  const timers = [];

  const say = (text) => {
    msgEl.textContent = text;
    msgEl.hidden = !text;
  };

  const setButtons = () => {
    cameraBtn.disabled = phase !== "idle";
    startBtn.disabled = !(phase === "ready" || phase === "done");
    cancelBtn.disabled = !(phase === "countdown" || phase === "running");
  };

  const clearTimers = () => {
    timers.forEach(clearTimeout);
    timers.length = 0;
  };

  function stop() {
    alive = false;
    cancelAnimationFrame(frame);
    clearTimers();
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
    if (window.__boosterRepCounters.get(instance) === stop) {
      window.__boosterRepCounters.delete(instance);
    }
  }

  window.__boosterRepCounters.set(instance, stop);

  function draw(points) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!points) return;
    ctx.lineWidth = 4;
    ctx.strokeStyle = "rgba(0, 220, 140, 0.9)";
    ctx.fillStyle = "#ffffff";
    for (const [a, b] of BONES) {
      if (!seen(points, [a, b])) continue;
      ctx.beginPath();
      ctx.moveTo(points[a].x * canvas.width, points[a].y * canvas.height);
      ctx.lineTo(points[b].x * canvas.width, points[b].y * canvas.height);
      ctx.stroke();
    }
    for (const i of [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]) {
      if (!seen(points, [i])) continue;
      ctx.beginPath();
      ctx.arc(points[i].x * canvas.width, points[i].y * canvas.height, 5, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function measure(points, aspect) {
    // 카메라에 더 잘 보이는 쪽 몸을 사용
    const sides = rule.sides
      .filter((ids) => seen(points, ids))
      .sort((p, q) => confidence(points, q) - confidence(points, p));

    if (!sides.length) return { reason: "몸 전체가 화면에 보이게 해 주세요" };

    const ids = sides[0];

    if (rule.lying) {
      const shoulder = ids[0];
      const hip = shoulder === 11 ? 23 : 24;
      if (!seen(points, [hip])) return { reason: "엉덩이까지 화면에 보이게 해 주세요" };
      const dx = Math.abs(points[shoulder].x - points[hip].x) * aspect;
      const dy = Math.abs(points[shoulder].y - points[hip].y);
      if (dy > dx * 0.7) return { reason: "엎드린 자세가 옆에서 보이게 해 주세요" };
    }

    return { angle: jointAngle(points[ids[0]], points[ids[1]], points[ids[2]], aspect) };
  }

  function update(points, aspect) {
    if (phase !== "running") return;

    const result = points ? measure(points, aspect) : { reason: "몸 전체가 화면에 보이게 해 주세요" };

    if (result.angle === undefined) {
      say(result.reason);
      return;
    }

    say("");
    smooth = smooth === null ? result.angle : smooth * 0.5 + result.angle * 0.5;

    if (pose === "up" && smooth < rule.down) {
      pose = "down";
    } else if (pose === "down" && smooth > rule.up) {
      pose = "up";
      count += 1;
      countEl.textContent = String(count);
    }
  }

  function finish() {
    phase = "done";
    setButtons();
    timerEl.textContent = "끝!";
    say(`🎉 ${count}개! 기록을 저장하고 있어요`);
    setTriggerValue("result", { exercise, duration, reps: count, finishedAt: Date.now() });
  }

  function loop() {
    if (!alive) return;

    if (!root.isConnected) {
      stop();
      return;
    }

    if (landmarker && video.readyState >= 2 && video.currentTime !== lastVideoTime) {
      lastVideoTime = video.currentTime;
      if (canvas.width !== video.videoWidth) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
      }
      const detected = landmarker.detectForVideo(video, performance.now());
      const points = detected.landmarks && detected.landmarks[0];
      draw(points);
      update(points, video.videoWidth / video.videoHeight);
    }

    if (phase === "running") {
      const left = Math.max(0, Math.ceil((endAt - Date.now()) / 1000));
      timerEl.textContent = `${left}초`;
      if (left <= 0) finish();
    }

    frame = requestAnimationFrame(loop);
  }

  cameraBtn.onclick = async () => {
    cameraBtn.disabled = true;
    try {
      say("카메라를 켜는 중이에요...");
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
      if (!alive) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      video.srcObject = stream;
      await video.play();
      say("자세 인식 도구를 불러오는 중이에요... (처음 한 번은 조금 걸려요)");
      landmarker = await loadLandmarker();
      phase = "ready";
      setButtons();
      say("준비 완료! 자리를 잡고 ▶️ 시작을 누르세요");
      loop();
    } catch (error) {
      console.error(error);
      phase = "idle";
      setButtons();
      say(
        error && error.name === "NotAllowedError"
          ? "카메라 사용이 막혀 있어요. 주소창 왼쪽 아이콘을 눌러 카메라를 허용해 주세요."
          : "카메라나 자세 인식 도구를 불러오지 못했어요. 인터넷 연결과 카메라를 확인해 주세요."
      );
    }
  };

  startBtn.onclick = () => {
    clearTimers();
    count = 0;
    pose = "up";
    smooth = null;
    countEl.textContent = "0";
    timerEl.textContent = `${duration}초`;
    phase = "countdown";
    setButtons();
    [3, 2, 1].forEach((n, i) => {
      timers.push(setTimeout(() => phase === "countdown" && say(String(n)), i * 1000));
    });
    timers.push(
      setTimeout(() => {
        if (phase !== "countdown") return;
        phase = "running";
        setButtons();
        say("시작!");
        endAt = Date.now() + duration * 1000;
      }, 3000)
    );
  };

  cancelBtn.onclick = () => {
    clearTimers();
    phase = "ready";
    setButtons();
    timerEl.textContent = `${duration}초`;
    say("그만뒀어요. 이번 기록은 저장되지 않아요.");
  };

  countEl.textContent = "0";
  timerEl.textContent = `${duration}초`;
  setButtons();
  say("📷 카메라 켜기를 눌러 주세요");

  return stop;
}
"""

REP_COUNTER = st.components.v2.component(
    "booster_rep_counter",
    html=REP_COUNTER_HTML,
    css=REP_COUNTER_CSS,
    js=REP_COUNTER_JS
)


def challenge_label(exercise, duration):
    return f"{CHALLENGE_EXERCISES[exercise]['name']} {duration}초"


def best_reps(user_id, exercise, duration, since=None):

    row = fetch_one("""
        SELECT MAX(reps) AS best FROM challenge_records
        WHERE user_id = ? AND exercise = ? AND duration = ? AND record_date >= ?
    """, (user_id, exercise, duration, str(since or "0000-00-00")))

    return row["best"]


def week_range(day=None):
    day = day or date.today()
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def leaderboard(exercise, duration, start, end):
    """기간 안의 사용자별 최고 기록 순위."""

    board = read_df("""
        SELECT c.user_id, u.name, COALESCE(s.show_in_ranking, 1) AS show_in_ranking,
               MAX(c.reps) AS best, COUNT(*) AS plays
        FROM challenge_records c
        JOIN users u ON u.id = c.user_id
        LEFT JOIN user_settings s ON s.user_id = c.user_id
        WHERE c.exercise = ? AND c.duration = ? AND c.record_date BETWEEN ? AND ?
        GROUP BY c.user_id
        ORDER BY best DESC, plays ASC
    """, (exercise, duration, str(start), str(end)))

    if board.empty:
        return board

    board["rank"] = board["best"].rank(method="min", ascending=False).astype(int)

    board["display"] = [
        name if show else "익명 부스터"
        for name, show in zip(board["name"], board["show_in_ranking"])
    ]

    return board


def settle_weekly_champions():
    """지난주 1위에게 챔피언 보상 (주마다 한 번)."""

    last_monday, last_sunday = week_range(date.today() - timedelta(days=7))

    for exercise in CHALLENGE_EXERCISES:
        for duration in CHALLENGE_DURATIONS:

            board = leaderboard(exercise, duration, last_monday, last_sunday)

            if board.empty or board["best"].max() == 0:
                continue

            for user_id in board.loc[board["rank"] == 1, "user_id"]:

                if give_reward(
                    int(user_id),
                    f"champion_{exercise}_{duration}",
                    f"👑 주간 챔피언 · {challenge_label(exercise, duration)}",
                    50,
                    200,
                    last_monday
                ):
                    notify(
                        int(user_id),
                        "champion",
                        f"👑 지난주 {challenge_label(exercise, duration)} 랭킹 1위! "
                        "경험치 +50 · 포인트 +200을 받았어요.",
                        "challenge"
                    )
                    update_badges(int(user_id))


def expire_duels():
    limit = (datetime.now() - timedelta(days=DUEL_DAYS)).isoformat(timespec="seconds")
    execute(
        "UPDATE duels SET status = 'expired' WHERE status = 'pending' AND created_at < ?",
        (limit,)
    )


def resolve_duels(user, exercise, duration, reps):
    """받은 도전장 중 같은 종목·시간인 것을 이번 기록으로 결정한다."""

    duels = fetch_all("""
        SELECT d.*, u.name AS from_name FROM duels d
        JOIN users u ON u.id = d.from_user
        WHERE d.to_user = ? AND d.exercise = ? AND d.duration = ? AND d.status = 'pending'
    """, (user["id"], exercise, duration))

    results = []

    for duel in duels:

        if reps > duel["target_reps"]:
            status, mine, theirs = "won", "이겼어요! 🎉", "졌어요. 다시 도전해 보세요! 💪"
        elif reps < duel["target_reps"]:
            status, mine, theirs = "lost", "졌어요. 다음엔 이길 수 있어요! 💪", "이겼어요! 🎉"
        else:
            status, mine, theirs = "draw", "비겼어요! 🤝", "비겼어요! 🤝"

        execute("""
            UPDATE duels SET status = ?, result_reps = ?, resolved_at = ?
            WHERE id = ?
        """, (status, reps, now_str(), duel["id"]))

        label = challenge_label(exercise, duration)

        notify(
            duel["from_user"],
            "duel",
            f"⚔️ {user['name']}님과의 {label} 대결: {duel['target_reps']}개 vs {reps}개, {theirs}",
            "challenge"
        )

        if status == "won":
            give_reward(user["id"], f"duel_win_{duel['id']}", f"⚔️ 대결 승리 · {label}", 30, 50)
        elif status == "lost":
            give_reward(duel["from_user"], f"duel_win_{duel['id']}", f"⚔️ 대결 승리 · {label}", 30, 50)
            update_badges(duel["from_user"])

        results.append(f"{duel['from_name']}님과의 대결 {reps}개 vs {duel['target_reps']}개, {mine}")

    return results


def save_challenge_result(user, payload, exercise, duration):

    user_id = user["id"]

    # 화면에서 고른 종목·시간과 결과가 같은지, 개수가 말이 되는지 확인
    if payload.get("exercise") != exercise or int(payload.get("duration", 0)) != duration:
        return

    reps = int(payload.get("reps", 0))

    if not 0 <= reps <= duration * 3:
        st.error("인식된 개수가 너무 많아서 저장하지 않았어요. 다시 도전해 주세요.")
        return

    previous_best = best_reps(user_id, exercise, duration)

    execute("""
        INSERT INTO challenge_records (user_id, exercise, duration, reps, record_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, exercise, duration, reps, today_str(), now_str()))

    label = challenge_label(exercise, duration)

    if reps > 0:
        add_workout(
            user_id,
            date.today(),
            f"📸 {label} 챌린지 {reps}개",
            max(1, round(duration / 60)),
            "힘들게",
            "카메라 챌린지"
        )

        if workout_minutes(user_id, date.today()) >= get_goals(user_id)["exercise_min"]:
            give_reward(user_id, "workout_goal", "🏃 운동 목표 달성", 50, 100)

    give_reward(user_id, "challenge_play", "📸 카메라 챌린지 참여", 10, 20)

    messages = [f"🎉 {label} {reps}개를 기록했어요!"]

    if reps > 0 and (previous_best is None or reps > previous_best):
        give_reward(user_id, f"best_{exercise}_{duration}", "🏅 개인 최고 기록", 20, 30)
        messages.append("🏅 개인 최고 기록이에요!")

    messages += resolve_duels(user, exercise, duration, reps)

    after_record(user_id)

    flash(" ".join(messages))

    st.rerun()


def show_rank_table(board, user_id):

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    table = pd.DataFrame({
        "순위": [f"{medals.get(rank, '')} {rank}위" for rank in board["rank"]],
        "이름": [
            f"{name} (나)" if member == user_id else name
            for name, member in zip(board["display"], board["user_id"])
        ],
        "최고 기록": [f"{best}개" for best in board["best"]],
        "도전 횟수": board["plays"]
    })

    st.dataframe(table, width="stretch", hide_index=True)


def page_challenge():

    user = current_user()
    user_id = user["id"]

    expire_duels()
    settle_weekly_champions()

    st.title("📸 카메라 챌린지")
    st.caption(
        "카메라가 푸시업·스쿼트 개수를 세어 줘요. 영상은 저장하거나 보내지 않고 "
        "이 컴퓨터 안에서만 분석해요. 저장되는 건 개수뿐이에요."
    )

    show_flash()

    # '도전 받기'로 고른 종목·시간은 선택 칸을 그리기 전에 넣어야 함
    if "challenge_pick" in st.session_state:
        picked_exercise, picked_duration = st.session_state.pop("challenge_pick")
        st.session_state["challenge_exercise"] = picked_exercise
        st.session_state["challenge_duration"] = picked_duration

    col1, col2 = st.columns(2)

    exercise = col1.radio(
        "종목",
        list(CHALLENGE_EXERCISES),
        format_func=lambda key: CHALLENGE_EXERCISES[key]["name"],
        horizontal=True,
        key="challenge_exercise"
    )

    duration = col2.radio(
        "시간",
        CHALLENGE_DURATIONS,
        format_func=lambda seconds: f"{seconds}초",
        horizontal=True,
        key="challenge_duration"
    )

    label = challenge_label(exercise, duration)
    monday, sunday = week_range()

    play_tab, rank_tab, duel_tab, history_tab = st.tabs(
        ["▶️ 도전하기", "🏆 주간 랭킹", "⚔️ 도전장", "📜 내 기록"]
    )

    # 도전하기 -------------------------------------------------------

    with play_tab:

        received = fetch_all("""
            SELECT d.target_reps, u.name FROM duels d
            JOIN users u ON u.id = d.from_user
            WHERE d.to_user = ? AND d.exercise = ? AND d.duration = ? AND d.status = 'pending'
        """, (user_id, exercise, duration))

        for duel in received:
            st.info(f"⚔️ {duel['name']}님의 도전장: **{duel['target_reps']}개**보다 많이 하면 승리!")

        week_best = best_reps(user_id, exercise, duration, monday)
        all_best = best_reps(user_id, exercise, duration)

        col1, col2 = st.columns(2)
        col1.metric("이번 주 내 최고", f"{week_best or 0}개")
        col2.metric("역대 내 최고", f"{all_best or 0}개")

        st.warning(
            "주변 물건을 치우고 미끄럽지 않은 곳에서 하세요. "
            "아프거나 어지러우면 바로 멈추세요. 개수보다 바른 자세가 중요해요."
        )

        result = REP_COUNTER(
            key=f"rep_counter_{exercise}_{duration}",
            data={
                "instance": "challenge",
                "exercise": exercise,
                "duration": duration,
                "how": CHALLENGE_EXERCISES[exercise]["how"]
            },
            on_result_change=lambda: None
        )

        payload = getattr(result, "result", None) if result is not None else None

        if isinstance(payload, dict):

            # 같은 결과가 두 번 저장되지 않게
            token = payload.get("finishedAt")
            saved = st.session_state.setdefault("saved_challenges", set())

            if token not in saved:
                saved.add(token)
                save_challenge_result(user, payload, exercise, duration)

        st.caption(
            "카메라가 안 켜지면 주소창 왼쪽 아이콘에서 카메라를 허용해 주세요. "
            "자세 인식 도구는 인터넷에서 불러오기 때문에 인터넷 연결이 필요해요."
        )

    # 주간 랭킹 ------------------------------------------------------

    with rank_tab:

        st.caption(f"{label} · {monday:%m월 %d일} ~ {sunday:%m월 %d일} · 매주 1위는 포인트 200점!")

        board = leaderboard(exercise, duration, monday, sunday)

        st.page_link(PAGES["ranking"], label="기간·종합 순위는 순위표에서 보기", icon="🏆")

        if board.empty:
            st.info("이번 주 기록이 아직 없어요. 첫 번째 도전자가 되어 보세요!")
        else:
            show_rank_table(board, user_id)

            mine = board[board["user_id"] == user_id]

            if mine.empty:
                st.caption("아직 이번 주 기록이 없어요. 도전하고 랭킹에 올라 보세요!")
            else:
                my_rank = int(mine["rank"].iloc[0])
                my_best = int(mine["best"].iloc[0])
                above = board[board["best"] > my_best]

                if above.empty:
                    st.success(f"🥇 지금 {my_rank}위예요! 1위를 지켜 보세요.")
                else:
                    gap = int(above["best"].min()) - my_best + 1
                    st.info(f"지금 {my_rank}위예요. **{gap}개**만 더 하면 한 계단 올라가요!")

    # 도전장 ---------------------------------------------------------

    with duel_tab:

        st.caption(
            f"내 이번 주 최고 기록으로 도전장을 보내요. 상대가 {DUEL_DAYS}일 안에 "
            "같은 종목·시간으로 도전하면 승패가 정해지고, 이긴 사람은 포인트 50점을 받아요."
        )

        st.subheader("받은 도전장")

        inbox = fetch_all("""
            SELECT d.*, u.name AS from_name FROM duels d
            JOIN users u ON u.id = d.from_user
            WHERE d.to_user = ? AND d.status = 'pending'
            ORDER BY d.id DESC
        """, (user_id,))

        if not inbox:
            st.caption("받은 도전장이 없어요.")

        for duel in inbox:

            with st.container(border=True):

                col1, col2 = st.columns([3, 1])

                col1.write(
                    f"**{duel['from_name']}**님 · "
                    f"{challenge_label(duel['exercise'], duel['duration'])} "
                    f"**{duel['target_reps']}개**"
                )
                col1.caption(f"받은 날: {duel['created_at'][:10]}")

                if col2.button("도전 받기", key=f"accept_duel_{duel['id']}", width="stretch"):
                    st.session_state["challenge_pick"] = (duel["exercise"], duel["duration"])
                    flash("⚔️ 종목과 시간을 맞춰 두었어요. '▶️ 도전하기' 탭에서 시작하세요!", "info")
                    st.rerun()

        st.subheader("도전장 보내기")

        my_best = best_reps(user_id, exercise, duration, monday)

        opponents = fetch_all("""
            SELECT u.id, u.name FROM users u
            LEFT JOIN user_settings s ON s.user_id = u.id
            WHERE u.id != ? AND COALESCE(s.show_in_ranking, 1) = 1
            ORDER BY u.name
        """, (user_id,))

        if not my_best:
            st.info(f"먼저 {label}에 도전해서 이번 주 기록을 만들어 주세요.")
        elif not opponents:
            st.info("도전장을 보낼 수 있는 다른 사용자가 아직 없어요.")
        else:
            names = {row["id"]: f"{row['name']} (#{row['id']})" for row in opponents}

            with st.form("duel_form"):

                opponent = st.selectbox("상대", list(names), format_func=names.get)

                st.write(f"보낼 기록: **{label} {my_best}개**")

                submitted = st.form_submit_button("⚔️ 도전장 보내기", width="stretch")

            if submitted:

                exists = fetch_one("""
                    SELECT 1 FROM duels
                    WHERE from_user = ? AND to_user = ? AND exercise = ? AND duration = ?
                      AND status = 'pending'
                """, (user_id, opponent, exercise, duration))

                if exists:
                    st.warning("이 상대에게 같은 종목의 도전장을 이미 보냈어요. 결과를 기다려 주세요.")
                else:
                    execute("""
                        INSERT INTO duels (from_user, to_user, exercise, duration, target_reps, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (user_id, opponent, exercise, duration, my_best, now_str()))

                    notify(
                        opponent,
                        "duel",
                        f"⚔️ {user['name']}님이 {label} {my_best}개로 도전장을 보냈어요! "
                        f"{DUEL_DAYS}일 안에 넘어 보세요.",
                        "challenge"
                    )

                    flash(f"⚔️ {names[opponent]}님에게 도전장을 보냈어요!")
                    st.rerun()

        st.subheader("보낸 도전장")

        sent = read_df("""
            SELECT d.created_at AS 보낸날, u.name AS 상대, d.exercise, d.duration,
                   d.target_reps AS 내기록, d.result_reps AS 상대기록, d.status
            FROM duels d JOIN users u ON u.id = d.to_user
            WHERE d.from_user = ?
            ORDER BY d.id DESC
            LIMIT 20
        """, (user_id,))

        if sent.empty:
            st.caption("보낸 도전장이 없어요.")
        else:
            status_text = {
                "pending": "⏳ 기다리는 중",
                "won": "😢 상대 승리",
                "lost": "🎉 내 승리",
                "draw": "🤝 무승부",
                "expired": "⌛ 기간 만료"
            }

            sent["종목"] = [
                challenge_label(exercise_key, int(seconds))
                for exercise_key, seconds in zip(sent["exercise"], sent["duration"])
            ]
            sent["결과"] = [status_text.get(value, value) for value in sent["status"]]
            sent["보낸날"] = sent["보낸날"].str[:10]

            st.dataframe(
                sent[["보낸날", "상대", "종목", "내기록", "상대기록", "결과"]],
                width="stretch",
                hide_index=True
            )

    # 내 기록 --------------------------------------------------------

    with history_tab:

        history = read_df("""
            SELECT created_at, reps FROM challenge_records
            WHERE user_id = ? AND exercise = ? AND duration = ?
            ORDER BY id
        """, (user_id, exercise, duration))

        if history.empty:
            st.info(f"아직 {label} 기록이 없어요.")
        else:
            history["도전"] = range(1, len(history) + 1)

            st.line_chart(history.set_index("도전")[["reps"]].rename(columns={"reps": "개수"}))

            history["일시"] = history["created_at"].str.replace("T", " ")

            st.dataframe(
                history[["일시", "reps"]].rename(columns={"reps": "개수"}).iloc[::-1],
                width="stretch",
                hide_index=True
            )


# ============================================================
# 순위표 (앱 사용자끼리 카메라 챌린지 기록 겨루기)
# ============================================================

RANKING_PERIODS = {
    "week": "이번 주",
    "month": "이번 달",
    "all": "전체 기간"
}


def ranking_metrics():
    """순위 기준: 종합 누적 개수 + 종목·시간별 최고 기록."""

    metrics = {"total": "🔥 종합 (푸시업 + 스쿼트 누적 개수)"}

    for exercise in CHALLENGE_EXERCISES:
        for duration in CHALLENGE_DURATIONS:
            metrics[f"{exercise}_{duration}"] = f"{challenge_label(exercise, duration)} 최고 기록"

    return metrics


def period_range(period):

    today = date.today()

    if period == "week":
        return week_range(today)

    if period == "month":
        first = today.replace(day=1)
        next_month = (first + timedelta(days=32)).replace(day=1)
        return first, next_month - timedelta(days=1)

    return date(2000, 1, 1), today


def ranking_board(metric, period):
    """사용자별 점수와 순위. 종합은 누적 개수, 나머지는 최고 기록."""

    start, end = period_range(period)

    if metric == "total":

        board = read_df("""
            SELECT c.user_id, u.name, COALESCE(s.show_in_ranking, 1) AS show_in_ranking,
                   SUM(c.reps) AS score, COUNT(*) AS plays
            FROM challenge_records c
            JOIN users u ON u.id = c.user_id
            LEFT JOIN user_settings s ON s.user_id = c.user_id
            WHERE c.record_date BETWEEN ? AND ?
            GROUP BY c.user_id
        """, (str(start), str(end)))

    else:

        exercise, duration = metric.rsplit("_", 1)

        board = leaderboard(exercise, int(duration), start, end).rename(
            columns={"best": "score"}
        )

    if board.empty:
        return board

    board = board[board["score"] > 0].sort_values(
        ["score", "plays"],
        ascending=[False, True]
    )

    if board.empty:
        return board

    board["rank"] = board["score"].rank(method="min", ascending=False).astype(int)

    board["display"] = [
        name if show else "익명 부스터"
        for name, show in zip(board["name"], board["show_in_ranking"])
    ]

    return board.reset_index(drop=True)


def my_ranking_summary(user_id):
    """홈 화면용: 이번 주 종합 순위."""

    board = ranking_board("total", "week")

    if board.empty:
        return None

    mine = board[board["user_id"] == user_id]

    if mine.empty:
        return None

    return int(mine["rank"].iloc[0]), len(board), int(mine["score"].iloc[0])


def page_ranking():

    user = current_user()
    user_id = user["id"]

    settle_weekly_champions()

    st.title("🏆 순위표")
    st.caption(
        "카메라 챌린지 기록으로 Life of Booster 사용자들과 겨뤄요. "
        "카메라가 센 개수만 순위에 올라가요."
    )

    metrics = ranking_metrics()

    col1, col2 = st.columns([1, 2])

    period = col1.radio(
        "기간",
        list(RANKING_PERIODS),
        format_func=RANKING_PERIODS.get,
        horizontal=True,
        key="ranking_period"
    )

    metric = col2.selectbox(
        "순위 기준",
        list(metrics),
        format_func=metrics.get,
        key="ranking_metric"
    )

    unit = "누적" if metric == "total" else "최고"
    start, end = period_range(period)

    if period != "all":
        st.caption(f"{start:%Y년 %m월 %d일} ~ {end:%m월 %d일}")

    board = ranking_board(metric, period)

    if board.empty:
        st.info("아직 이 기간에 기록이 없어요. 첫 번째로 순위에 올라 보세요!")
        st.page_link(PAGES["challenge"], label="카메라 챌린지 하러 가기", icon="📸")
        return

    # 시상대 (1~3위)

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    podium = board[board["rank"] <= 3]

    columns = st.columns(3)

    for index, row in enumerate(podium.head(3).itertuples()):

        with columns[index].container(border=True):

            me = " (나)" if row.user_id == user_id else ""

            st.markdown(f"### {medals[row.rank]} {row.rank}위")
            st.markdown(f"**{row.display}{me}**")
            st.metric(f"{unit} 개수", f"{int(row.score)}개")

    # 내 순위

    mine = board[board["user_id"] == user_id]

    if mine.empty:
        st.info("아직 이 순위표에 내 기록이 없어요. 도전해서 이름을 올려 보세요!")
    else:
        my_rank = int(mine["rank"].iloc[0])
        my_score = int(mine["score"].iloc[0])
        above = board[board["score"] > my_score]

        if above.empty:
            st.success(f"👑 {len(board)}명 중 **1위**예요! 자리를 지켜 보세요.")
        else:
            gap = int(above["score"].min()) - my_score + 1
            st.info(
                f"{len(board)}명 중 **{my_rank}위**예요. "
                f"**{gap}개**만 더 하면 한 계단 올라가요! 💪"
            )

    # 전체 순위

    st.subheader("📋 전체 순위")

    table = pd.DataFrame({
        "순위": [f"{medals.get(rank, '')} {rank}위".strip() for rank in board["rank"]],
        "이름": [
            f"{name} (나)" if member == user_id else name
            for name, member in zip(board["display"], board["user_id"])
        ],
        f"{unit} 개수": [f"{int(score)}개" for score in board["score"]],
        "도전 횟수": board["plays"].astype(int)
    })

    my_rows = set(board.index[board["user_id"] == user_id])

    st.dataframe(
        table.style.apply(
            lambda row: [
                "background-color: rgba(255, 193, 7, 0.25); font-weight: bold"
                if row.name in my_rows else ""
            ] * len(row),
            axis=1
        ),
        width="stretch",
        hide_index=True
    )

    st.caption(
        "같은 점수면 같은 순위예요. 이번 주 종목별 1위는 다음 주에 포인트 200점을 받아요. "
        "랭킹에 이름을 숨기려면 ⚙️ 설정 → 보상 설정에서 끌 수 있어요."
    )

    col1, col2 = st.columns(2)

    col1.page_link(PAGES["challenge"], label="기록 올리러 가기", icon="📸")
    col2.page_link(PAGES["challenge"], label="도전장 보내기", icon="⚔️")


def mask_email(email):
    name, _, domain = email.partition("@")
    return f"{name[:2]}{'*' * max(1, len(name) - 2)}@{domain}"


def page_admin():

    user = current_user()

    if not is_admin(user):
        st.error("관리자만 볼 수 있는 화면이에요.")
        return

    st.title("🛠️ 관리자 · 핵심 지표")

    today = date.today()
    week_ago = (today - timedelta(days=6)).isoformat()
    monday = (today - timedelta(days=today.weekday())).isoformat()

    users = read_df("SELECT id, email, name, created_at FROM users")
    events = read_df("SELECT user_id, event, event_date FROM activity_events")

    if users.empty:
        st.info("아직 가입한 사용자가 없어요.")
        return

    users["joined"] = pd.to_datetime(users["created_at"]).dt.date
    events["event_date"] = pd.to_datetime(events["event_date"]).dt.date

    total = len(users)

    weekly_active = set(events.loc[events["event_date"] >= date.fromisoformat(week_ago), "user_id"])
    wau = len(weekly_active)

    def revisit_rate(days):
        """가입 후 1~days일 사이에 다시 방문한 비율."""

        eligible = users[users["joined"] <= today - timedelta(days=days)]

        if eligible.empty:
            return None

        returned = 0

        for row in eligible.itertuples():
            visits = events[
                (events["user_id"] == row.id)
                & (events["event_date"] > row.joined)
                & (events["event_date"] <= row.joined + timedelta(days=days))
            ]
            returned += not visits.empty

        return returned / len(eligible) * 100

    recorded_today = {
        row["user_id"]
        for row in fetch_all("""
            SELECT user_id FROM daily_status WHERE log_date = :d
            UNION SELECT user_id FROM sleep_logs WHERE log_date = :d
            UNION SELECT user_id FROM workout_logs WHERE log_date = :d
            UNION SELECT user_id FROM meal_logs WHERE log_date = :d
        """, {"d": today.isoformat()})
    }

    active_today = set(events.loc[events["event_date"] == today, "user_id"])

    goal_today = {
        row["user_id"]
        for row in fetch_all(
            "SELECT user_id FROM reward_events WHERE code = 'workout_goal' AND event_date = ?",
            (today.isoformat(),)
        )
    }

    report_viewers = set(events.loc[
        (events["event"] == "report_view")
        & (events["event_date"] >= date.fromisoformat(monday)),
        "user_id"
    ])

    streaks = [get_streak(user_id, get_goals(user_id)) for user_id in users["id"]]

    # 체험권 사용자는 유료 전환으로 세지 않음
    subscribers = read_df(
        "SELECT user_id, status, expires_at FROM subscriptions WHERE plan != 'trial'"
    )
    active_subs = subscribers[subscribers["expires_at"] >= today.isoformat()]

    payers = fetch_one(
        "SELECT COUNT(DISTINCT user_id) AS n FROM payments WHERE status = 'success'"
    )["n"]

    def percent(part, whole):
        return f"{part / whole * 100:.0f}%" if whole else "-"

    def fmt(value):
        return "-" if value is None else f"{value:.0f}%"

    st.subheader("👥 사용자")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("전체 가입자", f"{total}명")
    col2.metric("주간 활성 사용자", f"{wau}명")
    col3.metric("7일 재방문율", fmt(revisit_rate(7)))
    col4.metric("30일 재방문율", fmt(revisit_rate(30)))

    st.subheader("📈 습관 형성")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("오늘 기록 완료율", percent(len(recorded_today & active_today), len(active_today)))
    col2.metric("오늘 운동 목표 달성률", percent(len(goal_today), len(recorded_today)))
    col3.metric("주간 리포트 확인율", percent(len(report_viewers & weekly_active), wau))
    col4.metric("평균 연속 달성", f"{sum(streaks) / len(streaks):.1f}일")

    st.subheader("💎 구독")

    col1, col2 = st.columns(2)

    col1.metric("무료 → 유료 전환율", percent(payers, total))
    col2.metric(
        "구독 유지율",
        percent(len(active_subs[active_subs["status"] == "active"]), payers)
    )

    st.subheader("📋 사용자 목록")
    st.caption("개인정보 보호를 위해 건강 기록은 보여 주지 않아요.")

    last_seen = events.groupby("user_id")["event_date"].max()

    table = pd.DataFrame({
        "번호": users["id"],
        "이름": users["name"],
        "이메일": [mask_email(email) for email in users["email"]],
        "가입일": users["joined"].astype(str),
        "마지막 방문": [str(last_seen.get(user_id, "-")) for user_id in users["id"]],
        "구독": [
            "구독 중" if user_id in set(active_subs["user_id"]) else "무료"
            for user_id in users["id"]
        ]
    })

    st.dataframe(table, width="stretch", hide_index=True)

    st.subheader("🤖 맞춤 추천 반응")

    feedback = read_df("""
        SELECT action, COALESCE(reason, '이유 없음') AS reason, COUNT(*) AS n
        FROM recommendation_feedback
        GROUP BY action, reason
    """)

    if feedback.empty:
        st.info("아직 추천에 대한 반응이 없어요.")
    else:
        accepted = feedback.loc[feedback["action"] == "accepted", "n"].sum()
        st.metric("추천 수락률", percent(accepted, feedback["n"].sum()))

        rejected = feedback[feedback["action"] == "rejected"]

        if not rejected.empty:
            st.caption("거절 이유 (추천 품질 개선용)")
            st.bar_chart(rejected.set_index("reason")[["n"]].rename(columns={"n": "건수"}))

    st.subheader("📸 카메라 챌린지")

    challenge = fetch_one("""
        SELECT COUNT(*) AS plays, COUNT(DISTINCT user_id) AS players
        FROM challenge_records
        WHERE record_date >= ?
    """, (monday,))

    col1, col2 = st.columns(2)

    col1.metric("이번 주 도전 횟수", f"{challenge['plays']}회")
    col2.metric("이번 주 참여자", f"{challenge['players']}명")


# ============================================================
# 화면 등록 · 이동
# ============================================================

PAGES = {
    "auth": st.Page(page_auth, title="로그인", icon="🔑", url_path="login"),
    "consent": st.Page(page_consent, title="동의", icon="📄", url_path="consent"),
    "onboarding": st.Page(page_profile_onboarding, title="건강 프로필", icon="👤", url_path="onboarding"),
    "starter": st.Page(page_starter_plan, title="시작 계획", icon="🎉", url_path="starter"),
    "home": st.Page(page_home, title="홈", icon="🏠", url_path="home", default=True),
    "goals": st.Page(page_goals, title="목표 설정", icon="🎯", url_path="goals"),
    "sleep": st.Page(page_sleep, title="수면 기록", icon="😴", url_path="sleep"),
    "workout": st.Page(page_workout, title="운동", icon="🏃", url_path="workout"),
    "meal": st.Page(page_meal, title="식단", icon="🥗", url_path="meal"),
    "device": st.Page(page_device, title="기기 연동", icon="⌚", url_path="device"),
    "rewards": st.Page(page_rewards, title="보상 · 성취", icon="🏆", url_path="rewards"),
    "challenge": st.Page(page_challenge, title="카메라 챌린지", icon="📸", url_path="challenge"),
    "ranking": st.Page(page_ranking, title="순위표", icon="🏆", url_path="ranking"),
    "inbox": st.Page(page_inbox, title="알림함", icon="🔔", url_path="inbox"),
    "report": st.Page(page_report, title="주간 리포트", icon="📊", url_path="report"),
    "subscription": st.Page(page_subscription, title="구독", icon="💎", url_path="subscription"),
    "settings": st.Page(page_settings, title="설정", icon="⚙️", url_path="settings"),
    "admin": st.Page(page_admin, title="관리자", icon="🛠️", url_path="admin")
}


def show_sidebar(user):

    user_id = user["id"]
    xp, points = get_progress(user_id)
    level, level_name, _, _ = get_level(xp)

    with st.sidebar:

        st.markdown(f"### 🚀 {user['name']}님")

        if is_premium(user_id):
            st.caption("💎 부스터 플러스 이용 중")

        st.write(f"**{level_name}** · 레벨 {level}")
        st.caption(f"경험치 {xp:,} · 포인트 {points:,}")

        if st.button("로그아웃", key="sidebar_logout", width="stretch"):
            logout()


def main():

    user = current_user()

    # 1. 로그인 상태?
    if user is None:
        st.navigation([PAGES["auth"]], position="hidden").run()
        return

    user_id = user["id"]

    # 2. 필수 동의 완료?
    if not required_consents_ok(user_id):
        st.navigation([PAGES["consent"]], position="hidden").run()
        return

    # 3. 건강 프로필 입력
    if get_profile(user_id) is None:
        st.navigation([PAGES["onboarding"]], position="hidden").run()
        return

    if st.session_state.get("show_starter_plan"):
        st.navigation([PAGES["starter"]], position="hidden").run()
        return

    log_event(user_id, "visit")

    goals = get_goals(user_id)
    settings = get_settings(user_id)

    # 어제 결과 정산 (유예권 자동 사용 / 운동 목표 미달성 차감, 하루 한 번)
    settle_yesterday(user_id, goals, settings)

    # 실천 알림 (하루 최대 5번, 방해 금지 시간 제외)
    generate_reminders(user_id, settings, goals)

    unread = unread_count(user_id)

    # 메뉴에 읽지 않은 알림 개수 표시 (주소는 PAGES["inbox"]와 같음)
    inbox_page = st.Page(
        page_inbox,
        title=f"알림함 ({unread})" if unread else "알림함",
        icon="🔔",
        url_path="inbox"
    )

    sections = {
        "홈 및 목표": [PAGES["home"], inbox_page, PAGES["goals"]],
        "생활 기록": [PAGES["sleep"], PAGES["workout"], PAGES["meal"], PAGES["device"]],
        "보상 · 대결 · 리포트": [PAGES["rewards"], PAGES["challenge"], PAGES["ranking"], PAGES["report"]],
        "구독 · 설정": [PAGES["subscription"], PAGES["settings"]]
    }

    if is_admin(user):
        sections["관리자"] = [PAGES["admin"]]

    page = st.navigation(sections)

    show_sidebar(user)

    st.sidebar.caption(DISCLAIMER)

    page.run()


main()
