from datetime import datetime
import logging
import os
import socket

from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

import database
import gemini_parser
import seed

load_dotenv()

logging.basicConfig(level=logging.INFO)

# ─── 설정 ─────────────────────────────────────────────
# 기본값은 LAN 공개(0.0.0.0). 인터넷 배포로 넘어가도 이 세 값만 환경변수로 바꾸면 된다.
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '5000'))
DEBUG = os.getenv('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')

# 프론트가 상대경로(/api)로 호출하므로 동일 출처다.
# 전체 허용 CORS를 켜두면 LAN에 열린 서버에 외부 페이지가 요청을 보낼 수 있어 두지 않는다.
app = Flask(__name__)

database.init_db()

# 또래 데이터가 비어 있으면 자동으로 채운다.
# 재배포·재클론 때마다 수동으로 seed.py를 돌리지 않아도 되고,
# 빠뜨렸을 때 또래 평균이 조용히 0이 되는 문제도 막는다.
if database.count_peer_averages() == 0:
    app.logger.info("또래 비교 데이터가 비어 있어 자동으로 채웁니다.")
    seed.seed()

# POST /api/transactions 저장에 반드시 필요한 필드 (card는 없어도 허용)
REQUIRED_TRANSACTION_FIELDS = ['amount', 'store', 'category', 'date', 'time']

# 카드 결제 문자는 100자 안팎이다. 긴 글을 통째로 붙여넣으면 Gemini 호출 시간만 늘어나므로 막는다.
MAX_SMS_LENGTH = 1000


def error_response(message, status=500, exc=None):
    """
    에러 응답을 한 형태로 통일한다.
    DEBUG가 아니면 내부 예외 메시지(SQL·경로 등)를 클라이언트에 노출하지 않고
    서버 로그에만 남긴다.
    """
    if exc is not None:
        app.logger.exception("요청 처리 실패: %s", exc)
        if DEBUG:
            message = f"{message}: {exc}"

    return jsonify({"success": False, "error": message}), status


@app.route('/')
def index():
    return render_template('index.html')

# ── SMS 파싱 ──────────────────────────────────────────
# 파싱은 미리보기까지만 담당한다. 저장은 POST /api/transactions 하나로만 이뤄진다.
# (두 곳에서 저장하면 "분석하기" + "저장하기"로 같은 거래가 두 번 들어간다)
@app.route('/api/parse', methods=['POST'])
def parse_sms():
    try:
        data = request.get_json(silent=True)
        sms = data.get('sms') if isinstance(data, dict) else None
        if not isinstance(sms, str) or not sms.strip():
            return jsonify({"success": False, "error": "sms 필드가 없습니다"}), 400

        if len(sms) > MAX_SMS_LENGTH:
            return jsonify({
                "success": False,
                "error": f"문자는 {MAX_SMS_LENGTH:,}자까지 입력할 수 있어요. 결제 문자 한 건만 붙여넣어주세요.",
            }), 400

        result = gemini_parser.parse_sms(sms)
        if not result['success']:
            status = result.pop('status', 500)
            return jsonify({"success": False, "error": result['error']}), status

        return jsonify({"success": True, "data": result['data']})

    except Exception as e:
        return error_response("문자를 분석하지 못했습니다", 500, e)


def _clean_transaction(data):
    """
    저장할 거래를 검증하고 DB 컬럼에 맞는 dict로 만든다.
    잘못된 입력은 ValueError로 알린다 (라우트에서 400으로 바꾼다).
    """
    if not data:
        raise ValueError("요청 본문이 비어있습니다")

    # amount가 0일 때 '누락'으로 잡히지 않도록 None/빈 문자열만 누락으로 본다
    missing = [f for f in REQUIRED_TRANSACTION_FIELDS
               if data.get(f) is None or data.get(f) == '']
    if missing:
        raise ValueError(f"필수 항목이 없습니다: {', '.join(missing)}")

    # SQLite는 타입이 느슨해서 INTEGER 컬럼에 문자열도 그대로 들어간다.
    # 검증 없이 저장하면 SUM()이 깨져 통계 총액이 오염된다.
    try:
        amount = gemini_parser.to_int_amount(data['amount'])
    except ValueError as exc:
        raise ValueError(f"금액이 올바르지 않습니다: {data['amount']!r}") from exc

    if amount <= 0:
        raise ValueError("금액은 0보다 커야 합니다")

    if data['category'] not in database.CATEGORIES:
        raise ValueError(f"알 수 없는 카테고리입니다: {data['category']!r}")

    # DB 컬럼에 해당하는 키만 뽑는다 (id 등 불필요한 키가 섞여 들어오는 것을 막는다)
    return {
        'amount':   amount,
        'store':    data['store'],
        'category': data['category'],
        'date':     data['date'],
        'time':     data['time'],
        'card':     data.get('card'),
    }


# ── 거래 저장 ─────────────────────────────────────────
@app.route('/api/transactions', methods=['POST'])
def save_transaction():
    try:
        transaction = _clean_transaction(request.get_json(silent=True))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    try:
        transaction_id = database.insert_transaction(transaction)
        return jsonify({"success": True, "data": {"id": transaction_id}})

    except Exception as e:
        return error_response("거래를 저장하지 못했습니다", 500, e)


