import sqlite3
from datetime import date, timedelta

import pandas as pd
import streamlit as st


# ============================================================
# Life of Booster
# STEP 1 + STEP 2 + STEP 3
# ============================================================

st.set_page_config(
    page_title="Life of Booster",
    page_icon="🚀",
    layout="wide"
)


# ============================================================
# DATABASE
# ============================================================

DB_PATH = "life_of_booster.db"


def get_connection():
    return sqlite3.connect(
        DB_PATH,
        check_same_thread=False
    )


def initialize_database():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_progress (
            id INTEGER PRIMARY KEY,
            total_xp INTEGER DEFAULT 0,
            total_points INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO user_progress
        (id, total_xp, total_points)
        VALUES (1, 0, 0)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mission_completion (
            mission_date TEXT PRIMARY KEY,
            mission_title TEXT NOT NULL,
            xp_earned INTEGER NOT NULL,
            points_earned INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS badges (
            badge_id TEXT PRIMARY KEY,
            badge_name TEXT NOT NULL,
            badge_description TEXT NOT NULL,
            earned_date TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


initialize_database()


# ============================================================
# STYLE
# ============================================================

st.markdown("""
<style>

.main-title {
    font-size: 42px;
    font-weight: 800;
}

.small-text {
    color: #777777;
}

div[data-testid="stMetric"] {
    background-color: white;
    border: 1px solid #eeeeee;
    padding: 15px;
    border-radius: 15px;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# DAILY LOG
# ============================================================

def save_daily_log(
    log_date,
    steps,
    sleep_hours,
    water_ml,
    exercise_min,
    mood,
    note
):

    conn = get_connection()

    conn.execute("""
        INSERT INTO daily_log
        (
            log_date,
            steps,
            sleep_hours,
            water_ml,
            exercise_min,
            mood,
            note
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(log_date)
        DO UPDATE SET
            steps = excluded.steps,
            sleep_hours = excluded.sleep_hours,
            water_ml = excluded.water_ml,
            exercise_min = excluded.exercise_min,
            mood = excluded.mood,
            note = excluded.note
    """, (
        str(log_date),
        steps,
        sleep_hours,
        water_ml,
        exercise_min,
        mood,
        note
    ))

    conn.commit()
    conn.close()


def get_today_log():

    conn = get_connection()

    row = conn.execute("""
        SELECT
            steps,
            sleep_hours,
            water_ml,
            exercise_min,
            mood,
            note
        FROM daily_log
        WHERE log_date = ?
    """, (
        str(date.today()),
    )).fetchone()

    conn.close()

    return row


def get_all_logs():

    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT *
        FROM daily_log
        ORDER BY log_date DESC
    """, conn)

    conn.close()

    return df


# ============================================================
# SCORE
# ============================================================

def clamp(value):

    return max(
        0,
        min(100, value)
    )


def calculate_score(
    steps,
    sleep_hours,
    water_ml,
    exercise_min,
    mood
):

    steps_score = clamp(
        steps / 8000 * 100
    )

    sleep_score = clamp(
        100 - abs(sleep_hours - 8) * 25
    )

    water_score = clamp(
        water_ml / 1500 * 100
    )

    exercise_score = clamp(
        exercise_min / 30 * 100
    )

    mood_score = clamp(
        mood / 5 * 100
    )

    score = (
        steps_score * 0.25
        + sleep_score * 0.20
        + water_score * 0.15
        + exercise_score * 0.25
        + mood_score * 0.15
    )

    return round(score, 1)


# ============================================================
# XP / POINTS
# ============================================================

def get_progress():

    conn = get_connection()

    row = conn.execute("""
        SELECT total_xp, total_points
        FROM user_progress
        WHERE id = 1
    """).fetchone()

    conn.close()

    return row[0], row[1]


def add_rewards(xp, points):

    conn = get_connection()

    conn.execute("""
        UPDATE user_progress
        SET
            total_xp = total_xp + ?,
            total_points = total_points + ?
        WHERE id = 1
    """, (
        xp,
        points
    ))

    conn.commit()
    conn.close()


# ============================================================
# LEVEL
# ============================================================

def get_level(xp):

    if xp < 100:
        return 1, "🌱 새싹", 100

    if xp < 250:
        return 2, "🌿 성장 중", 250

    if xp < 500:
        return 3, "🌳 습관 형성", 500

    if xp < 1000:
        return 4, "🚀 Booster", 1000

    return 5, "🏆 Life Master", 1000


# ============================================================
# MISSION
# ============================================================

def get_today_mission(
    steps,
    sleep_hours,
    water_ml,
    exercise_min,
    mood
):

    if steps < 8000:

        return (
            "🚶 10분 걷기",
            "가볍게 10분 정도 걸어보세요.",
            50,
            100
        )

    if water_ml < 1500:

        return (
            "💧 물 마시기",
            "물 한 잔을 더 마셔보세요.",
            30,
            70
        )

    if sleep_hours < 7.5:

        return (
            "😴 수면 준비",
            "오늘은 조금 일찍 휴식을 준비해보세요.",
            20,
            50
        )

    if exercise_min < 30:

        return (
            "🏃 10분 움직이기",
            "가볍게 몸을 움직여보세요.",
            50,
            100
        )

    if mood <= 2:

        return (
            "🙂 기분 전환",
            "좋아하는 활동으로 기분을 전환해보세요.",
            30,
            70
        )

    return (
        "🎉 오늘의 목표 달성!",
        "오늘 생활 습관 목표를 잘 달성했어요.",
        20,
        50
    )


def mission_completed_today():

    conn = get_connection()

    row = conn.execute("""
        SELECT mission_date
        FROM mission_completion
        WHERE mission_date = ?
    """, (
        str(date.today()),
    )).fetchone()

    conn.close()

    return row is not None


def complete_mission(
    title,
    xp,
    points
):

    conn = get_connection()

    conn.execute("""
        INSERT INTO mission_completion
        (
            mission_date,
            mission_title,
            xp_earned,
            points_earned
        )
        VALUES (?, ?, ?, ?)
    """, (
        str(date.today()),
        title,
        xp,
        points
    ))

    conn.commit()
    conn.close()


# ============================================================
# BADGES
# ============================================================

def update_badges():

    xp, points = get_progress()

    conn = get_connection()

    mission_count = conn.execute("""
        SELECT COUNT(*)
        FROM mission_completion
    """).fetchone()[0]

    log_count = conn.execute("""
        SELECT COUNT(*)
        FROM daily_log
    """).fetchone()[0]

    badges = []

    if log_count >= 1:

        badges.append((
            "first_log",
            "🌱 첫 기록",
            "첫 번째 생활 기록을 남겼어요."
        ))

    if mission_count >= 1:

        badges.append((
            "first_mission",
            "🎯 첫 미션",
            "첫 번째 미션을 완료했어요."
        ))

    if mission_count >= 7:

        badges.append((
            "mission_7",
            "🔥 미션 7회",
            "미션을 7번 완료했어요."
        ))

    if xp >= 500:

        badges.append((
            "xp_500",
            "⭐ XP 500",
            "XP 500을 달성했어요."
        ))

    if xp >= 1000:

        badges.append((
            "xp_1000",
            "🏆 XP 1000",
            "XP 1000을 달성했어요."
        ))

    for badge in badges:

        conn.execute("""
            INSERT OR IGNORE INTO badges
            (
                badge_id,
                badge_name,
                badge_description,
                earned_date
            )
            VALUES (?, ?, ?, ?)
        """, (
            badge[0],
            badge[1],
            badge[2],
            str(date.today())
        ))

    conn.commit()
    conn.close()


def get_badges():

    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT *
        FROM badges
        ORDER BY earned_date DESC
    """, conn)

    conn.close()

    return df


# ============================================================
# STREAK
# ============================================================

def get_streak():

    df = get_all_logs()

    if df.empty:
        return 0

    dates = set(
        pd.to_datetime(
            df["log_date"]
        ).dt.date
    )

    current = date.today()

    streak = 0

    while current in dates:

        streak += 1

        current -= timedelta(days=1)

    return streak


# ============================================================
# WEEKLY REPORT
# ============================================================

def get_week_data():

    df = get_all_logs()

    if df.empty:
        return df

    df["log_date"] = pd.to_datetime(
        df["log_date"]
    )

    today = pd.Timestamp.today().normalize()

    monday = today - pd.Timedelta(
        days=today.weekday()
    )

    sunday = monday + pd.Timedelta(
        days=6
    )

    week = df[
        (df["log_date"] >= monday)
        &
        (df["log_date"] <= sunday)
    ].copy()

    if week.empty:
        return week

    week["score"] = week.apply(
        lambda row:
        calculate_score(
            row["steps"],
            row["sleep_hours"],
            row["water_ml"],
            row["exercise_min"],
            row["mood"]
        ),
        axis=1
    )

    return week.sort_values(
        "log_date"
    )


def get_best_habit(week):

    if week.empty:
        return "기록 시작"

    habits = {
        "🏃 활동량": week["exercise_min"].mean(),
        "🚶 걸음 수": week["steps"].mean(),
        "💧 물 섭취": week["water_ml"].mean(),
        "😴 수면": week["sleep_hours"].mean(),
        "🙂 기분": week["mood"].mean()
    }

    return max(
        habits,
        key=habits.get
    )


def get_recommendation(week):

    if week.empty:

        return "먼저 오늘의 생활 기록을 남겨보세요."

    avg_steps = week["steps"].mean()
    avg_water = week["water_ml"].mean()
    avg_sleep = week["sleep_hours"].mean()
    avg_exercise = week["exercise_min"].mean()

    if avg_steps < 5000:

        return "🚶 다음 주에는 하루에 조금 더 걸어보는 것을 추천해요."

    if avg_water < 1000:

        return "💧 물 섭취 기록을 조금 더 꾸준히 유지해보세요."

    if avg_sleep < 6.5:

        return "😴 수면 시간을 조금 더 확보하는 것을 추천해요."

    if avg_exercise < 20:

        return "🏃 하루에 짧게라도 몸을 움직이는 습관을 만들어보세요."

    return "🔥 지금처럼 좋은 생활 습관과 기록을 꾸준히 유지해보세요!"


# ============================================================
# SIDEBAR
# ============================================================

xp, points = get_progress()

level, level_name, next_xp = get_level(xp)

st.sidebar.title("🚀 Life of Booster")

st.sidebar.write(
    f"### {level_name}"
)

st.sidebar.write(
    f"**Lv.{level}**"
)

st.sidebar.metric(
    "⭐ XP",
    xp
)

st.sidebar.metric(
    "💰 Points",
    points
)

st.sidebar.divider()

page = st.sidebar.radio(
    "메뉴",
    [
        "🏠 오늘의 Booster",
        "📊 주간 리포트",
        "🏆 배지 & 레벨",
        "📋 전체 기록"
    ]
)

st.sidebar.divider()

st.sidebar.metric(
    "🔥 연속 기록",
    f"{get_streak()}일"
)


# ============================================================
# PAGE 1
# TODAY
# ============================================================

if page == "🏠 오늘의 Booster":

    st.markdown(
        "# 🚀 Life of Booster"
    )

    st.caption(
        "오늘의 생활 습관을 기록하고 Booster를 받아보세요."
    )

    st.info(
        "🌱 완벽할 필요는 없어요. "
        "작은 습관을 하나씩 기록해보세요."
    )

    today_log = get_today_log()

    if today_log:

        default_steps = today_log[0]
        default_sleep = today_log[1]
        default_water = today_log[2]
        default_exercise = today_log[3]
        default_mood = today_log[4]
        default_note = today_log[5] or ""

    else:

        default_steps = 3000
        default_sleep = 7.0
        default_water = 500
        default_exercise = 10
        default_mood = 3
        default_note = ""

    st.subheader("📝 오늘의 생활 기록")

    with st.form("daily_form"):

        col1, col2 = st.columns(2)

        with col1:

            steps = st.number_input(
                "🚶 걸음 수",
                min_value=0,
                max_value=50000,
                value=int(default_steps),
                step=500
            )

            sleep_hours = st.number_input(
                "😴 수면 시간",
                min_value=0.0,
                max_value=24.0,
                value=float(default_sleep),
                step=0.5
            )

            water_ml = st.number_input(
                "💧 물 섭취량 (mL)",
                min_value=0,
                max_value=10000,
                value=int(default_water),
                step=100
            )

        with col2:

            exercise_min = st.number_input(
                "🏃 운동 / 활동 시간 (분)",
                min_value=0,
                max_value=600,
                value=int(default_exercise),
                step=5
            )

            mood = st.slider(
                "🙂 오늘의 기분",
                min_value=1,
                max_value=5,
                value=int(default_mood)
            )

            note = st.text_area(
                "📝 오늘의 메모",
                value=default_note
            )

        submitted = st.form_submit_button(
            "💾 오늘 기록 저장",
            use_container_width=True
        )

    if submitted:

        save_daily_log(
            date.today(),
            steps,
            sleep_hours,
            water_ml,
            exercise_min,
            mood,
            note
        )

        update_badges()

        st.success(
            "✅ 오늘의 기록이 저장되었습니다!"
        )

        st.rerun()

    # SCORE

    score = calculate_score(
        steps,
        sleep_hours,
        water_ml,
        exercise_min,
        mood
    )

    xp, points = get_progress()

    level, level_name, next_xp = get_level(xp)

    st.subheader("📊 오늘의 Booster")

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "⭐ 생활 점수",
            f"{score}"
        )

    with col2:

        st.metric(
            "✨ XP",
            f"{xp}"
        )

    with col3:

        st.metric(
            "🏆 레벨",
            f"Lv.{level}"
        )

    with col4:

        st.metric(
            "💰 포인트",
            f"{points}"
        )

    st.progress(
        min(
            xp / next_xp,
            1.0
        )
    )

    st.caption(
        f"{level_name} · 다음 레벨까지 "
        f"{max(next_xp - xp, 0)} XP"
    )

    # MISSION

    st.subheader("🎯 오늘의 미션")

    (
        mission_title,
        mission_text,
        mission_xp,
        mission_points
    ) = get_today_mission(
        steps,
        sleep_hours,
        water_ml,
        exercise_min,
        mood
    )

    st.info(
        f"""
        ### {mission_title}

        {mission_text}

        **+{mission_xp} XP**
        ·
        **+{mission_points} Points**
        """
    )

    if mission_completed_today():

        st.success(
            "🎉 오늘의 미션을 이미 완료했어요!"
        )

    else:

        if st.button(
            "🎯 미션 완료하기",
            use_container_width=True
        ):

            complete_mission(
                mission_title,
                mission_xp,
                mission_points
            )

            add_rewards(
                mission_xp,
                mission_points
            )

            update_badges()

            st.success(
                f"🎉 미션 완료! "
                f"+{mission_xp} XP / "
                f"+{mission_points} Points"
            )

            st.rerun()


# ============================================================
# PAGE 2
# WEEKLY REPORT
# ============================================================

elif page == "📊 주간 리포트":

    st.title("📊 주간 리포트")

    st.caption(
        "이번 주 생활 습관을 한눈에 확인해보세요."
    )

    week = get_week_data()

    if week.empty:

        st.warning(
            "이번 주 기록이 아직 없습니다."
        )

        st.info(
            "🏠 오늘의 Booster에서 생활 기록을 추가해보세요."
        )

    else:

        average_score = round(
            week["score"].mean(),
            1
        )

        st.subheader(
            "🌟 이번 주 생활 점수"
        )

        st.metric(
            "평균 점수",
            f"{average_score} / 100"
        )

        st.progress(
            average_score / 100
        )

        if average_score >= 85:

            st.success(
                "🏆 정말 좋은 한 주였어요!"
            )

        elif average_score >= 70:

            st.success(
                "🔥 좋은 흐름이에요! 계속 유지해보세요."
            )

        elif average_score >= 50:

            st.info(
                "🌱 잘하고 있어요. 작은 습관부터 꾸준히!"
            )

        else:

            st.info(
                "💪 기록을 시작한 것 자체가 좋은 시작이에요."
            )

        st.subheader("📌 이번 주 평균")

        col1, col2, col3, col4 = st.columns(4)

        with col1:

            st.metric(
                "🚶 평균 걸음",
                f"{round(week['steps'].mean()):,}"
            )

        with col2:

            st.metric(
                "💧 평균 물",
                f"{round(week['water_ml'].mean()):,} mL"
            )

        with col3:

            st.metric(
                "😴 평균 수면",
                f"{week['sleep_hours'].mean():.1f} h"
            )

        with col4:

            st.metric(
                "🏃 평균 활동",
                f"{round(week['exercise_min'].mean())} 분"
            )

        st.subheader("📈 일별 생활 점수")

        chart_df = week[
            ["log_date", "score"]
        ].copy()

        chart_df = chart_df.set_index(
            "log_date"
        )

        st.line_chart(
            chart_df,
            use_container_width=True
        )

        st.subheader("📅 이번 주 기록")

        for _, row in week.iterrows():

            weekday = row["log_date"].strftime(
                "%A"
            )

            weekday_korean = {
                "Monday": "월",
                "Tuesday": "화",
                "Wednesday": "수",
                "Thursday": "목",
                "Friday": "금",
                "Saturday": "토",
                "Sunday": "일"
            }.get(
                weekday,
                weekday
            )

            score_value = int(
                row["score"]
            )

            st.write(
                f"**{weekday_korean}** "
                f"— "
                f"**{score_value}점**"
            )

            st.progress(
                score_value / 100
            )

        st.subheader("🌟 이번 주 가장 좋아진 습관")

        best_habit = get_best_habit(
            week
        )

        st.success(
            f"이번 주에는 **{best_habit}**이 "
            f"가장 돋보였어요!"
        )

        st.subheader("🎯 다음 주 추천")

        recommendation = get_recommendation(
            week
        )

        st.info(
            recommendation
        )

        st.subheader("📝 WEEKLY SUMMARY")

        st.write(
            f"""
            이번 주에는 **{len(week)}일** 동안 기록했어요.

            평균 생활 점수는 **{average_score}점**입니다.

            가장 돋보였던 습관은
            **{best_habit}**입니다.

            다음 주에도 완벽하게 하려고 하기보다
            작은 행동을 꾸준히 이어가 보세요. 🌱
            """
        )

        with st.expander(
            "📋 이번 주 상세 기록 보기"
        ):

            detail = week.copy()

            detail["log_date"] = (
                detail["log_date"]
                .dt.strftime("%Y-%m-%d")
            )

            detail = detail[
                [
                    "log_date",
                    "score",
                    "steps",
                    "sleep_hours",
                    "water_ml",
                    "exercise_min",
                    "mood",
                    "note"
                ]
            ]

            detail.columns = [
                "날짜",
                "생활 점수",
                "걸음 수",
                "수면 시간",
                "물(mL)",
                "활동(분)",
                "기분",
                "메모"
            ]

            st.dataframe(
                detail,
                use_container_width=True,
                hide_index=True
            )


# ============================================================
# PAGE 3
# BADGES
# ============================================================

elif page == "🏆 배지 & 레벨":

    st.title("🏆 배지 & 레벨")

    update_badges()

    xp, points = get_progress()

    level, level_name, next_xp = get_level(
        xp
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "🏆 현재 레벨",
            f"Lv.{level}"
        )

    with col2:

        st.metric(
            "✨ XP",
            xp
        )

    with col3:

        st.metric(
            "💰 포인트",
            points
        )

    st.subheader(
        level_name
    )

    if level < 5:

        st.progress(
            min(
                xp / next_xp,
                1.0
            )
        )

        st.caption(
            f"다음 레벨까지 "
            f"{next_xp - xp} XP"
        )

    else:

        st.success(
            "🏆 최고 레벨에 도달했어요!"
        )

    st.subheader(
        "🎖️ 획득한 배지"
    )

    badges = get_badges()

    if badges.empty:

        st.info(
            "아직 획득한 배지가 없습니다."
        )

    else:

        for _, badge in badges.iterrows():

            st.success(
                f"""
                ### {badge["badge_name"]}

                {badge["badge_description"]}

                획득일: {badge["earned_date"]}
                """
            )


# ============================================================
# PAGE 4
# ALL RECORDS
# ============================================================

elif page == "📋 전체 기록":

    st.title("📋 전체 기록")

    st.caption(
        "지금까지 기록한 생활 데이터를 확인하세요."
    )

    df = get_all_logs()

    if df.empty:

        st.info(
            "아직 생활 기록이 없습니다."
        )

    else:

        df["log_date"] = pd.to_datetime(
            df["log_date"]
        )

        df["score"] = df.apply(
            lambda row:
            calculate_score(
                row["steps"],
                row["sleep_hours"],
                row["water_ml"],
                row["exercise_min"],
                row["mood"]
            ),
            axis=1
        )

        st.subheader(
            "📈 생활 점수 변화"
        )

        chart_df = df[
            ["log_date", "score"]
        ].sort_values(
            "log_date"
        )

        chart_df = chart_df.set_index(
            "log_date"
        )

        st.line_chart(
            chart_df,
            use_container_width=True
        )

        st.subheader(
            "📊 전체 기록"
        )

        display_df = df.copy()

        display_df["log_date"] = (
            display_df["log_date"]
            .dt.strftime("%Y-%m-%d")
        )

        display_df = display_df[
            [
                "log_date",
                "score",
                "steps",
                "sleep_hours",
                "water_ml",
                "exercise_min",
                "mood",
                "note"
            ]
        ]

        display_df.columns = [
            "날짜",
            "생활 점수",
            "걸음 수",
            "수면 시간",
            "물(mL)",
            "활동(분)",
            "기분",
            "메모"
        ]

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )

        csv = display_df.to_csv(
            index=False
        ).encode(
            "utf-8-sig"
        )

        st.download_button(
            "📥 CSV 다운로드",
            csv,
            "life_of_booster_records.csv",
            "text/csv",
            use_container_width=True
        )