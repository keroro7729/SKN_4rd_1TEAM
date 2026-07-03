# WOOK'S CODING

AI 기반 코딩 학습 웹 애플리케이션 (SKN 4차 프로젝트)

문제를 풀고, 코드 실행 결과를 확인하며, **AI 단계별 힌트**와 **오답노트 RAG**를 통해
반복 실수와 취약 개념을 추적하는 학습 서비스입니다.

## 기술 스택
- **Web/인증/권한/CRUD:** Django 5 (Template · PostgreSQL)
- **AI/RAG:** FastAPI + LangGraph
- **저장소:** PostgreSQL(원본) · ChromaDB(벡터 인덱스)
- **코드 실행:** Docker Worker 격리 실행 (Python 3.11)
- **배포:** AWS EC2 · Docker Compose · Nginx · Gunicorn

## 컴포넌트 구조 (모노레포)

```
00_skn_4rd/
├─ .env                 # 통합 환경변수 (모든 컴포넌트 공유, git 제외)
├─ .env.example         # 환경변수 템플릿
├─ docker-compose.yml   # 전체 오케스트레이션
├─ django/              # [웹] Django + Gunicorn      (venv 개별)
├─ fastapi_app/         # [AI/RAG] FastAPI + LangGraph (venv 개별)
├─ worker/              # [실행] 코드 실행 Worker      (venv 개별)
├─ nginx/               # [프록시] Nginx reverse proxy
└─ llm_wiki/            # 설계 문서
```

- **`.env`는 루트 하나로 통합 관리**, **`.venv`는 컴포넌트별 개별 관리**.
- 자세한 구조/관리 규칙: `llm_wiki/3. WOOKS_CODING_프로젝트_구조_및_환경관리_v0.1.md`

## 진행 현황
- [x] STEP-01 Django 골격 · `accounts.CustomUser` · 로그인/관리자 화면
- [x] fastapi_app / worker / nginx **스캐폴딩** (동작 스텁 + 구조)
- [ ] STEP-02~ 데이터 모델 · 실제 AI/RAG · 코드 실행 로직

---

## 실행 방법 (A) — Docker Compose (권장, 전체 한 번에)

Nginx·Django·FastAPI·Worker·PostgreSQL·ChromaDB를 한 번에 기동합니다.

```bash
# 1. 환경변수 준비
cp .env.example .env          # (Windows: copy .env.example .env)
#   .env 의 POSTGRES_* / OPENAI_API_KEY / INTERNAL_API_KEY 값 채우기

# 2. 전체 빌드 & 기동
docker compose up --build

# (백그라운드 실행: docker compose up --build -d)
# (종료: docker compose down   /  DB까지 삭제: docker compose down -v)
```

- 서비스 접속: **http://localhost/** (Nginx → Django)
- Django 관리자: http://localhost/admin/
- 관리자 계정 생성: `docker compose exec django python manage.py createsuperuser`
- FastAPI/ChromaDB/Worker/PostgreSQL은 **내부 네트워크 전용**(외부 미노출).

---

## 실행 방법 (B) — 로컬 개발 (컴포넌트별 개별 실행)

컴포넌트마다 **독립 venv**를 사용합니다. PostgreSQL·ChromaDB는 별도로 띄워야 합니다.

> 아래는 Windows PowerShell 기준. (Git Bash/macOS/Linux는 `source .venv/bin/activate`)

### 0) 공통: 환경변수
```powershell
copy .env.example .env
#  .env 의 POSTGRES_* 값을 로컬 DB에 맞게 수정
```

### 1) Django (웹) — 포트 8000
```powershell
cd django
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver          # http://127.0.0.1:8000/
```
- 홈 `/` · 로그인 `/accounts/login/` · 회원가입 `/accounts/signup/` · 관리자 `/admin/`

### 2) FastAPI (AI/RAG) — 포트 8001
```powershell
cd fastapi_app
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

uvicorn main:app --reload --port 8001
```
- 헬스체크: http://127.0.0.1:8001/ai/health
- API 문서(Swagger): http://127.0.0.1:8001/docs
- 내부 API는 `X-Internal-API-Key` 헤더 필요 (`.env`의 `INTERNAL_API_KEY`).

### 3) Worker (코드 실행) — 상시 폴링
```powershell
cd worker
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

python main.py
```
- `jobs` 테이블을 polling 합니다. **STEP-02(데이터 모델) 이후** 정상 동작합니다.

### 4) Nginx
로컬 개별 실행에서는 보통 생략하고 Django(8000)로 직접 접속합니다.
Nginx까지 확인하려면 위 **실행 방법 (A) Docker Compose**를 사용하세요.

---

## 참고
- **로컬 개발 Python은 3.13**: `psycopg2-binary`(3.13 휠 없음) 대신 **psycopg3**를 사용합니다.
- **`.env` 빈 값 주의**: 키만 있고 값이 비면 코드 기본값이 아니라 빈 문자열이 들어갑니다. 실행 전 값 채우기.
- 설계 문서: `llm_wiki/` (구현방향 v0.3 · 서비스기획서 v0.3 · 코드생성 지시문 v0.7 · 구조/환경관리 v0.1)
