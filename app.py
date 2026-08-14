import os
import sqlite3
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "life_of_booster.db"

st.set_page_config(
    page_title="Life of Booster",
    page_icon="🚀",
    layout="wide",
)

# ---------- Database ----------
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_log (
            log_date TEXT PRIMARY KEY,
            steps INTEGER NOT NULL,
            sleep_hours REAL NOT NULL,
            water_ml INTEGER NOT NULL,
            exercise_min INTEGER NOT NULL,
            mood INTEGER NOT NULL,
            note TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_log(log_date, steps, sleep_hours, water_ml, exercise_min, mood, note):
    conn = get_conn()
    conn.execute("""
        INSERT INTO daily_log
        (log_date, steps, sleep_hours, water_ml, exercise_min, mood, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(log_date) DO UPDATE SET
            steps=excluded.steps,
            sleep_hours=excluded.sleep_hours,
            water_ml=excluded.water_ml,
            exercise_min=excluded.exercise_min,
            mood=excluded.mood,
            note=excluded.note
    """, (str(log_date), steps, sleep_hours, water_ml, exercise_min, mood, note))
    conn.commit()
    conn.close()

def load_logs():
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM daily_log ORDER BY log_date DESC", conn
    )
    conn.close()
    return df

# ---------- Scoring ----------
def clamp(value, low=0, high=100):
    return max(low, min(high, value))

def calculate_score(steps, sleep_hours, water_ml, exercise_min, mood):
    step_score = clamp(steps / 8000 * 100)
    sleep_score = clamp(100 - abs(sleep_hours - 8) * 25)
    water_score = clamp(water_ml / 1500 * 100)
    exercise_score = clamp(exercise_min / 30 * 100)
    mood_score = clamp(mood / 5 * 100)

    score = (
        step_score * 0.25
        + sleep_score * 0.20
        + water_score * 0.15
        + exercise_score * 0.25
        + mood_score * 0.15
    )
    return round(score)

def get_mission(steps, sleep_hours, water_ml, exercise_min, mood):
    items = [
        ("steps", 8000 - steps, "🚶 10분 걷기 미션", "가볍게 10분 정도 걸어보세요."),
        ("sleep", 8 - sleep_hours, "😴 수면 준비 미션", "오늘은 잠들기 30분 전부터 화면을 줄여보세요."),
        ("water", 1500 - water_ml, "💧 물 마시기 미션", "물 한 컵을 마시고 잠시 쉬어보세요."),
        ("exercise", 30 - exercise_min, "🏃 움직임 미션", "가볍게 스트레칭이나 산책을 해보세요."),
        ("mood", 5 - mood, "🙂 기분 전환 미션", "좋아하는 음악을 듣거나 잠깐 쉬어보세요."),
    ]
    # 가장 부족한 항목을 우선 추천
    positive = [x for x in items if x[1] > 0]
    if not positive:
        return "🎉 오늘 목표를 대부분 달성했어요!", "지금처럼 꾸준히 이어가 보세요."
    chosen = max(positive, key=lambda x: x[1])
    return chosen[2], chosen[3]

def calculate_points(score):
    return score * 10

def calculate_streak(df):
    if df.empty:
        return 0

    dates = set(pd.to_datetime(df["log_date"]).dt.date)
    today = date.today()

    # 오늘 기록이 없으면 어제부터 계산
    current = today if today in dates else today - timedelta(days=1)
    streak = 0
    while current in dates:
        streak += 1
        current -= timedelta(days=1)
    return streak

# ---------- Optional AI ----------
def ai_recommendation(score, steps, sleep_hours, water_ml, exercise_min, mood):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        mission_title, mission_text = get_mission(
            steps, sleep_hours, water_ml, exercise_min, mood
        )
        return (
            "현재는 OPENAI_API_KEY가 없어 규칙 기반 추천을 사용하고 있어요.\n\n"
            f"**{mission_title}**\n\n{mission_text}"
        )

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        prompt = f"""
너는 건강 습관을 돕는 앱 'Life of Booster'의 코치다.
사용자의 기록을 바탕으로 부담 없는 생활 습관 미션 1~2개를 추천해라.
의학적 진단이나 치료 조언은 하지 말고, 과도한 운동이나 식단 제한을 권하지 마라.
한국어로 짧고 친절하게 답해라.

오늘 점수: {score}/100
걸음 수: {steps}
수면: {sleep_hours}시간
물: {water_ml}mL
운동: {exercise_min}분
기분: {mood}/5
"""
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            input=prompt,
        )
        return response.output_text
    except Exception as e:
        return (
            "AI 추천을 불러오지 못해 기본 추천을 표시합니다.\n\n"
            f"오류 유형: {type(e).__name__}\n\n"
            "API 키와 인터넷 연결을 확인해 주세요."
        )

# ---------- App ----------
init_db()

st.title("🚀 Life of Booster")
st.caption("개인 생활 데이터를 바탕으로 오늘의 작은 미션과 보상을 제공하는 습관 관리 MVP")

with st.sidebar:
    st.header("📌 메뉴")
    page = st.radio(
        "이동",
        ["오늘의 Booster", "기록 보기", "프로젝트 설명"]
    )
    st.divider()
    st.info(
        "이 앱은 건강 관리의 참고용 습관 기록 서비스입니다. "
        "의료 진단이나 치료를 대신하지 않습니다."
    )

