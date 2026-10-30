# tests/test_auth.py
# 회원가입·로그인·로그아웃과 사용자별 데이터 격리를 검사한다.
import pytest

import database
from conftest import signup

TRANSACTION = {
    "amount": 12000,
    "store": "스타벅스",
    "category": "cafe",
    "date": "2026-07-14",
    "time": "14:32",
    "card": "신한카드",
}


def login(test_client, username="tester", password="password123"):
    return test_client.post("/api/auth/login", json={"username": username, "password": password})


# ── 회원가입 ─────────────────────────────────────────
def test_signup_logs_in_and_returns_profile(anon_client):
    res = signup(anon_client, age_group="30대초반", income_group="high")

    assert res.status_code == 200
    assert res.get_json()["data"] == {
        "username": "tester", "age_group": "30대초반", "income_group": "high",
    }
    assert anon_client.get("/api/auth/me").status_code == 200


def test_signup_duplicate_username_is_409(anon_client, make_client):
    signup(anon_client)

    res = signup(make_client(), username="tester")
    assert res.status_code == 409
    assert res.get_json()["error"] == "이미 사용 중인 아이디예요"


@pytest.mark.parametrize("overrides", [
    {"username": "ab"},                 # 너무 짧음
    {"username": "a" * 21},             # 너무 김
    {"username": "Hello"},              # 대문자
    {"username": "한글아이디"},
    {"username": "has space"},
    {"password": "short"},
    {"password": 12345678},
    {"age_group": "100대"},
    {"income_group": "rich"},
])
def test_signup_validation_is_400(anon_client, overrides):
    res = signup(anon_client, **overrides)

    assert res.status_code == 400
    assert res.get_json()["success"] is False
    assert anon_client.get("/api/auth/me").status_code == 401


def test_password_is_hashed_and_never_returned(anon_client, fresh_db):  # pylint: disable=unused-argument
    body = signup(anon_client).get_data(as_text=True)
    assert "password" not in body

    stored = database.get_user_with_password("tester")
    assert stored["password_hash"] != "password123"
    assert "password" not in anon_client.get("/api/auth/me").get_data(as_text=True)


# ── 로그인 · 로그아웃 ────────────────────────────────
def test_login_and_logout(anon_client, make_client):
    signup(make_client())

    assert login(anon_client).status_code == 200
    assert anon_client.get("/api/auth/me").get_json()["data"]["username"] == "tester"

    assert anon_client.post("/api/auth/logout").status_code == 200
    assert anon_client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("username, password", [
    ("tester", "wrongpassword"),
    ("nobody", "password123"),
])
def test_login_failure_has_same_message(anon_client, make_client, username, password):
    signup(make_client())

    res = login(anon_client, username, password)
    assert res.status_code == 401
    # 아이디가 없는 경우와 비밀번호가 틀린 경우를 구분하지 않는다
    assert res.get_json()["error"] == "아이디 또는 비밀번호가 맞지 않아요"


def test_login_ignores_username_case(anon_client, make_client):
    # 가입은 소문자만 받지만, 휴대폰 자동 대문자로 'Tester'라고 쳐도 로그인되게 한다
    signup(make_client())
    assert login(anon_client, "Tester").status_code == 200


def test_login_missing_fields_is_400(anon_client):
    assert anon_client.post("/api/auth/login", json={"username": "tester"}).status_code == 400


# ── 보호된 경로 ──────────────────────────────────────
@pytest.mark.parametrize("method, path", [
    ("get", "/api/auth/me"),
    ("get", "/api/transactions"),
    ("post", "/api/transactions"),
    ("delete", "/api/transactions/1"),
    ("get", "/api/stats"),
    ("get", "/api/analysis"),
    ("post", "/api/parse"),
])
def test_protected_routes_require_login(anon_client, gemini_calls, method, path):
    res = getattr(anon_client, method)(path, json={})

    assert res.status_code == 401
    assert res.get_json() == {"success": False, "error": "로그인이 필요해요"}
    assert not gemini_calls.prompts


# ── 사용자 간 격리 ───────────────────────────────────
def test_users_cannot_see_or_delete_each_others_transactions(make_client):
    alice, bob = make_client(), make_client()
    signup(alice, username="alice")
    signup(bob, username="bob")

    tid = alice.post("/api/transactions", json=TRANSACTION).get_json()["data"]["id"]

    assert bob.get("/api/transactions").get_json()["total"] == 0
    assert bob.get("/api/stats?month=2026-07").get_json()["data"]["total_amount"] == 0
    assert bob.delete(f"/api/transactions/{tid}").status_code == 404

    # bob이 지우려 했어도 alice의 거래는 그대로다
    assert alice.get("/api/transactions").get_json()["total"] == 1
    assert alice.get("/api/stats?month=2026-07").get_json()["data"]["total_amount"] == 12000


def test_first_user_adopts_orphan_transactions(make_client, fresh_db):  # pylint: disable=unused-argument
    # 로그인 도입 전에 저장된 거래 (user_id 없음)
    conn = database.get_connection()
    conn.execute(
        "INSERT INTO transactions (amount, store, category, date, time) "
        "VALUES (5000, '예전 거래', 'food', '2026-07-01', '12:00')"
    )
    conn.commit()
    conn.close()

    first, second = make_client(), make_client()
    signup(first, username="first")
    signup(second, username="second")

    assert first.get("/api/transactions").get_json()["total"] == 1
    assert second.get("/api/transactions").get_json()["total"] == 0


def test_migration_adds_user_id_to_old_database(tmp_path, monkeypatch):
    # 로그인 도입 전 스키마의 DB를 그대로 가져와서 서버를 띄운 상황
    db_path = str(tmp_path / "old.db")
    monkeypatch.setattr(database, "DB_PATH", db_path)
    conn = database.get_connection()
    conn.executescript("""
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, amount INTEGER NOT NULL, store TEXT NOT NULL,
            category TEXT NOT NULL, date TEXT NOT NULL, time TEXT NOT NULL, card TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        INSERT INTO transactions (amount, store, category, date, time) VALUES (5000, 'x', 'food', '2026-07-01', '12:00');
    """)
    conn.close()

    database.init_db()

    conn = database.get_connection()
    row = conn.execute("SELECT amount, user_id FROM transactions").fetchone()
    conn.close()
    assert row["amount"] == 5000      # 기존 거래는 지워지지 않는다
    assert row["user_id"] is None     # 첫 가입자가 넘겨받을 때까지 주인 없음


def test_analysis_defaults_to_profile_group(anon_client, gemini_calls):  # pylint: disable=unused-argument
    signup(anon_client, age_group="40대", income_group="high")

    data = anon_client.get("/api/analysis?month=2026-07").get_json()["data"]
    assert data["peer_group"] == "40대 / high"

    # 드롭다운으로 다른 그룹을 고르면 그 그룹과 비교한다
    data = anon_client.get(
        "/api/analysis?month=2026-07&age_group=10대&income_group=low"
    ).get_json()["data"]
    assert data["peer_group"] == "10대 / low"


def test_session_for_deleted_user_is_rejected(client, fresh_db):  # pylint: disable=unused-argument
    # DB를 초기화했는데 브라우저에 예전 쿠키가 남아 있는 상황
    conn = database.get_connection()
    conn.execute("DELETE FROM users")
    conn.commit()
    conn.close()

    assert client.get("/api/transactions").status_code == 401
