from datetime import datetime
from functools import lru_cache
import json
import logging
import os
import re
import ssl
import time

from google import genai
from dotenv import load_dotenv
import httpx

import database

load_dotenv()

logger = logging.getLogger(__name__)

# ─── Gemini 클라이언트 (지연 생성) ─────────────────────────────────────────────
# 모듈 최상단에서 Client를 만들면 GEMINI_API_KEY가 없을 때 import 자체가 터져서
# Flask 서버가 아예 뜨지 않는다. 키 확인은 실제 호출 시점으로 미룬다.
MODEL_NAME = "gemini-3.8-flash"

# MODEL_NAME이 막히면 차례로 넘어갈 보조 모델. 무료 등급 분당 한도(429)는 모델마다 따로 잡혀서
# 기본 모델이 막혀도 다른 모델은 대개 바로 받아준다. 모델이 은퇴하면 client.models.list()로 확인하고 여기만 고친다.
FALLBACK_MODEL_NAMES = ("gemini-3.5-flash-lite", "gemini-3.7-flash")

# 파싱 결과에 반드시 있어야 하는 필드 (card는 없어도 허용)
REQUIRED_FIELDS = ["amount", "store", "category", "date", "time"]

# Gemini는 503(과부하)이 잦고, 무료 등급은 모델당 분당 5회(실패한 재시도도 포함)라 429도 쉽게 난다.
# 같은 모델로 여러 번 재시도하면 한도만 빨리 쓰므로, 한 번 더 해보고 안 되면 다음 모델로 넘어간다.
ATTEMPTS_PER_MODEL = 2
RETRY_DELAY = 1.0                         # 초, 같은 모델로 다시 보내기 전 대기
RETRYABLE_STATUSES = (500, 502, 503, 504)  # 같은 모델로 한 번 더
SWITCH_MODEL_STATUSES = (429, 404)        # 분당 한도·모델 은퇴: 같은 모델은 당분간 계속 실패 → 바로 다음 모델

# 상태코드 없이 연결 단계에서 끊기는 오류 (SSL 끊김, 연결 리셋, 타임아웃).
# SDK가 httpx로 통신해서 대부분 httpx.TransportError로 오고, 감싸지 않은 SSL·소켓 오류도 같이 본다.
# 이것도 일시적이라 다시 보내면 대개 성공한다.
NETWORK_ERRORS = (httpx.TransportError, ssl.SSLError, ConnectionError, TimeoutError)

# 다시 보내도 똑같이 실패하는 오류는 원인과 할 일을 알려준다 (원본 예외 문구는 서버 로그에만 남긴다)
STATUS_MESSAGES = {
    400: "Gemini가 요청을 거부했어요. .env의 GEMINI_API_KEY가 올바른지 확인해주세요.",
    403: "Gemini API 키에 권한이 없어요. .env의 GEMINI_API_KEY를 확인해주세요.",
    404: "사용할 수 있는 Gemini 모델을 찾지 못했어요. 모델이 은퇴했을 수 있어요 (gemini_parser.MODEL_NAME 확인).",
}


@lru_cache(maxsize=1)
def _get_client():
    """클라이언트를 한 번만 만들어 재사용한다 (요청마다 새로 만들지 않는다)."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY가 설정되지 않았습니다. .env 파일에 키를 넣어주세요."
        )
    return genai.Client(api_key=api_key)


PROMPT_TEMPLATE = """
다음 카드 결제 문자에서 정보를 추출해줘.
반드시 아래 JSON 형식으로만 응답해. 다른 말은 절대 하지 마.

{
  "amount": 숫자 (원 단위 정수, 쉼표 없이),
  "store": "상점명",
  "category": "food|cafe|transport|shopping|medical|leisure|etc 중 하나",
  "date": "YYYY-MM-DD",
  "time": "HH:MM",
  "card": "카드사명"
}

오늘은 {today}이다. 문자에 연도가 없으면 {current_year}년으로 간주해라.

