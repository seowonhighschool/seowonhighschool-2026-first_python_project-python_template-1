# tests/conftest.py
import os
import tempfile

import pytest

# app.py는 import하는 순간 init_db()·seed()로 DB를 건드린다.
# 그 전에 DB_PATH를 임시 파일로 돌려놓아야 실제 database.db가 테스트 데이터로 오염되지 않는다.
# (load_dotenv는 이미 있는 환경변수를 덮어쓰지 않는다)
_IMPORT_DB = os.path.join(tempfile.mkdtemp(prefix="sms-budget-test-"), "import.db")
os.environ["DB_PATH"] = _IMPORT_DB

# pylint: disable=wrong-import-position
import app as app_module
import database
import gemini_parser
import seed


def signup(test_client, username="tester", **overrides):
    """회원가입(=로그인)한다. 가입하면 그 test_client의 쿠키에 세션이 남는다."""
    payload = {
        "username": username,
        "password": "password123",
        "age_group": "20대초반",
        "income_group": "mid-low",
        **overrides,
    }
    return test_client.post("/api/auth/signup", json=payload)


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """테스트마다 빈 DB(+또래 데이터 시드)를 새로 만들어 서로 영향을 주지 않게 한다."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DB_PATH", db_path)
    monkeypatch.setattr(seed, "DB_PATH", db_path)
    database.init_db()
    seed.seed()
    app_module.app.config["TESTING"] = True
    return db_path


@pytest.fixture
def anon_client(fresh_db):  # pylint: disable=unused-argument
    """로그인하지 않은 클라이언트"""
    with app_module.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def client(fresh_db):  # pylint: disable=unused-argument
    """가입·로그인까지 마친 클라이언트. 거래·통계 API 테스트는 대부분 이것을 쓴다."""
    with app_module.app.test_client() as test_client:
        assert signup(test_client).status_code == 200
        yield test_client


@pytest.fixture
def make_client(fresh_db):  # pylint: disable=unused-argument
    """같은 DB를 쓰는 별도 사용자 클라이언트를 만든다 (사용자 간 격리 테스트용). 쿠키는 클라이언트마다 따로다."""
    return app_module.app.test_client


@pytest.fixture
def gemini_calls(monkeypatch):
    """
    Gemini를 실제로 부르지 않게 막고, 들어온 프롬프트를 기록한다.
    응답은 테스트에서 gemini_calls.reply 에 넣는다 (기본값은 조언용 문장).
    """
    class FakeGemini:
        def __init__(self):
            self.prompts = []
            self.reply = "테스트 조언입니다."

        def __call__(self, prompt):
            self.prompts.append(prompt)
            return self.reply

    fake = FakeGemini()
    monkeypatch.setattr(gemini_parser, "generate_text", fake)
    return fake
