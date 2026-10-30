# CLAUDE.md — SMS Budget Tracker (문자 기반 자동 가계부)

> 이 파일은 Claude가 프로젝트 맥락을 바로 이해하도록 만든 지침서다.
> **실제 코드가 이 문서와 다르면 코드를 먼저 확인하고**, 불일치는 사용자에게 알린 뒤 진행한다.

---

## 1. 프로젝트 개요

카드 결제 문자(SMS)를 텍스트로 입력하면 **Gemini API**가 금액·상점명·일시·카드사를 추출하고 카테고리로 분류해 DB에 저장한다. 이후 나이대·소득 수준이 비슷한 또래 그룹의 평균 소비와 비교하고, 맞춤형 소비 개선 조언을 제공한다.

- 참고 서비스: 토스 (카드 연동 기반 소비 분류)
- 기대효과: 가계부 작성 시간 90% 이상 단축 / Chart.js 소비 패턴 시각화 / 또래 비교를 통한 소비 억제
- 개발 일정(5일): 환경 구축 → SMS 파싱 → 통계·또래 비교 API → 4탭 프론트 → 통합 테스트·완성도 향상

## 2. 팀 · 협업 방식

- **박도연**, **이효재** 2인 팀. 계획서상 역할은 나뉘어 있으나 **실제로는 프론트·백엔드 구분 없이 전체 코드를 함께 작성**한다.
- Claude는 요청에 따라 **프론트엔드(HTML/CSS/JS)와 백엔드(Python/Flask/SQLite) 모두** 도와준다.
- 구조·설계 논의, 코드 충돌, 프론트-백엔드 인터페이스 불일치가 생기면 해결 방향을 함께 제시한다.
- 사용자(박도연)는 **한국어로 편하게** 소통하고, 에러는 **스크린샷**으로 공유하는 경우가 많다. 스크린샷이 오면 내용을 읽고 원인 분석 → 수정 코드 순서로 답한다.

## 3. 현재 진행 상황 (2026-10-16 기준)

### 완료
- Flask + SQLite + Vanilla JS 웹앱 골격, GitHub 저장소 연동 (`seowonhighschool` org, `first-python-project-Yyeon222`, **`dev` 브랜치**), 이효재 collaborator 추가
- 영문 README 작성 (shields.io 배지 포함, 프로젝트가 인상적으로 보이는 것을 중시)
- `peer_averages` 테이블 확장: **연령대 × 소득 구간 × 카테고리** 구조, KOSIS 가계 지출 데이터 기반 **224행** 시드
- `/api/analysis` 엔드포인트 및 프론트 드롭다운(연령대·소득 구간) 필터링 — **end-to-end 동작 확인 완료**
- 중첩 `.git` 폴더 문제 → **GitHub에서 깨끗하게 re-clone**하여 해결
- **`POST /api/parse` 500 해결** (원인: Gemini 모델명 은퇴. 아래 19절 참조)
- 내역 조회의 카테고리 필터·상점명 검색 백엔드 구현 (기존엔 프론트만 파라미터를 보내고 백엔드가 무시)
- 거래 중복 저장 버그 수정 (`/api/parse`가 저장까지 하고 있었음)
- `requirements.txt` UTF-16 → UTF-8 재작성 (UTF-16이면 `pip install -r`이 실패)
- **Gemini 재시도 + 보조 모델 전환** (`generate_text`). 5xx·**네트워크 끊김**(SSL EOF·연결 리셋·타임아웃,
  `NETWORK_ERRORS`)은 같은 모델로 한 번 더, **429(분당 한도)·404(모델 없음)는 바로 다음 모델**로 넘어간다.
  순서: `MODEL_NAME` → `FALLBACK_MODEL_NAMES`. 400·403(키 문제)은 즉시 실패.
  2026-10-16 실측(카드사 예시 4종 반복, 호출 간격 5~6초): 같은 모델 재시도만 할 때 **2/6(33%)** →
  모델 전환 후 **14/14(100%)**, 필드 정확 14/14, 최장 응답 18.4초 → 6.7초. 두 번째 보조 모델은 실측에서 쓰이지 않았다
- Gemini 실패 시 **원본 예외 문구를 응답에 넣지 않는다.** `gemini_parser._user_message()`가 네트워크/혼잡/
  잘못된 키(400·403)/모델 없음(404)별 안내 문구로 바꾸고, 원본은 서버 로그에만 남긴다
- **미리보기 카테고리 수정**: Gemini가 고른 카테고리를 저장 전에 7개 드롭다운으로 바꿀 수 있다 (프론트만 변경)
- 내역 조회 **건수 표시**(`total`), `/api/parse` **1,000자 제한**, 또래 데이터 없음일 때 비교 차트 대신 안내
- 대시보드 일별 차트를 **일별 누적 라인**으로 변경 (13절 지침대로). 지출 없는 날도 채우고, 이번 달은 오늘까지만
- **거래 삭제**: `DELETE /api/transactions/<id>` + 내역 행을 누르면 열리는 상세 다이얼로그(시간·카드사 표시, 빨간 "삭제" 버튼,
  기본 포커스는 "닫기"). 새 API는 2026-10-16 이효재 확인으로 확정