SMS: {sms_text}
"""


def _status_code(exc) -> int | None:
    """예외에서 HTTP 상태코드를 뽑아낸다. SDK 버전에 따라 속성명이 달라서 문자열도 본다."""
    for attr in ("code", "status_code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value

    match = re.search(r"\b([45]\d\d)\b", str(exc))
    return int(match.group(1)) if match else None


def _is_network_error(exc) -> bool:
    return isinstance(exc, NETWORK_ERRORS)


def _error_label(exc) -> str:
    """로그용 오류 이름. 네트워크 오류는 상태코드가 없으므로 예외 타입명을 쓴다."""
    # 네트워크 오류를 먼저 본다. 문구에 ':443' 같은 포트가 있으면 _status_code가 443으로 오인한다.
    if _is_network_error(exc):
        return type(exc).__name__
    return str(_status_code(exc))


def _failover_action(exc) -> str:
    """
    실패를 어떻게 이어갈지 정한다.
    'retry' 같은 모델로 한 번 더 / 'switch' 바로 다음 모델로 / 'fail' 즉시 실패
    """
    if _is_network_error(exc):
        return "retry"

    status = _status_code(exc)
    if status in SWITCH_MODEL_STATUSES:
        return "switch"
    if status in RETRYABLE_STATUSES:
        return "retry"

    # 400·403(키 문제) 등은 어느 모델로 보내도 똑같이 실패한다
    return "fail"


def generate_text(prompt: str) -> str:
    """
    일반 텍스트 생성. Gemini 호출을 이 모듈 하나로 모아 모델명이 갈라지지 않게 한다.
    MODEL_NAME부터 FALLBACK_MODEL_NAMES 순서로 시도하고, 모두 실패하면 마지막 오류를 그대로 올린다.
    """
    models = (MODEL_NAME, *FALLBACK_MODEL_NAMES)

    for index, model in enumerate(models):
        is_last_model = index == len(models) - 1

        for attempt in range(1, ATTEMPTS_PER_MODEL + 1):
            try:
                response = _get_client().models.generate_content(model=model, contents=prompt)
                if model != MODEL_NAME:
                    logger.info("보조 모델(%s)로 응답했습니다.", model)
                return response.text.strip()

            except Exception as e:
                action = _failover_action(e)
                give_up_model = action == "switch" or attempt == ATTEMPTS_PER_MODEL

                if action == "fail" or (give_up_model and is_last_model):
                    raise

                if give_up_model:
                    logger.warning(
                        "Gemini %s 실패(%s). %s로 넘어갑니다.",
                        model, _error_label(e), models[index + 1],
                    )
                    break

                logger.warning(
                    "Gemini %s 일시적 오류(%s). %.1f초 후 재시도",
                    model, _error_label(e), RETRY_DELAY,
                )
                time.sleep(RETRY_DELAY)

    # 도달하지 않는다 (마지막 모델의 마지막 시도는 위에서 raise된다)
    raise RuntimeError("Gemini 호출에 실패했습니다.")


def _strip_code_fence(raw: str) -> str:
    """```json ... ``` 형태로 감싸져 오면 펜스를 제거한다."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def to_int_amount(value) -> int:
    """
    '12,000' / '12000원' / 12000 모두 12000으로 정규화한다.
    음수 부호는 보존한다. 숫자만 남기면 -500이 조용히 500이 되어
    호출부의 검증을 그대로 통과해버린다.
    """
    text = str(value).strip()
    is_negative = text.startswith("-")

    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        raise ValueError(f"금액을 숫자로 변환할 수 없습니다: {value!r}")

    amount = int(digits)
    return -amount if is_negative else amount


def parse_sms(sms_text):
    try:
        # 프롬프트에 JSON 중괄호가 있어 str.format()은 KeyError를 낸다 → replace 사용
        today = datetime.now()
        prompt = (
            PROMPT_TEMPLATE
            .replace("{today}", today.strftime("%Y년 %m월 %d일"))
            .replace("{current_year}", str(today.year))
            .replace("{sms_text}", sms_text)
        )

        parsed = json.loads(_strip_code_fence(generate_text(prompt)))

        missing = [f for f in REQUIRED_FIELDS if not parsed.get(f)]
        if missing:
            return {
                "success": False,
                "error": f"문자에서 {', '.join(missing)} 항목을 읽지 못했습니다. 문자 내용을 확인해주세요.",
                "status": 400,
            }

        parsed["amount"] = to_int_amount(parsed["amount"])

        # 7개 고정 카테고리 외의 값이 들어오면 통계에서 조용히 누락되므로 etc로 보정
        if parsed.get("category") not in database.CATEGORIES:
            parsed["category"] = "etc"

        return {"success": True, "data": parsed}

    # status는 라우트가 HTTP 코드를 고르기 위한 내부 힌트다 (응답 본문에는 넣지 않는다).
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "Gemini 응답을 JSON으로 읽지 못했습니다.",
            "status": 400,
        }
    except ValueError as e:
        return {"success": False, "error": str(e), "status": 400}
    except RuntimeError as e:
        return {"success": False, "error": str(e), "status": 500}
    except Exception as e:
        # 원본 예외 문구(SSL 내부 메시지, 응답 JSON 등)는 사용자에게 보내지 않고 로그에만 남긴다
        logger.warning("Gemini 호출 실패(%s): %s", _error_label(e), e)
        return {"success": False, "error": _user_message(e), "status": 502}


def _user_message(exc) -> str:
    """Gemini 호출 실패를 사용자가 할 일이 보이는 문구로 바꾼다."""
    if _is_network_error(exc):
        return (
            "Gemini 서버와 연결이 끊겼어요. 여러 번 시도했지만 실패했어요. "
            "인터넷 연결을 확인하고 잠시 후 다시 시도해주세요."
        )

    status = _status_code(exc)
    if status == 429:
        return "Gemini 무료 사용량(분당 한도)을 넘었어요. 1분쯤 뒤에 다시 시도해주세요."
    if status in RETRYABLE_STATUSES:
        return (
            "Gemini 서버가 혼잡합니다. 여러 모델로 시도했지만 실패했어요. "
            "잠시 후 다시 시도해주세요."
        )

    return STATUS_MESSAGES.get(
        status,
        "Gemini 호출에 실패했어요. 잠시 후 다시 시도하고, 계속되면 서버 로그를 확인해주세요.",
    )