if page == "오늘의 Booster":
    st.subheader("오늘의 생활 데이터")

    df = load_logs()
    today = date.today()
    existing = df[df["log_date"] == str(today)]

    if not existing.empty:
        row = existing.iloc[0]
        default_steps = int(row["steps"])
        default_sleep = float(row["sleep_hours"])
        default_water = int(row["water_ml"])
        default_exercise = int(row["exercise_min"])
        default_mood = int(row["mood"])
        default_note = str(row["note"] or "")
    else:
        default_steps = 3000
        default_sleep = 7.0
        default_water = 500
        default_exercise = 10
        default_mood = 3
        default_note = ""

    with st.form("daily_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            steps = st.number_input("🚶 걸음 수", 0, 50000, default_steps, step=500)
            sleep_hours = st.number_input("😴 수면 시간", 0.0, 24.0, default_sleep, step=0.5)
        with c2:
            water_ml = st.number_input("💧 물 섭취량 (mL)", 0, 10000, default_water, step=100)
            exercise_min = st.number_input("🏃 활동 시간 (분)", 0, 600, default_exercise, step=5)
        with c3:
            mood = st.slider("🙂 오늘 기분", 1, 5, default_mood)
            note = st.text_area("📝 오늘 한 줄 기록", value=default_note)

        submitted = st.form_submit_button("오늘 기록 저장", type="primary")

    if submitted:
        save_log(today, steps, sleep_hours, water_ml, exercise_min, mood, note)
        st.success("오늘의 기록을 저장했습니다!")
        st.rerun()

    score = calculate_score(steps, sleep_hours, water_ml, exercise_min, mood)
    points = calculate_points(score)
    mission_title, mission_text = get_mission(
        steps, sleep_hours, water_ml, exercise_min, mood
    )

    st.divider()
    st.subheader("📊 오늘의 Booster Score")

    m1, m2, m3 = st.columns(3)
    m1.metric("생활 점수", f"{score}/100")
    m2.metric("예상 획득 포인트", f"+{points} P")
    m3.metric("연속 기록", f"{calculate_streak(df)}일")

    st.progress(score / 100)

    st.subheader("🎯 오늘의 맞춤 미션")
    st.info(f"**{mission_title}**\n\n{mission_text}")

    if st.button("🤖 AI로 추천받기"):
        with st.spinner("AI가 오늘의 데이터를 분석하고 있어요..."):
            result = ai_recommendation(
                score, steps, sleep_hours, water_ml, exercise_min, mood
            )
        st.markdown("### AI Booster")
        st.write(result)

    if score >= 80:
        st.success("🏆 훌륭해요! 오늘의 생활 습관을 잘 관리하고 있어요.")
    elif score >= 60:
        st.warning("🔥 좋아요! 작은 미션 하나만 더 실천해 봐요.")
    else:
        st.info("🌱 완벽할 필요 없어요. 오늘은 작은 행동 하나부터 시작해 봐요.")

elif page == "기록 보기":
    st.subheader("📅 생활 기록")

    df = load_logs()
    if df.empty:
        st.info("아직 기록이 없습니다. '오늘의 Booster'에서 기록을 추가해 주세요.")
    else:
        chart_df = df.copy()
        chart_df["log_date"] = pd.to_datetime(chart_df["log_date"])
        chart_df["score"] = chart_df.apply(
            lambda r: calculate_score(
                r["steps"], r["sleep_hours"], r["water_ml"],
                r["exercise_min"], r["mood"]
            ), axis=1
        )
        chart_df = chart_df.sort_values("log_date")

        st.line_chart(chart_df.set_index("log_date")[["score"]])

        st.subheader("최근 기록")
        st.dataframe(
            chart_df.sort_values("log_date", ascending=False),
            use_container_width=True,
            hide_index=True,
        )

        csv = chart_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ CSV로 내보내기",
            csv,
            "life_of_booster_history.csv",
            "text/csv",
        )

elif page == "프로젝트 설명":
    st.subheader("📖 Life of Booster MVP")

    st.markdown("""
### 프로젝트 목표
개인화된 생활 데이터를 바탕으로 사용자가 실천할 수 있는 작은 활동을 추천하고,
기록과 포인트를 통해 지속적인 동기를 제공하는 서비스입니다.

### 현재 구현된 기능
- 생활 데이터 입력: 걸음 수 / 수면 / 물 / 활동 / 기분
- 0~100 생활 점수 계산
- 개인 맞춤형 오늘의 미션
- 포인트 계산
- 연속 기록(Streak)
- SQLite 데이터 저장
- 기록 그래프
- CSV 다운로드
- OpenAI API를 연결할 경우 AI 추천 기능 사용
- API 키가 없어도 규칙 기반 추천으로 앱 실행 가능

### 다음 개발 단계
1. 로그인 및 사용자별 데이터 분리
2. 실제 스마트폰 건강 데이터 연동
3. 미니게임/퀘스트 시스템
4. 포인트 상점과 배지
5. 주간 리포트
6. AI 기반 개인화 추천 고도화
""")