- **LAN 공개**: `0.0.0.0` 바인딩, `api.js`를 상대경로로 전환, 시작 시 LAN 주소 출력
- 서버 시작 시 또래 데이터가 비어 있으면 **자동 seed**
- 운영 설정: `FLASK_DEBUG` 기본 꺼짐, 내부 예외 메시지 비노출, `/api/*` 404·405를 JSON으로 응답
- 거래 저장 시 **금액·카테고리 검증** (문자열 금액이 SQLite에 그대로 들어가 통계가 깨지던 문제)
- 로딩 오버레이 중첩 가드, 검색 debounce(300ms), 상점명 XSS 방어
- `style.css`의 `[hidden]` 중첩 구조 정리, Chart.js 4.5.0 버전 고정 + SRI
- **GitHub Actions Pylint** 도입 (`.pylintrc`, 현재 10.00/10, `--fail-under=9.0`)
- 대시보드·내역 조회 **빈 상태 안내** (`utils.js`의 `createEmptyState()`). 지출 없는 달은 차트 대신 안내,
  내역은 "그 달에 내역 없음"과 "필터 결과 없음"을 구분한다. 빈 행이 `.table td:last-child`에 걸려
  우측 정렬·주색으로 보이던 CSS 우선순위 문제도 함께 수정
- AI 분석 **빈 데이터 처리**: 지출 0원인 달은 백엔드가 Gemini를 호출하지 않고(`advice`에 안내 문구),
  프론트는 비교 차트·조언 대신 빈 상태 안내를 보여준다. 내 지출/또래 평균 카드(`peer_group`)는 그대로 표시
- 내역 표 **375px 줄바꿈 정리**: 날짜·카테고리·금액은 한 줄 고정, 상점명만 단어 단위 줄바꿈.
  표는 항상 월로 걸러지므로 날짜를 `10.14`(`formatShortDate()`)로 줄였다. "금액" 헤더 우측 정렬 누락도 수정
- **계획서 대비 점검 (2026-10-31)**: 핵심 기능·1~4일차는 완료. 빠졌던 두 가지를 보완했다
  - 대시보드 **최근 6개월 추이 막대**. API는 그대로 두고 `GET /api/stats`를 6번 병렬 호출한다
    (`getRecentMonths()`, `MONTHLY_TREND_COUNT`). 선택한 달만 주색, 6개월 모두 0원이면 카드를 숨긴다
  - **pytest 자동 테스트 61개** (`tests/`). Gemini는 가짜로 대체하고 임시 DB를 써서 키·네트워크 없이 돈다.
    CI(`pylint.yml`)에서도 실행한다
  - 남은 것(코드 밖): "작성 시간 90% 단축" 실측, 동아리 발표 때 사용자 피드백 수집
- **UI 다크 프리미엄 리디자인 (2026-10-31)**: 토큰 전면 교체, Pretendard 웹폰트, SVG 아이콘, 히어로 카드,
  유리 효과 헤더·탭 바, 차트 색을 토큰에서 읽기. 동작·API 변경 없음 (15절 참조)
- **로그인·회원가입 (2026-10-31, 이효재 합의)**: 아이디+비밀번호, Flask 세션 쿠키, `werkzeug.security` 해시(새 패키지 없음).
  거래·통계·분석·파싱은 로그인한 사용자 것만. 가입 때 연령대·소득을 받아 AI 분석 기본값으로 쓴다.
  로그인 도입 전 거래는 **첫 가입 계정**이 넘겨받는다. 테스트 90개 (`tests/test_auth.py` 추가)

### 다음 할 일
- 동아리 발표 후 필요하면 인터넷 공개 배포 (Render 등). 그때는 `HOST`/`PORT`만 바꾸면 되고
  WSGI 서버(gunicorn 등)와 `.env` 대신 플랫폼 환경변수 설정이 필요하다

### 알려진 제약
- Gemini가 자주 **503 UNAVAILABLE**(과부하)을 반환한다. 2026-10-16 측정에서 기본 모델 시도의 대부분이 503이었다.
- **무료 등급은 모델당 분당 5회**(`GenerateRequestsPerMinutePerProjectPerModel-FreeTier`)이고 **실패한 재시도도 횟수에 들어간다.**
  같은 모델로 재시도를 늘리면 오히려 429가 나므로, 한도가 따로 잡히는 보조 모델로 넘어가는 방식을 쓴다.
  AI 분석 탭의 조언 생성도 같은 한도를 쓴다 (드롭다운을 연달아 바꾸면 그만큼 호출된다).
- 모든 모델이 막히면 "잠시 후 다시 시도"(503) 또는 "1분쯤 뒤에 다시 시도"(429) 안내가 나간다.
- `app.py`는 Flask 개발 서버다. LAN 발표용으로는 충분하지만 인터넷 공개 시에는 WSGI 서버를 써야 한다.
- 다른 기기에서 접속하려면 **Windows 방화벽에서 5000 포트 인바운드 허용**이 필요하다 (19절 참조).
- LAN은 **HTTP라 로그인 비밀번호가 암호화 없이** 와이파이로 전송된다. 다른 사이트와 같은 비밀번호를 쓰지 않도록 안내한다
  (가입 화면 문구). 인터넷 배포 시에는 HTTPS 필수, 그때 `SESSION_COOKIE_SECURE=True`도 켠다
- 로그인 시도 횟수 제한·비밀번호 변경·탈퇴는 없다

## 4. 기술 스택 · 개발 환경

| 영역 | 기술 |
|---|---|
| 백엔드 | Python 3, Flask |
| DB | SQLite |
| 프론트엔드 | Vanilla JS (ES6+), HTML5, CSS3 |
| 시각화 | Chart.js |
| AI | Google Gemini API — SDK `google-genai`, 모델 **`gemini-3.8-flash`** (막히면 `gemini-3.5-flash-lite` → `gemini-3.7-flash`) |
| 환경변수 | python-dotenv (`.env`) |
| 협업 | GitHub (GitHub Classroom), VS Code |

