# database.py
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "database.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Migration ────────────────────────────────────────────────────────────────

def _table_exists(conn, table_name):
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def _column_exists(conn, table_name, column_name):
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cursor.fetchall())


def _migrate_peer_averages(conn):
    """
    구 스키마: (category TEXT PK, avg_amount INTEGER)
    신 스키마: (id, age_group, income_group, category, avg_amount)

    구 데이터는 age_group/income_group 없이 단일 그룹이라 그대로 옮길 수 없음.
    → 테이블 DROP 후 재생성. 마이그레이션 후 seed.py 재실행 필요.
    """
    if not _table_exists(conn, "peer_averages"):
        return  # 테이블 자체가 없으면 패스

    if not _column_exists(conn, "peer_averages", "age_group"):
        print("[migration] peer_averages: 구 스키마 감지 → DROP 후 재생성")
        conn.execute("DROP TABLE peer_averages")
        conn.commit()
        print("[migration] 완료. seed.py를 다시 실행해서 데이터를 채워줘.")


def _migrate_transactions_user_id(conn):
    """
    로그인 도입 전 transactions에는 user_id가 없다.
    컬럼만 추가하고 기존 행은 NULL(주인 없음)로 둔다 → 첫 가입자가 create_user()에서 넘겨받는다.
    """
    if not _table_exists(conn, "transactions"):
        return

    if not _column_exists(conn, "transactions", "user_id"):
        print("[migration] transactions: user_id 컬럼 추가 (기존 거래는 첫 가입 계정에 넘어간다)")
        conn.execute("ALTER TABLE transactions ADD COLUMN user_id INTEGER REFERENCES users(id)")
        conn.commit()


# ─── Init ─────────────────────────────────────────────────────────────────────

