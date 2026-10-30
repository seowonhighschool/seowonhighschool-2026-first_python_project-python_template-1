# tests/test_parser.py
# gemini_parser의 후처리(금액 정규화, 코드펜스 제거, 카테고리 보정, 재시도 판단)를 네트워크 없이 검사한다.
import json

import pytest

import gemini_parser


# ── to_int_amount ────────────────────────────────────
@pytest.mark.parametrize("value, expected", [
    (12000, 12000),
    ("12000", 12000),
    ("12,000", 12000),
    ("12,000원", 12000),
    (" 1,234,567원 ", 1234567),
    ("-500", -500),   # 부호를 지우면 음수가 양수로 둔갑해 검증을 통과한다
])
def test_to_int_amount(value, expected):
    assert gemini_parser.to_int_amount(value) == expected


@pytest.mark.parametrize("value", ["", "원", "abc", None])
def test_to_int_amount_rejects_non_numbers(value):
    with pytest.raises(ValueError):
        gemini_parser.to_int_amount(value)


# ── 코드펜스 제거 ────────────────────────────────────
@pytest.mark.parametrize("raw", [
    '{"a": 1}',
    '```json\n{"a": 1}\n```',
    '```\n{"a": 1}\n```',
    '  ```json{"a": 1}```  ',
])
def test_strip_code_fence(raw):
    # pylint: disable=protected-access
    assert json.loads(gemini_parser._strip_code_fence(raw)) == {"a": 1}


# ── parse_sms 후처리 ─────────────────────────────────
VALID_REPLY = {
    "amount": "12,000",
    "store": "스타벅스",
    "category": "cafe",
    "date": "2026-07-14",
    "time": "14:32",
    "card": "신한카드",
}


def reply_with(gemini_calls, **overrides):
    gemini_calls.reply = "```json\n" + json.dumps({**VALID_REPLY, **overrides}) + "\n```"


def test_parse_sms_normalizes_reply(gemini_calls):
    reply_with(gemini_calls)

    result = gemini_parser.parse_sms("[신한카드] 승인 12,000원 스타벅스 07/14 14:32")

    assert result["success"] is True
    assert result["data"]["amount"] == 12000
    assert result["data"]["category"] == "cafe"


def test_parse_sms_prompt_has_sms_and_base_year(gemini_calls):
    reply_with(gemini_calls)
    gemini_parser.parse_sms("문자 본문 {중괄호}")

    prompt = gemini_calls.prompts[0]
    assert "SMS: 문자 본문 {중괄호}" in prompt
    # 기준 연도가 없으면 '07/14'를 과거 연도로 추론해 월별 통계에서 빠진다
    assert "{current_year}" not in prompt
    assert "{today}" not in prompt


def test_parse_sms_unknown_category_becomes_etc(gemini_calls):
    reply_with(gemini_calls, category="coffee")
    assert gemini_parser.parse_sms("x")["data"]["category"] == "etc"


def test_parse_sms_missing_field_is_400(gemini_calls):
    reply_with(gemini_calls, store="")
    result = gemini_parser.parse_sms("x")

    assert result["success"] is False
    assert result["status"] == 400
    assert "store" in result["error"]


def test_parse_sms_non_json_reply_is_400(gemini_calls):
    gemini_calls.reply = "죄송하지만 문자를 이해하지 못했어요."
    result = gemini_parser.parse_sms("x")

    assert result["success"] is False
    assert result["status"] == 400


# ── 재시도·모델 전환 판단 ────────────────────────────
class FakeApiError(Exception):
    def __init__(self, code):
        super().__init__(f"{code} error")
        self.code = code


@pytest.mark.parametrize("exc, action", [
    (FakeApiError(503), "retry"),
    (FakeApiError(500), "retry"),
    (FakeApiError(429), "switch"),
    (FakeApiError(404), "switch"),
    (FakeApiError(400), "fail"),
    (FakeApiError(403), "fail"),
    (ConnectionResetError("reset"), "retry"),
    (TimeoutError("timeout"), "retry"),
])
def test_failover_action(exc, action):
    # pylint: disable=protected-access
    assert gemini_parser._failover_action(exc) == action


def test_generate_text_switches_model_on_429(monkeypatch):
    """기본 모델이 429면 같은 모델로 재시도하지 않고 바로 보조 모델로 넘어간다."""
    called = []

    class FakeModels:
        def generate_content(self, model, contents):  # pylint: disable=unused-argument
            called.append(model)
            if model == gemini_parser.MODEL_NAME:
                raise FakeApiError(429)
            return type("Response", (), {"text": " 보조 모델 응답 "})()

    fake_client = type("Client", (), {"models": FakeModels()})()
    monkeypatch.setattr(gemini_parser, "_get_client", lambda: fake_client)

    assert gemini_parser.generate_text("hi") == "보조 모델 응답"
    assert called == [gemini_parser.MODEL_NAME, gemini_parser.FALLBACK_MODEL_NAMES[0]]


def test_user_message_hides_raw_error():
    # pylint: disable=protected-access
    msg = gemini_parser._user_message(ConnectionResetError("[SSL: UNEXPECTED_EOF_WHILE_READING]"))
    assert "SSL" not in msg