- 환경: **Windows + PowerShell + Python venv**
- **서버는 기본적으로 `0.0.0.0`에 바인딩**되어 같은 와이파이의 다른 기기에서도 접속할 수 있다.
  실행하면 터미널에 LAN 주소(`http://192.168.x.x:5000`)가 출력된다.
  `HOST` / `PORT` / `FLASK_DEBUG` 환경변수로 바꿀 수 있다 (12절 표 참조).
- **`FLASK_DEBUG`는 기본 꺼짐.** 켠 채로 외부에 노출하면 Werkzeug 디버거로 임의 코드 실행이 가능하다.
- **모델명은 `gemini_parser`의 `MODEL_NAME`(기본)·`FALLBACK_MODEL_NAMES`(보조)에서만 관리한다.** 다른 파일에 모델명을 하드코딩하지 않는다.
  - `gemini-2.5-flash`는 **신규 사용자에게 404로 차단**되어 더 이상 쓸 수 없다 (`models.list()`에는 나오지만 호출이 막힌다).
  - 모델이 또 은퇴하면 `client.models.list()`로 사용 가능한 목록을 먼저 확인한다.
- `requirements.txt`는 **UTF-8로 저장**한다. PowerShell에서 `pip freeze > requirements.txt`를 하면 UTF-16으로 저장되어 설치가 깨진다.
- 서버 실행: `python app.py` → `http://localhost:5000`
- 테스트: `python -m pytest -q` (pytest는 `requirements.txt`가 아니라 개발 도구로 따로 설치: `pip install pytest`)

## 5. 파일 구조

```
project-root/
├── app.py                  # Flask 엔트리포인트
├── database.py             # DB 처리 로직
├── gemini_parser.py        # Gemini API 파싱 모듈 (모델명·클라이언트 단일 관리)
├── seed.py                 # 또래 비교 데이터 초기 삽입
├── requirements.txt        # UTF-8, 직접 의존성만
├── .pylintrc               # Pylint 설정 (CI와 로컬이 같은 기준을 쓴다)
├── pytest.ini              # 테스트에서 루트 모듈을 import하도록 pythonpath 설정
├── tests/                  # conftest.py(임시 DB·가짜 Gemini·로그인 클라이언트), test_api.py, test_parser.py, test_auth.py
├── .github/workflows/
│   └── pylint.yml          # push/PR 시 Pylint + pytest 실행
├── .env                    # API 키 (커밋 금지, 로컬 전용)
├── .env.example            # 키 형식 템플릿 (커밋 대상)
├── .gitignore
├── static/
│   ├── css/style.css
│   └── js/
│       ├── main.js         # 탭 전환 및 앱 초기화
│       ├── api.js          # Flask API 호출 모듈 (공통 request 헬퍼)
│       ├── auth.js         # 로그인·회원가입 화면, 로그아웃
│       ├── dashboard.js    # Chart.js 시각화
│       └── utils.js        # 공통 유틸
└── templates/
    └── index.html          # 단일 페이지
```

- `api.js`가 `export`를 사용하므로 `index.html`에서 `<script type="module">`로 로드한다.
  진입점은 `main.js` 하나만 넣는다 (나머지는 main.js가 import한다).
- **VS Code는 프로젝트 루트 폴더 하나만** 연다 (중첩 `.git` 재발 방지).

## 6. 화면 구성 (4탭)

| 탭 | 이름 | 주요 기능 |
|---|---|---|
| 0 | 로그인·회원가입 | 탭 바깥의 별도 화면. 로그인 전에는 앱(4탭)이 보이지 않는다. 헤더에 아이디 + 로그아웃 |
| 1 | 문자 입력 | SMS 입력 → Gemini 파싱 요청 → 결과 미리보기(카테고리 수정 가능) → 저장하기 |
| 2 | 대시보드 | 카테고리별 도넛 + 일별 누적 라인 + 최근 6개월 추이 막대 (Chart.js) |
| 3 | 내역 조회 | 전체 거래 테이블 (월·카테고리 필터, 상점명 검색, 건수). 행을 누르면 상세(시간·카드사)·삭제 |
| 4 | AI 분석 | 또래 그룹 비교(연령대·소득 드롭다운) + Gemini 맞춤 조언 |

> 탭1에서 **"분석하기"는 저장하지 않는다.** 미리보기를 확인한 뒤 "저장하기"를 눌러야 DB에 들어간다.

## 7. 코딩 컨벤션

### JavaScript
- 변수/함수 `camelCase`, 상수 `UPPER_SNAKE_CASE`
- `async/await` 사용, `.then()` 체이닝 지양
- **모든 `fetch`는 `try/catch` 필수** — `api.js`의 공통 `request()` 헬퍼가 담당한다
- 실패 시 **응답 본문의 `error` 메시지를 살린다.** `HTTP ${status}`만 던지면 백엔드가 보낸 원인이 사라진다
- DOM 선택은 `querySelector` / `querySelectorAll` (`getElementById` 지양)
- 이벤트는 `addEventListener` (인라인 `onclick` 지양)
- 기능별 파일 분리, 전역 오염 최소화

```js
// 올바른 예시 — api.js의 공통 헬퍼를 통해 호출한다
export async function getTransactions({ month, category, search } = {}) {
  const params = new URLSearchParams();
  if (month)    params.set('month', month);
  if (category) params.set('category', category);
  if (search)   params.set('search', search);

  return request(`/transactions?${params}`, {}, '거래 내역 조회');
}
```

