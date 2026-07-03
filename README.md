# WOOK'S CODING

AI 기반 코딩 학습 웹 애플리케이션 (SKN 4차 프로젝트)

문제를 풀고, 코드 실행 결과를 확인하며, **AI 단계별 힌트**와 **오답노트 RAG**를 통해
반복 실수와 취약 개념을 추적하는 학습 서비스입니다.

## 기술 스택
- **Web/인증/권한/CRUD:** Django 5 (Template · PostgreSQL)
- **AI/RAG:** FastAPI + LangGraph (이후 STEP)
- **저장소:** PostgreSQL(원본) · ChromaDB(벡터 인덱스)
- **코드 실행:** Docker Worker 격리 실행
- **배포:** AWS EC2 · Docker Compose · Nginx · Gunicorn

## 현재 진행 (STEP-01)
- [x] Django 프로젝트 골격 (`config/`)
- [x] `accounts.CustomUser` 모델 (role · point · is_subscribed)
- [x] 회원가입 / 로그인 / 로그아웃 화면
- [x] Django 관리자 화면 (`/admin/`) — CustomUser 등록

이후 STEP-02(데이터 모델)부터 STEP-10(Seed/Test/배포)까지 순차 진행합니다.

## 로컬 실행 방법

> 문서 규칙상 DB는 **PostgreSQL 고정**입니다. 먼저 PostgreSQL이 실행 중이어야 합니다.

```bash
# 1. 가상환경 + 의존성
python -m venv .venv
.venv\Scripts\activate        # (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt

# 2. 환경변수
copy .env.example .env         # (macOS/Linux: cp .env.example .env)
#  .env 안의 POSTGRES_* 값을 로컬 DB에 맞게 수정

# 3. PostgreSQL DB 준비 (예시)
#  psql -U postgres -c "CREATE DATABASE wooks_coding;"
#  psql -U postgres -c "CREATE USER wooks WITH PASSWORD 'wooks1234';"
#  psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE wooks_coding TO wooks;"

# 4. 마이그레이션 + 관리자 계정
python manage.py makemigrations accounts
python manage.py migrate
python manage.py createsuperuser

# 5. 실행
python manage.py runserver
```

- 홈: http://127.0.0.1:8000/
- 로그인: http://127.0.0.1:8000/accounts/login/
- 관리자: http://127.0.0.1:8000/admin/

## 프로젝트 문서
설계 문서는 `llm_wiki/` 폴더의 워드 문서(구현방향 v0.3 · 서비스기획서 v0.3 · 코드생성 지시문 v0.7)를 기준으로 합니다.
