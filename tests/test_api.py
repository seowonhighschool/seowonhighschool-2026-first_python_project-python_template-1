# tests/test_api.py
# Flask 라우트를 실제 DB(임시 파일)와 함께 검사한다. Gemini는 conftest의 가짜로 대체한다.
import json

import pytest

import app as app_module

SAMPLE = {
    "amount": 12000,
    "store": "스타벅스",
    "category": "cafe",
    "date": "2026-07-14",
    "time": "14:32",
    "card": "신한카드",
}


def save(client, **overrides):
    return client.post("/api/transactions", json={**SAMPLE, **overrides})


# ── POST /api/transactions ───────────────────────────
def test_save_returns_id(client):
    res = save(client)

    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert isinstance(body["data"]["id"], int)


@pytest.mark.parametrize("field", ["amount", "store", "category", "date", "time"])
def test_save_missing_required_field_is_400(client, field):
    payload = {k: v for k, v in SAMPLE.items() if k != field}
    res = client.post("/api/transactions", json=payload)

    assert res.status_code == 400
    assert field in res.get_json()["error"]


def test_save_card_is_optional(client):
    payload = {k: v for k, v in SAMPLE.items() if k != "card"}
    assert client.post("/api/transactions", json=payload).status_code == 200


def test_save_normalizes_string_amount(client):
    # SQLite는 문자열도 INTEGER 컬럼에 넣어버린다. 정수로 바꿔 저장해야 통계 합계가 맞다.
    save(client, amount="12,000원")

    stats = client.get("/api/stats?month=2026-07").get_json()["data"]
    assert stats["total_amount"] == 12000


@pytest.mark.parametrize("amount", ["abc", 0, -500, "-500"])
def test_save_rejects_bad_amount(client, amount):
    assert save(client, amount=amount).status_code == 400


def test_save_rejects_unknown_category(client):
    assert save(client, category="travel").status_code == 400


def test_save_rejects_empty_body(client):
    res = client.post("/api/transactions", data="", content_type="application/json")
    assert res.status_code == 400
    assert res.get_json()["success"] is False


# ── DELETE /api/transactions/<id> ────────────────────
def test_delete_removes_transaction(client):
    tid = save(client).get_json()["data"]["id"]

    res = client.delete(f"/api/transactions/{tid}")
    assert res.status_code == 200
    assert res.get_json()["data"]["id"] == tid
    assert client.get("/api/transactions").get_json()["total"] == 0


def test_delete_unknown_id_is_404(client):
    res = client.delete("/api/transactions/99999")
    assert res.status_code == 404
    assert res.get_json()["error"] == "해당 거래를 찾을 수 없습니다"


def test_delete_non_numeric_id_is_json_404(client):
    res = client.delete("/api/transactions/abc")
    assert res.status_code == 404
    assert res.get_json()["error"] == "없는 API 경로입니다"


# ── GET /api/transactions ────────────────────────────
def test_list_filters_by_month_category_and_search(client):
    save(client)
    save(client, store="김밥천국", category="food", amount=8000)
    save(client, store="스타벅스 강남", date="2026-08-02")

    def total(query):
        return client.get(f"/api/transactions?{query}").get_json()["total"]

    assert total("") == 3
    assert total("month=2026-07") == 2
    assert total("month=2026-07&category=food") == 1
    assert total("search=스타벅스") == 2
    assert total("month=2026-08&search=스타벅스") == 1
    assert total("search=없는가게") == 0


def test_list_returns_api_schema_keys(client):
    save(client)
    row = client.get("/api/transactions").get_json()["data"][0]
    assert set(row) == {"id", "amount", "store", "category", "date", "time", "card"}


# ── GET /api/stats ───────────────────────────────────
def test_stats_always_has_seven_categories(client):
    res = client.get("/api/stats?month=2026-07").get_json()["data"]

    assert set(res["by_category"]) == {
        "food", "cafe", "transport", "shopping", "medical", "leisure", "etc",
    }
    assert res["total_amount"] == 0
    assert res["by_date"] == []


def test_stats_sums_by_category_and_date(client):
    save(client)
    save(client, amount=3000)
    save(client, store="김밥천국", category="food", amount=8000, date="2026-07-15")

    data = client.get("/api/stats?month=2026-07").get_json()["data"]
    assert data["total_amount"] == 23000
    assert data["by_category"]["cafe"] == 15000
    assert data["by_category"]["food"] == 8000
    assert data["by_date"] == [
        {"date": "2026-07-14", "amount": 15000},
        {"date": "2026-07-15", "amount": 8000},
    ]


# ── POST /api/parse ──────────────────────────────────
def test_parse_returns_preview_without_saving(client, gemini_calls):
    gemini_calls.reply = json.dumps({**SAMPLE, "amount": "12,000"}, ensure_ascii=False)

    res = client.post("/api/parse", json={"sms": "[신한카드] 승인 12,000원 스타벅스 07/14 14:32"})

    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["amount"] == 12000
    assert "id" not in data
    # 미리보기 전용: 저장은 POST /api/transactions에서만 한다
    assert client.get("/api/transactions").get_json()["total"] == 0


@pytest.mark.parametrize("payload", [{}, {"sms": ""}, {"sms": "   "}, {"sms": 123}])
def test_parse_rejects_missing_sms(client, gemini_calls, payload):
    assert client.post("/api/parse", json=payload).status_code == 400
    assert not gemini_calls.prompts


def test_parse_rejects_too_long_sms_before_gemini(client, gemini_calls):
    sms = "가" * (app_module.MAX_SMS_LENGTH + 1)

    res = client.post("/api/parse", json={"sms": sms})

    assert res.status_code == 400
    assert not gemini_calls.prompts


# ── GET /api/analysis ────────────────────────────────
def test_analysis_skips_gemini_when_no_spending(client, gemini_calls):
    res = client.get("/api/analysis?month=2026-07&age_group=20대초반&income_group=mid-low")

    data = res.get_json()["data"]
    assert data["user_total"] == 0
    assert data["has_peer_data"] is True
    assert not gemini_calls.prompts


def test_analysis_compares_with_peer_group(client, gemini_calls):
    save(client)

    data = client.get(
        "/api/analysis?month=2026-07&age_group=20대초반&income_group=mid-low"
    ).get_json()["data"]

    assert data["peer_group"] == "20대초반 / mid-low"
    assert data["user_total"] == 12000
    assert data["peer_average"] > 0
    assert data["by_category"]["cafe"]["user"] == 12000
    assert data["advice"] == "테스트 조언입니다."
    assert len(gemini_calls.prompts) == 1


def test_analysis_unknown_group_has_no_peer_data(client, gemini_calls):
    save(client)

    data = client.get(
        "/api/analysis?month=2026-07&age_group=없는그룹&income_group=mid-low"
    ).get_json()["data"]

    assert data["has_peer_data"] is False
    assert data["peer_average"] == 0
    assert not gemini_calls.prompts


# ── 에러 응답 형식 ───────────────────────────────────
def test_unknown_api_path_is_json(client):
    res = client.get("/api/nope")
    assert res.status_code == 404
    assert res.get_json() == {"success": False, "error": "없는 API 경로입니다"}


def test_wrong_method_is_json_405(client):
    res = client.put("/api/stats")
    assert res.status_code == 405
    assert res.get_json()["success"] is False