### CSS
- BEM 느슨하게 (`블록__요소--수정자`)
- 레이아웃 단위 `rem` / `%` / `fr`, 보더·그림자는 `px`
- 색상은 CSS 변수로 최상단에 정의
- 모바일 퍼스트, 브레이크포인트 `max-width: 768px`

```css
:root {
  --color-primary: #4F46E5;
  --color-accent: #10B981;
  --color-bg: #F9FAFB;
  --color-text: #111827;
  --radius-md: 8px;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.1);
}
```

### HTML
- 시맨틱 태그 (`<main>`, `<section>`, `<header>`, `<nav>`)
- JS 연결은 `data-*` 속성 (예: `data-tab="dashboard"`)
- 필요한 곳에 `aria-label`, `role` 추가

### Python (Flask)
- 함수/변수 `snake_case`, 상수 `UPPER_SNAKE_CASE`
- **에러 응답은 항상** `{"success": false, "error": "메시지"}` 형태로 통일
- **상태코드를 구분한다**: 클라이언트 입력 문제는 `400`, 서버/DB 문제는 `500`, Gemini 등 외부 API 실패는 `502`
- 환경변수는 하드코딩 금지, `os.getenv()`로만 읽기
- Gemini 호출은 **`gemini_parser` 모듈을 통해서만** 한다 (모델명이 갈라지지 않게)

```python
@app.route('/api/parse', methods=['POST'])
def parse_sms():
    try:
        data = request.get_json(silent=True)
        if not data or not data.get('sms'):
            return jsonify({"success": False, "error": "sms 필드가 없습니다"}), 400

        result = gemini_parser.parse_sms(data['sms'])
        if not result['success']:
            status = result.pop('status', 500)
            return jsonify({"success": False, "error": result['error']}), status

        return jsonify({"success": True, "data": result['data']})

    except Exception as e:
        return error_response("문자를 분석하지 못했습니다", 500, e)
```

- **내부 예외 메시지를 그대로 응답에 넣지 않는다.** `error_response()`가 `FLASK_DEBUG`가 켜졌을 때만
  상세 내용을 붙이고, 평소에는 서버 로그에만 남긴다.

## 8. API 규칙 · 스키마

프론트의 Flask 통신은 **`static/js/api.js`에 집중**한다.

```js
// 상대경로를 쓴다. localhost를 하드코딩하면 다른 기기에서 접속할 때 전부 실패한다.
const API_BASE_URL = '/api';

export async function signup({ username, password, age_group, income_group }) { ... }
export async function login({ username, password }) { ... }
export async function logout() { ... }
export async function getMe() { ... }
export async function parseSMS(smsText) { ... }
export async function saveTransaction(data) { ... }
export async function deleteTransaction(id) { ... }
export async function getTransactions(params) { ... }
export async function getDashboardStats(month) { ... }
export async function getAIAnalysis(ageGroup, incomeGroup, month) { ... }
```