# ── 거래 삭제 ─────────────────────────────────────────
# 잘못 저장한 거래를 되돌릴 방법이 없어 추가했다. <int:...>라서 숫자가 아닌 id는
# 라우트에 걸리지 않고 handle_404가 JSON으로 응답한다.
@app.route('/api/transactions/<int:transaction_id>', methods=['DELETE'])
def delete_transaction(transaction_id):
    try:
        if not database.delete_transaction(transaction_id):
            return jsonify({"success": False, "error": "해당 거래를 찾을 수 없습니다"}), 404

        return jsonify({"success": True, "data": {"id": transaction_id}})

    except Exception as e:
        return error_response("거래를 삭제하지 못했습니다", 500, e)


# ── 거래 내역 조회 ────────────────────────────────────
@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    try:
        month    = request.args.get('month')
        category = request.args.get('category')
        search   = request.args.get('search')

        rows = database.get_transactions(month, category, search)
        return jsonify({"success": True, "data": rows, "total": len(rows)})

    except Exception as e:
        return error_response("거래 내역을 불러오지 못했습니다", 500, e)


# ── 대시보드 통계 ─────────────────────────────────────
@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        month = request.args.get('month')
        if not month:
            month = datetime.now().strftime('%Y-%m')

        stats = database.get_stats(month)
        return jsonify({"success": True, "data": stats})

    except Exception as e:
        return error_response("통계를 불러오지 못했습니다", 500, e)


# ── AI 분석 & 또래 비교 ───────────────────────────────
@app.route('/api/analysis', methods=['GET'])
def get_analysis():
    try:
        month      = request.args.get('month', datetime.now().strftime('%Y-%m'))
        age_group  = request.args.get('age_group', '20대초반')
        income_group = request.args.get('income_group', 'mid-low')

        stats = database.get_stats(month)
        peer  = database.get_peer_averages(age_group, income_group)

        by_category = {
            cat: {"user": user_amt, "peer_avg": peer.get(cat, 0)}
            for cat, user_amt in stats['by_category'].items()
        }

        peer_total = sum(peer.values())

        # 시드가 없거나 해당 그룹 조합이 없으면 peer가 {}로 온다.
        # 이때 또래 평균 0원을 그대로 보여주면 "내가 무한히 더 쓴다"처럼 오해되므로 구분해서 안내한다.
        if not peer:
            advice = (
                f"'{age_group} / {income_group}' 그룹의 또래 데이터가 없습니다. "
                "python seed.py 를 실행해 또래 비교 데이터를 채워주세요."
            )
        # 지출이 없는 달은 비교할 내용이 없다. Gemini를 부르면 전부 0원인 데이터로
        # 의미 없는 조언이 나오고 호출(과 503 위험)만 늘어나므로 건너뛴다.
        elif stats['total_amount'] == 0:
            advice = (
                f"{month}에는 지출 내역이 없어 맞춤 조언을 만들지 않았습니다. "
                "결제 문자를 입력하면 또래 평균과 비교해 조언해드립니다."
            )
        else:
            advice = _generate_advice(stats['by_category'], peer)

        return jsonify({
            "success": True,
            "data": {
                "user_total":    stats['total_amount'],
                "peer_average":  peer_total,
                "peer_group":    f"{age_group} / {income_group}",
                "has_peer_data": bool(peer),
                "by_category":   by_category,
                "advice":        advice
            }
        })

    except Exception as e:
        return error_response("분석 데이터를 불러오지 못했습니다", 500, e)


def _generate_advice(user_by_category, peer):
    try:
        summary = "\n".join([
            f"- {cat}: 내 지출 {user_by_category.get(cat, 0)}원 / 또래 평균 {peer.get(cat, 0)}원"
            for cat in user_by_category
        ])

        prompt = f"""아래는 이번 달 소비 내역과 또래 평균 비교야.
{summary}

이 데이터를 바탕으로 2~3문장으로 맞춤형 소비 조언을 한국어로 작성해줘.
구체적인 절약 금액이나 횟수를 포함해서 실용적으로 써줘."""

        # 모델명·클라이언트는 gemini_parser 한 곳에서만 관리한다
        return gemini_parser.generate_text(prompt)

    except Exception as e:
        # 통째로 삼키면 키 오류와 일시적 장애를 구분할 수 없어 원인을 서버 로그에 남긴다
        app.logger.warning("조언 생성 실패: %s", e)
        return "조언을 생성하지 못했습니다. 잠시 후 다시 시도해주세요."


# ── 에러 핸들러 ───────────────────────────────────────
# /api/* 는 Flask 기본 HTML 에러 페이지 대신 JSON을 돌려줘야
# 프론트의 공통 request() 헬퍼가 메시지를 읽을 수 있다.
@app.errorhandler(404)
def handle_404(_e):
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "error": "없는 API 경로입니다"}), 404
    return render_template('index.html'), 404


@app.errorhandler(405)
def handle_405(_e):
    return jsonify({"success": False, "error": "허용되지 않는 요청 방식입니다"}), 405


@app.errorhandler(500)
def handle_500(e):
    return error_response("서버 내부 오류가 발생했습니다", 500, e)


def _lan_ip():
    """LAN에서 접속할 때 쓸 IP를 찾는다 (실제로 연결하지는 않는다)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0]
    except OSError:
        return None


if __name__ == '__main__':
    print()
    print('  스마트 가계부 서버를 시작합니다.')
    print(f'  이 컴퓨터    : http://localhost:{PORT}')

    ip = _lan_ip()
    if HOST == '0.0.0.0' and ip:
        print(f'  같은 와이파이: http://{ip}:{PORT}')
        print('  (처음 실행 시 Windows 방화벽 허용 창이 뜨면 "개인 네트워크"를 체크하고 허용하세요)')
    print()

    app.run(host=HOST, port=PORT, debug=DEBUG)
