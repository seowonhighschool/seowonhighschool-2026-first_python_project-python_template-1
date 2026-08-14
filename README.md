# Life of Booster

초보자도 실행할 수 있는 Streamlit 기반 습관 관리 MVP입니다.

## 1. Python 설치
Python 3.11 이상을 권장합니다.

## 2. VS Code에서 폴더 열기
이 폴더를 VS Code로 엽니다.

## 3. 가상환경 만들기

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

PowerShell에서 실행 정책 오류가 나면:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

그 다음 다시:

```powershell
.venv\Scripts\Activate.ps1
```

## 4. 패키지 설치

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 5. 실행

```powershell
streamlit run app.py
```

브라우저가 열리면 Life of Booster가 실행됩니다.

## 6. OpenAI AI 추천 사용

기본 앱은 API 키 없이도 실행됩니다.

AI 추천 기능을 사용하려면:

1. `.env.example`을 복사해서 `.env`로 이름 변경
2. `.env`에 본인의 OpenAI API 키 입력
3. 다시 `streamlit run app.py`

API 키는 GitHub 등에 올리지 마세요.

## 7. 현재 MVP 구조

- app.py: 화면 + 데이터 처리 + 추천 로직
- life_of_booster.db: 실행 시 자동 생성되는 SQLite DB
- requirements.txt: 필요한 Python 패키지
- .env: API 키 등 비밀 설정

## 8. 최종 서비스로 발전시키려면

현재 버전은 '프로젝트 시연용 MVP'입니다.

다음 단계에서는:
- 회원가입/로그인
- 사용자별 DB
- 실제 건강 데이터 API
- 미션/퀘스트
- 보상/배지
- 주간 리포트
- AI 추천
- 모바일 앱 또는 웹 배포

를 추가하면 됩니다.