> ⚠️ 아래는 팀이 합의한 스키마다. **임의 변경 금지.** 변경이 필요하면 먼저 제안하고 확인을 받은 뒤 이 문서를 갱신한다.

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/api/parse` | SMS 파싱 **(미리보기 전용, 저장하지 않음)** |
| POST | `/api/transactions` | 거래 저장 |
| DELETE | `/api/transactions/<id>` | 거래 삭제 (2026-10-16 팀 합의로 추가) |
| GET | `/api/transactions?month=&category=&search=` | 거래 내역 (월·카테고리·상점명 검색) |
| GET | `/api/stats?month=YYYY-MM` | 대시보드 통계 |
| GET | `/api/analysis?month=&age_group=&income_group=` | AI 분석 + 또래 비교 |
| POST | `/api/auth/signup` | 회원가입 후 바로 로그인 (2026-10-31 팀 합의로 추가) |
| POST | `/api/auth/login` | 로그인 |
| POST | `/api/auth/logout` | 로그아웃 |
| GET | `/api/auth/me` | 로그인한 사용자 정보 |

**인증 규칙 (2026-10-31)**
- `/api/auth/*`와 `/`를 뺀 **모든 API는 로그인이 필요하다** (`app.login_required`). 비로그인은 `401 "로그인이 필요해요"`.
  `/api/parse`도 막는다 (비로그인 사용자가 Gemini 무료 한도를 쓰지 않게)
- 세션 쿠키(`HttpOnly`, `SameSite=Lax`, 30일). 모든 조회·삭제는 `g.user['id']`로 범위를 좁힌다.
  **남의 거래 id로 삭제하면 없는 id와 똑같이 `404`** (있는지조차 알려주지 않는다)
- `api.js`의 `request()`는 `/auth/` 밖에서 `401`을 받으면 `auth:required` 이벤트를 보내고, `main.js`가 로그인 화면으로 돌린다
- 사용자 정보 응답은 `{username, age_group, income_group}`만. **`password_hash`와 `id`는 절대 내보내지 않는다**

**`POST /api/auth/signup`** — 가입하면 바로 로그인된다.
아이디는 영문 소문자·숫자·`_` 3~20자, 비밀번호 8자 이상, `age_group`·`income_group`은 9절 표의 값. 어기면 `400`, 중복 아이디 `409`.
```json
// Request
{ "username": "doyeon", "password": "********", "age_group": "20대초반", "income_group": "mid-low" }
// Response
{ "success": true, "data": { "username": "doyeon", "age_group": "20대초반", "income_group": "mid-low" } }
```

**`POST /api/auth/login`** — `{username, password}`. 아이디는 대소문자를 구분하지 않는다.
틀리면 아이디가 없든 비밀번호가 틀리든 같은 `401 "아이디 또는 비밀번호가 맞지 않아요"`. 응답 형식은 signup과 같다.

**`GET /api/auth/me`** — 로그인 상태면 signup 응답과 같은 `data`, 아니면 `401`. 프론트는 시작할 때 이것으로 화면을 고른다.

**`POST /api/parse`** — 파싱만 하고 저장하지 않는다. 응답에 `id`가 없다.
`sms`가 문자열이 아니거나 비었으면 `400`, **1,000자를 넘으면 `400`** (`app.MAX_SMS_LENGTH`, Gemini 호출 전에 막는다).
```json
// Request
{ "sms": "[신한카드] 승인 12,000원 스타벅스 07/14 14:32 잔여한도 2,450,000원" }

// Response
{
  "success": true,
  "data": {
    "amount": 12000, "store": "스타벅스", "category": "cafe",
    "date": "2026-07-14", "time": "14:32", "card": "신한카드"
  }
}
```

**`POST /api/transactions`** — `/api/parse` 응답의 `data`를 그대로 보내면 된다.
`amount / store / category / date / time`은 필수, `card`는 선택. 누락 시 `400`.
```json
{ "success": true, "data": { "id": 12 } }
```

**`DELETE /api/transactions/<id>`** — 거래 1건 삭제. 되돌릴 수 없다.
성공하면 지운 `id`를 돌려준다. 없는 id면 `404 "해당 거래를 찾을 수 없습니다"`,
숫자가 아닌 id는 라우트에 걸리지 않아 `404 "없는 API 경로입니다"`.
```json
{ "success": true, "data": { "id": 12 } }
```

**`GET /api/transactions`**
쿼리 파라미터: `month`(`YYYY-MM`), `category`(7개 key 중 하나), `search`(상점명 부분 일치). 전부 선택.
```json
{
  "success": true,
  "data": [
    { "id": 1, "amount": 12000, "store": "스타벅스", "category": "cafe",
      "date": "2026-07-14", "time": "14:32", "card": "신한카드" }
  ],
  "total": 1
}
```

**`GET /api/stats`**
```json
{
  "success": true,
  "data": {
    "total_amount": 352000,
    "by_category": { "food": 120000, "cafe": 45000, "transport": 38000,
                     "shopping": 89000, "medical": 0, "leisure": 60000, "etc": 0 },
    "by_date": [ { "date": "2026-07-01", "amount": 15000 } ]
  }
}
```
`by_category`는 항상 7개 key가 모두 들어있다 (없으면 0).

**`GET /api/analysis`**
쿼리 파라미터: `month`(기본값 이번 달), `age_group`(기본값 `20대초반`), `income_group`(기본값 `mid-low`).
**연령대 값은 한글이므로 프론트에서 `URLSearchParams`로 인코딩해 보낸다.**
```json
{
  "success": true,
  "data": {
    "user_total": 352000,
    "peer_average": 298000,
    "peer_group": "20대초반 / mid-low",
    "has_peer_data": true,
    "by_category": {
      "food": { "user": 120000, "peer_avg": 95000 },
      "cafe": { "user": 45000, "peer_avg": 32000 }
    },
    "advice": "이번 달 카페 지출이 또래 평균보다 40% 높습니다. ..."
  }
}
```
- `peer_average`는 해당 그룹의 **전 카테고리 합계**다.
- `has_peer_data`가 `false`면 그 그룹의 시드 데이터가 없다는 뜻이다. 프론트는 `0원` 대신 **"데이터 없음"** 으로 표시한다.
- `peer_group`은 반드시 화면에 표시한다. 표시하지 않으면 드롭다운이 실제로 반영되는지 눈으로 확인할 수 없다.

**`installment`(할부)는 스키마에서 제외한다.** DB 컬럼도 파싱 대상도 아니다.

## 9. DB 스키마

**컬럼명 규칙:** API 응답 JSON의 key와 DB 컬럼명을 **1:1로 일치**시킨다. 임의 변경 금지.

```sql
-- users (2026-10-31 추가)
CREATE TABLE users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT    NOT NULL,          -- werkzeug generate_password_hash. 평문 저장 금지
  age_group     TEXT    NOT NULL,
  income_group  TEXT    NOT NULL,
  created_at    TEXT    DEFAULT (datetime('now', 'localtime'))
);

-- transactions
CREATE TABLE transactions (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  amount     INTEGER NOT NULL,
  store      TEXT    NOT NULL,
  category   TEXT    NOT NULL,
  date       TEXT    NOT NULL,
  time       TEXT    NOT NULL,
  card       TEXT,
  created_at TEXT    DEFAULT (datetime('now', 'localtime')),
  user_id    INTEGER REFERENCES users(id)  -- 2026-10-31 추가. API 응답에는 넣지 않는다
);

-- peer_averages (연령대 × 소득 구간 × 카테고리)
CREATE TABLE peer_averages (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  age_group    TEXT    NOT NULL,
  income_group TEXT    NOT NULL,
  category     TEXT    NOT NULL,
  avg_amount   INTEGER NOT NULL,
  UNIQUE(age_group, income_group, category)
);
```

시드 규모: **224행 = 8 연령대 × 4 소득 구간 × 7 카테고리**

| 구분 | 값 |
|---|---|
| `age_group` | `10대` `20대초반` `20대후반` `30대초반` `30대후반` `40대` `50대` `60대이상` |
| `income_group` | `low` `mid-low` `mid-high` `high` |
| `category` | 아래 10절의 7개 key |

- 시드 데이터는 `seed.py`를 실행해 삽입한다 (하드코딩·외부 API 사용 금지). 값 수정은 코드 로직이 아닌 시드 데이터만 바꾸고 재실행한다.
- `*.db`는 `.gitignore` 대상이므로 **클론 후 DB 재생성이 필요**하다: `python app.py`로 한 번 띄워 테이블을 만든 뒤(`init_db()`가 import 시 실행됨) `python seed.py`.
- `user_id`는 내부 소유자 표시라 API JSON key와 1:1 규칙의 예외다 (응답에 내보내지 않는다).
- `_migrate_transactions_user_id`는 로그인 도입 전 DB에 `user_id` 컬럼만 **추가**한다 (데이터 삭제 없음).
  기존 거래는 `NULL`로 남아 있다가 **첫 회원가입 때 그 계정으로 넘어간다** (`create_user()`). 두 번째 가입자부터는 빈 가계부로 시작한다.
- `database.py`의 거래·통계 함수는 **첫 인자가 `user_id`**다. 새 조회를 만들 때 `user_id = ?` 조건을 빠뜨리지 않는다.
- `database.py`의 `_migrate_peer_averages`는 **구스키마를 만나면 테이블을 DROP한다.** 마이그레이션 후에는 `seed.py`를 반드시 다시 실행해야 한다. 안 하면 또래 비교가 조용히 전부 0이 된다.

## 10. 소비 카테고리 (7개 고정)

| 카테고리 | key | 아이콘 | 색상 |
|---|---|---|---|
| 식비 | `food` | 🍽️ | `#FF6B6B` |
| 카페 | `cafe` | ☕ | `#C49A6C` |
| 교통 | `transport` | 🚌 | `#4ECDC4` |
| 쇼핑 | `shopping` | 🛍️ | `#9B59B6` |
| 의료 | `medical` | 💊 | `#2ECC71` |
| 문화/여가 | `leisure` | 🎬 | `#F39C12` |
| 기타 | `etc` | 📌 | `#95A5A6` |

- Chart.js 색상 배열도 **위 순서 그대로** 유지한다 (`utils.js`의 `CATEGORY_MAP`에서 파생된다).
- **7개 외의 값이 저장되면 통계에서 조용히 누락된다.** `gemini_parser`가 화이트리스트로 검증해 `etc`로 보정한다.

## 11. Gemini 연동

- Gemini 호출은 **백엔드(Flask)에서만**, 그중에서도 **`gemini_parser` 모듈을 통해서만** 수행한다.
- SDK: `google-genai`, 모델: **`gemini_parser.MODEL_NAME`** (현재 `gemini-3.8-flash`), 막히면 `FALLBACK_MODEL_NAMES` 순서로 넘어간다.
  키는 `os.getenv("GEMINI_API_KEY")`.
- 클라이언트는 **지연 생성**한다. 모듈 최상단에서 만들면 키가 없을 때 `import` 단계에서 서버가 아예 뜨지 않는다.
- SMS → JSON 변환은 아래 프롬프트를 **고정**으로 사용한다.

```
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
```

**파싱 규칙**
- 프롬프트에 JSON 중괄호가 있으므로 `str.format()`은 `KeyError`를 낸다 → `.replace("{sms_text}", sms)` 사용
- **기준 연도를 반드시 넣는다.** 없으면 `07/14` 같은 문자를 과거 연도로 추론해 월별 통계에서 누락된다
- 응답은 `json.loads()`로 파싱 (코드펜스 ```` ```json ```` 가 섞이면 제거 후 파싱)
- `amount`는 `'12,000'`/`'12000원'` 형태로 올 수 있으므로 숫자만 추출해 `int` 변환
- `category`가 7개 고정값이 아니면 `"etc"`로 보정
- 필수 필드(`amount` `store` `category` `date` `time`)가 없으면 400으로 응답

## 12. 보안 · `.env`

**핵심 원칙**
- `.env`는 **절대 커밋하지 않는다.** API 키를 JS 코드에 하드코딩하지 않는다.
- 흐름: `[JS fetch()] → /api/parse (Flask) → Gemini API` (`GEMINI_API_KEY`는 Flask에서만 사용)
- **Claude는 코드 작성 시 API 키가 JS 파일이나 커밋 대상 파일에 들어가지 않도록 능동적으로 경고한다.** 사용자에게 실제 키 값을 채팅에 붙여넣으라고 요청하지 않으며, `.env` 파일은 사용자가 직접 만든다.

| 파일 | GitHub | 용도 |
|---|---|---|
| `.env` | ❌ 금지 | 실제 API 키 |
| `.env.example` | ✅ | 키 형식 템플릿 |
| `.gitignore` | ✅ | `.env` 커밋 차단 |

```
# .gitignore 필수 내용
.env
__pycache__/
*.pyc
*.db
venv/
.DS_Store
```

**환경변수**

| 이름 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `GEMINI_API_KEY` | ✅ | — | Google AI Studio 발급 키 |
| `DB_PATH` | ❌ | `database.db` | SQLite 경로 |
| `SECRET_KEY` | 권장 | 실행마다 임의 생성 | 로그인 세션 서명 키. 없으면 **서버를 재시작할 때마다 모두 로그아웃**된다. `python -c "import secrets; print(secrets.token_hex(32))"`로 만든다. 커밋 금지 |
| `HOST` | ❌ | `0.0.0.0` | 바인딩 주소. `127.0.0.1`로 두면 이 컴퓨터에서만 접속 가능 |
| `PORT` | ❌ | `5000` | 포트 |
| `FLASK_DEBUG` | ❌ | 꺼짐 | `1`/`true`면 디버그 모드. **외부 노출 상태에서는 절대 켜지 않는다** |

**LAN 공개 시 주의**
- 서버가 `0.0.0.0`에 열리므로 **같은 와이파이의 누구나** 접속할 수 있다. 공용 와이파이에서는 주의한다.
- `FLASK_DEBUG=1`로 외부에 노출하면 Werkzeug 디버거를 통해 **임의 코드 실행**이 가능하다. 기본값(꺼짐)을 유지한다.
- 프론트가 상대경로(`/api`)를 쓰므로 동일 출처다. 전체 허용 CORS는 켜지 않는다.

**주의**
- `.gitignore`는 첫 커밋 **이전에** 생성한다. 커밋 전 `git status`로 `.env`가 목록에 없는지 확인한다.
- 이미 `.env`를 커밋했다면 **API 키를 즉시 재발급**한다.
- `.env`는 git이 추적하지 않으므로 **re-clone 시 수동으로 백업·재생성**해야 한다.

## 13. Chart.js 지침

- Chart 인스턴스는 재렌더링 시 **반드시 `.destroy()` 후 재생성**
- 색상 팔레트는 CSS 변수·카테고리 색상과 일관되게
- 옵션: `responsive: true, maintainAspectRatio: false`
- 도넛/파이: 카테고리별 비율 / 막대: 월별 추이 / 라인: 일별 누적

## 14. GitHub 협업 규칙

- 브랜치: `main`(배포), `dev`(개발), `feat/기능명`(기능 개발). 현재 작업은 `dev`
- **`dev`가 `main`보다 뒤처지지 않게 관리한다.** 2026-09-19에 두 브랜치가 갈라져 `main`에만 기능 작업이 쌓여 있었고, `main`을 `dev`로 머지해 정리했다.
- 커밋 메시지: `[feat] SMS 입력 UI 구현` / `[fix] 차트 리렌더링 오류 수정` / `[style] 대시보드 레이아웃 조정`
- PR 전 `dev`에서 충돌 해결 후 머지

## 15. 디자인 방향

- **다크 프리미엄** 핀테크 스타일 (2026-10-31 라이트에서 전환). 신뢰감·빠른 파악이 목표인 건 그대로
- 배경 `#0B0D14`, 카드 `#151823` + 1px 반투명 테두리 (어두운 화면이라 그림자 대신 테두리로 층을 나눈다)
- 인디고는 역할별로 둘: 글자·강조·차트는 `--color-primary` `#818CF8`, 버튼 배경은 `--color-primary-strong` `#4F46E5`
  (`#4F46E5`를 어두운 배경 위 글자로 쓰면 대비가 부족하다). 포인트 에메랄드 `#34D399`
- 대시보드 "이번 달 총 지출"만 인디고 그라데이션 히어로 카드 (`.stat-card--hero`). 화면당 큰 숫자는 하나
- 폰트: **Pretendard Variable** (jsDelivr v1.3.9, SRI 고정. `.min.css`는 즉석 압축이라 SRI가 깨질 수 있어 원본 `.css`)
- UI 아이콘은 인라인 SVG(`currentColor`). 이모지는 카테고리(`CATEGORY_MAP`)에만 쓴다
- **색은 전부 `style.css` `:root` 토큰.** 차트도 `dashboard.js`의 `cssVar()`로 토큰을 읽는다 (hex 하드코딩 금지)
- 카드 UI: `border-radius: 16px`(`--radius-lg`)
- 발표 프로젝터에서는 어두운 화면이 흐리게 보일 수 있다. 발표 전에 실제 화면으로 확인한다
- **로딩 스피너 · 성공 토스트 · 에러 메시지는 항상 구현**
- 에러 토스트에는 **백엔드가 보낸 실제 원인 메시지**를 띄운다

## 16. 파싱 대상 SMS 예시 (UI 안내문구·플레이스홀더 참고)

```
[신한카드] 승인 12,000원 스타벅스 07/14 14:32 잔여한도 2,450,000원
[KB국민카드] 홍길동님 12,000원(일시불) 07/14 14:32 스타벅스 승인완료
삼성카드(1234) 12,000원 스타벅스 승인완료 07/14 14:32
[현대카드] 07/14 14:32 스타벅스 12,000원 승인 (일시불)
```

입력창 플레이스홀더: `[신한카드] 승인 12,000원 스타벅스 07/14 14:32 잔여한도 2,450,000원`

## 17. Claude 응답 방식

**코드 요청 시**
1. 변경/추가할 **파일명을 먼저** 명시하고, 코드 블록 상단에 경로 주석 표기 (`// static/js/api.js`)
2. 사용자는 **바로 복붙해서 쓸 수 있는 완성된 코드**를 선호한다 → 함수·블록 단위로 **완결된 코드**를 주고, "어디에 넣는지"는 한 줄로 명확히 알려준다. 스니펫 조각만 던져놓고 사용자가 끼워 맞추게 하지 않는다.
3. 파일 전체 재작성은 구조적으로 필요할 때만 하고, 그 경우 **이유를 먼저 설명**한다 (설명 없이 통째로 갈아엎지 않는다).
4. 변경 이유는 1~2줄로 간략히.

**설명 요청 시:** 결론 먼저, 이유는 간략하게, 불필요한 배경 생략. **한국어로 응답**(기술 용어·변수명은 영어 유지).

**여러 방법이 있을 때:** 권장안 1개를 먼저 제시하고 대안은 "다른 방법:"으로 구분.

**디버깅 시:** 에러 메시지/스크린샷/상황 설명 → 원인 분석 → 수정 코드 순서. 사용자는 구조가 꼬이면 **처음부터 깔끔하게 다시 하는 방식**(예: re-clone)을 선호한다.

## 18. Claude가 하지 말아야 할 것

- 요청하지 않은 기능을 임의로 추가하지 않는다
- 설명 없이 전체 파일을 새로 작성하지 않는다
- `.env`나 API 키 관련 코드를 프론트엔드 JS에 포함시키지 않는다
- 프론트-백엔드 **API 스키마를 임의로 변경하지 않는다** — 필요하면 먼저 제안하고 확인받는다
- DB 컬럼명과 API JSON key를 서로 다르게 만들지 않는다
- 모델명을 `gemini_parser`(`MODEL_NAME`·`FALLBACK_MODEL_NAMES`) 밖에 하드코딩하지 않는다

## 19. 트러블슈팅 메모 (겪었던 문제)

| 문제 | 해결 |
|---|---|
| `POST /api/parse` 500 | **모델 `gemini-2.5-flash`가 신규 사용자에게 404로 차단됨.** `gemini-3.8-flash`로 교체. 서버 터미널 traceback을 먼저 볼 것 |
| `pip install -r requirements.txt` 실패 | PowerShell `pip freeze >`가 **UTF-16**으로 저장. UTF-8로 재작성 |
| 키가 없으면 서버가 아예 안 뜸 | `genai.Client()`를 모듈 최상단에서 생성하면 import가 터진다 → **지연 생성**으로 변경 |
| 거래가 두 번 저장됨 | `/api/parse`와 `/api/transactions` 양쪽에서 insert하고 있었음 → 저장은 후자 하나로 |
| 필터·검색이 동작 안 함 | 프론트는 파라미터를 보내는데 백엔드가 안 읽고 있었음 |
| 드롭다운이 반영 안 됨 | `api.js`가 파라미터를 쿼리스트링에 안 붙이고 있었음. `peer_group`을 화면에 표시해 재발 방지 |
| 연도 없는 문자가 과거 연도로 저장 | 프롬프트에 **기준 연도** 추가 |
| 토스트에 `HTTP 500`만 표시 | `api.js`가 응답 본문을 안 읽고 throw → 공통 `request()`에서 `error` 메시지 사용 |
| 중첩 `.git` 폴더로 git이 전체 파일을 삭제된 것으로 표시 | 깨끗하게 re-clone, 이후 루트 폴더 하나만 VS Code로 열기 |
| re-clone 후 Gemini 호출 실패 | `.env`는 git 미추적 → 수동 재생성 (키 재입력) |
| 서버 로그에 `python-dotenv could not parse statement starting at line 1` | `.env` 변수명 오타(예: `GEMINI_API KEY`처럼 공백). 줄 전체가 무시돼 키가 안 읽힌다. `GEMINI_API_KEY=값` 형태로, `=` 앞뒤에 공백 없이 쓴다 |
| PowerShell에서 venv 활성화 차단 | `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| Gemini 503 UNAVAILABLE | 과부하. 같은 모델로 한 번 더 시도하고, 안 되면 보조 모델로 넘어간다 |
| Gemini 429 RESOURCE_EXHAUSTED (`limit: 5`) | 무료 등급 **모델당 분당 5회** 초과. 실패한 재시도도 횟수에 들어간다 → 같은 모델 재시도 대신 보조 모델로 전환. 측정할 때는 호출 사이에 간격을 둔다 |
| `[SSL: UNEXPECTED_EOF_WHILE_READING]`가 토스트에 그대로 뜸 | 연결이 중간에 끊긴 네트워크 오류. 예전엔 상태코드가 없어 재시도 없이 바로 실패하고 원본 문구가 노출됐다 → `NETWORK_ERRORS`로 재시도 + 안내 문구로 교체 |
| 휴대폰에서 LAN 주소로 접속이 안 됨 | Windows 방화벽 인바운드 허용 필요. 관리자 PowerShell에서 아래 명령 실행 |
| 다른 기기에서 화면은 뜨는데 데이터가 안 나옴 | `api.js`가 `localhost`를 하드코딩하면 발생. 상대경로(`/api`)를 쓴다 |
| 문자열 금액이 저장돼 통계 총액이 소수점으로 깨짐 | SQLite는 타입이 느슨하다. 저장 전 `to_int_amount()`로 검증 |
| `-500`이 `500`으로 저장됨 | 숫자만 추출하면 음수 부호가 사라진다. `to_int_amount()`가 부호를 보존한다 |

### 방화벽 허용 (LAN 접속용, 최초 1회)

다른 기기에서 접속하려면 **관리자 권한 PowerShell**에서 실행한다:

```powershell
New-NetFirewallRule -DisplayName "SMS Budget Tracker (5000)" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow -Profile Private
```

- `-Profile Private`이므로 집·학교처럼 "개인 네트워크"로 설정된 곳에서만 열린다. 공용 와이파이에서는 열리지 않는다.
- 되돌리려면: `Remove-NetFirewallRule -DisplayName "SMS Budget Tracker (5000)"`