def init_db():
    conn = get_connection()
    try:
        _migrate_peer_averages(conn)
        _migrate_transactions_user_id(conn)

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT    NOT NULL,
                age_group     TEXT    NOT NULL,
                income_group  TEXT    NOT NULL,
                created_at    TEXT    DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                amount     INTEGER NOT NULL,
                store      TEXT    NOT NULL,
                category   TEXT    NOT NULL,
                date       TEXT    NOT NULL,
                time       TEXT    NOT NULL,
                card       TEXT,
                created_at TEXT    DEFAULT (datetime('now', 'localtime')),
                user_id    INTEGER REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS peer_averages (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                age_group    TEXT    NOT NULL,
                income_group TEXT    NOT NULL,
                category     TEXT    NOT NULL,
                avg_amount   INTEGER NOT NULL,
                UNIQUE(age_group, income_group, category)
            );
        """)
        conn.commit()
    finally:
        conn.close()


# ─── Users ────────────────────────────────────────────────────────────────────
# password_hash는 이 모듈 밖(API 응답)으로 내보내지 않는다. 로그인 검증에만 쓴다.

USER_PUBLIC_COLUMNS = "id, username, age_group, income_group"


def create_user(username: str, password_hash: str, age_group: str, income_group: str) -> int:
    """
    사용자 1명 생성. 반환값: 새 user id
    이미 있는 아이디면 sqlite3.IntegrityError (UNIQUE, 대소문자 무시).
    첫 가입자라면 로그인 도입 전에 쌓인 주인 없는 거래를 같은 트랜잭션에서 넘겨받는다.
    """
    conn = get_connection()
    try:
        is_first_user = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0

        cursor = conn.execute(
            """
            INSERT INTO users (username, password_hash, age_group, income_group)
            VALUES (?, ?, ?, ?)
            """,
            (username, password_hash, age_group, income_group),
        )
        user_id = cursor.lastrowid

        if is_first_user:
            conn.execute("UPDATE transactions SET user_id = ? WHERE user_id IS NULL", (user_id,))

        conn.commit()
        return user_id
    finally:
        conn.close()


def get_user(user_id: int):
    """id로 사용자 조회 (password_hash 제외). 없으면 None"""
    conn = get_connection()
    try:
        row = conn.execute(
            f"SELECT {USER_PUBLIC_COLUMNS} FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_with_password(username: str):
    """로그인 검증용. password_hash까지 포함한다. 없으면 None"""
    conn = get_connection()
    try:
        row = conn.execute(
            f"SELECT {USER_PUBLIC_COLUMNS}, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ─── Transactions ─────────────────────────────────────────────────────────────
# 모든 함수가 user_id로 범위를 좁힌다. 빠뜨리면 다른 사람의 가계부가 섞여 보인다.

def insert_transaction(user_id: int, data: dict) -> int:
    """거래 내역 1건 삽입. 반환값: 새로 생성된 row id"""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO transactions (amount, store, category, date, time, card, user_id)
            VALUES (:amount, :store, :category, :date, :time, :card, :user_id)
            """,
            {**data, "user_id": user_id},
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def delete_transaction(user_id: int, transaction_id: int) -> bool:
    """
    거래 내역 1건 삭제. 반환값: 지운 행이 있으면 True
    다른 사람의 거래 id면 없는 id와 똑같이 False (남의 거래가 있는지조차 알려주지 않는다)
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM transactions WHERE id = ? AND user_id = ?",
            (transaction_id, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_transactions(user_id: int, month: str = None, category: str = None,
                     search: str = None) -> list:
    """
    로그인한 사용자의 거래 내역 조회.
    month:    'YYYY-MM' 형식으로 넘기면 해당 월 필터
    category: 7개 카테고리 key 중 하나로 넘기면 해당 카테고리만
    search:   상점명 부분 일치 검색
    """
    conditions = ["user_id = ?"]
    params = [user_id]

    if month:
        conditions.append("strftime('%Y-%m', date) = ?")
        params.append(month)
    if category:
        conditions.append("category = ?")
        params.append(category)
    if search:
        # LIKE 패턴도 파라미터로 바인딩한다 (문자열 포매팅 금지)
        conditions.append("store LIKE ?")
        params.append(f"%{search}%")

    where = f"WHERE {' AND '.join(conditions)}"

    conn = get_connection()
    try:
        cursor = conn.execute(
            f"""
            SELECT id, amount, store, category, date, time, card
            FROM transactions
            {where}
            ORDER BY date DESC, time DESC
            """,
            params,
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


# ─── Stats ────────────────────────────────────────────────────────────────────

CATEGORIES = ["food", "cafe", "transport", "shopping", "medical", "leisure", "etc"]


def get_stats(user_id: int, month: str) -> dict:
    """로그인한 사용자의 월별 통계: 총액 + 카테고리별 + 날짜별"""
    conn = get_connection()
    try:
        total = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE user_id = ? AND strftime('%Y-%m', date) = ?
            """,
            (user_id, month),
        ).fetchone()["total"]

        cat_rows = conn.execute(
            """
            SELECT category, COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE user_id = ? AND strftime('%Y-%m', date) = ?
            GROUP BY category
            """,
            (user_id, month),
        ).fetchall()

        by_category = {c: 0 for c in CATEGORIES}
        for row in cat_rows:
            if row["category"] in by_category:
                by_category[row["category"]] = row["total"]

        date_rows = conn.execute(
            """
            SELECT date, SUM(amount) AS amount
            FROM transactions
            WHERE user_id = ? AND strftime('%Y-%m', date) = ?
            GROUP BY date
            ORDER BY date
            """,
            (user_id, month),
        ).fetchall()

        return {
            "total_amount": total,
            "by_category": by_category,
            "by_date": [dict(row) for row in date_rows],
        }
    finally:
        conn.close()


# ─── Peer Averages ────────────────────────────────────────────────────────────

def count_peer_averages() -> int:
    """또래 비교 데이터 행 수. 서버 시작 시 자동 seed 여부를 판단하는 데 쓴다."""
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM peer_averages").fetchone()[0]
    finally:
        conn.close()


def get_peer_averages(age_group: str, income_group: str) -> dict:
    """
    특정 나이/소득 그룹의 카테고리별 평균 소비 반환.
    반환 형식: { "food": 95000, "cafe": 32000, ... }
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT category, avg_amount
            FROM peer_averages
            WHERE age_group = ? AND income_group = ?
            """,
            (age_group, income_group),
        ).fetchall()
        return {row["category"]: row["avg_amount"] for row in rows}
    finally:
        conn.close()
