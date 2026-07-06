# CLAUDE.md

WOOK'S CODING — AI 기반 코딩 학습 웹앱 (SKN 4차 프로젝트). 문제 풀이 · 코드 실행 · **AI 단계별 힌트** · **오답노트 RAG**.

## ⚠️ 이 저장소에서 가장 먼저 알아야 할 것

1. **STEP 단위 순차 빌드 — 전체를 한 번에 생성하지 말 것.**
   코드생성 지시문 v0.7 규칙상 STEP-01~STEP-10을 순서대로 구현한다.
   - STEP-01(골격) · STEP-02(데이터 모델 §7) · STEP-03(화면/URL/View/권한) · STEP-04(코드실행 Job/Worker + 채점) **완료**
   - fastapi_app 은 **스캐폴딩(동작 스텁)만** 존재
   - 다음: STEP-05(FastAPI 기본 구조) → STEP-06(AI/RAG) → STEP-07(Fetch 연동)
   - 새 기능은 해당 STEP 범위 안에서만 구현하고, 앞선 STEP을 건너뛰지 않는다. (Fetch/AI 연결은 STEP-07/06, 포인트 지급은 STEP-08)

2. **로컬 Python은 3.13 (miniconda) → `psycopg2` 금지, `psycopg[binary]`(psycopg3) 사용.**
   psycopg2-binary는 3.13 휠이 없어 소스빌드 실패한다. 바이너리 휠은 psycopg 3.2.2+ 부터 존재.

3. **DB는 PostgreSQL 고정 (SQLite/MySQL 금지).**
   문서 규칙. 로컬에 postgres가 안 떠 있으면 `check`/`makemigrations --dry-run`은 통과하지만
   실제 `migrate`/`runserver`는 실패한다.

4. **`.env` 빈 값 gotcha.** `POSTGRES_DB=` 처럼 값이 비면 `os.environ.get("KEY", "기본값")`이
   기본값이 아니라 **빈 문자열("")**을 반환한다. 실행 전 `.env` 값을 채울 것.
   기본값 폴백이 필요하면 `os.environ.get("KEY") or "기본값"` 패턴 사용.

## 아키텍처 (컴포넌트 분리형 모노레포)

```
00_skn_4rd/
├─ .env                # ★ 루트 단일 통합 (모든 컴포넌트 공유, git 제외)
├─ .env.example        # 템플릿 (git 포함, 값 비움)
├─ docker-compose.yml  # 전체 오케스트레이션 (postgres·chromadb·django·fastapi·worker·nginx)
├─ django/             # [웹] Django 5 + Gunicorn — UI·인증·권한·CRUD·PostgreSQL
├─ fastapi_app/        # [AI/RAG] FastAPI + LangGraph — 힌트·오답분석·RAG (내부 전용)
├─ worker/             # [실행] 코드 격리 실행, jobs 테이블 polling (내부 전용)
├─ nginx/              # [프록시] reverse proxy (외부 노출은 여기 하나)
└─ llm_wiki/           # 설계 문서 (.docx 3종 + 구조/환경관리 .md)
```

- **역할 분리**: Django(서비스 로직) ↔ FastAPI(AI 로직). 모델/프롬프트 변경 영향 최소화.
- **`.env`는 루트 하나로 통합**, **`.venv`는 컴포넌트별 개별**. 두 규칙을 섞지 말 것.
- **DB/벡터**: PostgreSQL(원본) + ChromaDB(벡터 인덱스, 컬렉션 `wrong_note_embeddings`).
- Worker MVP는 Redis/RabbitMQ 없이 **jobs 테이블 polling** (`FOR UPDATE SKIP LOCKED`로 1건 선점).

## 데이터 소유권 / 접근 규칙 (SSOT) ⚠️

실측 접근 구조 (섞으면 안 됨):

| 컴포넌트 | PostgreSQL | ChromaDB |
|---|:---:|:---:|
| Django | ✅ (쓰기 주인) | ❌ |
| FastAPI | ❌ (stateless, payload로만 수신) | ✅ (쓰기 주인) |
| Worker | ✅ (jobs 실행자) | ❌ |

- ❌ **FastAPI에 psycopg 추가 금지** — RDB 직접 접근하지 말 것. 필요한 데이터는 Django가 요청 body로 넘긴다.
- ❌ **Django에 chromadb 클라이언트 추가 금지** — 벡터 작업은 전부 FastAPI HTTP(`/ai/*`) 경유.
- **호출은 단방향**: `사용자→Nginx→Django→FastAPI→(Chroma/OpenAI)`. FastAPI→Django 역호출 금지(순환 방지).
- **VDB 격리는 규율일 뿐** — 같은 docker 네트워크라 물리적으로는 누구나 chromadb에 접근 가능.
- **볼륨/영속성**: `pgdata`·`chromadata`는 named volume → 재시작/`down`엔 유지, **`down -v`에서만 삭제**.
- ⚠️ `postgres`가 host에 `5432` 노출 중 → **EC2 배포 시 닫을 것**.
- 상세: `llm_wiki/4. WOOKS_CODING_데이터_소유권_및_의존구조_v0.1.md`

## 볼륨(호스트 바인드 마운트) 디렉토리 — `volumes/`

호스트에 보존되는 바인드 마운트는 모두 `volumes/` 아래로 모은다(named volume 인 pgdata/chromadata/staticfiles 와 별개).

```
volumes/
├─ logs/                              # 로그 (Docker: ./volumes/logs → /logs), git 미추적(파일)
└─ data/<컴포넌트>/<목적>/            # seed 등 입력 데이터, git 추적
   └─ django/seed/problem_dataset.csv # ./volumes/data → /app/data:ro
```

- seed 적재: `docker compose run --build --rm django python manage.py load_problems` (상세는 `problems` 앱의 `load_problems` 명령).

## 로깅

모든 컴포넌트가 `volumes/logs/`에 기록(Docker는 `./volumes/logs:/logs` **bind mount** → 컨테이너 지워도 호스트에 보존).

```
volumes/logs/{django,fastapi,worker}/app.log   # 개발/디버깅 (회전 5MB×5)
volumes/logs/ai/research.jsonl                  # AI 연구용: LLM/RAG 이벤트 JSON Lines
```

- 경로는 env `LOG_DIR`로 통일 — **Docker는 compose가 `/logs` 주입**(비우면 코드 기본값 `<repo>/logs`이나 실행은 docker 전용). (`or` 패턴으로 빈 값 gotcha 회피)
- ⚠️ **로그 마운트는 반드시 `/app` 밖(`/logs`)에.** Django `logs` 앱이 `/app/logs`에 있어, 로그 볼륨을 `/app/logs`에 마운트하면 앱 코드가 가려져 `logs.models` ImportError + `logs` 마이그레이션 누락이 발생한다(겪고 수정함). 앱 이름과 마운트 경로 충돌 주의.
- 레벨은 env `LOG_LEVEL`(기본 INFO).
- **FastAPI**: `logging_setup.py`의 `setup_logging()`(main.py에서 호출) + `log_ai_event(event, **fields)`로 `research.jsonl` 기록. 라우터에 계측 지점 존재(`hint`/`rag_search`/`analyze`/`note_ask`).
- **사람이 읽는 로그(app.log)와 기계가 읽는 로그(research.jsonl)를 섞지 말 것.**
- 상세: `llm_wiki/5. WOOKS_CODING_로깅_시스템_v0.1.md`

## 환경변수 로딩 규약

각 컴포넌트가 자기 위치에서 루트 `.env`를 로드한다 (`python-dotenv`):

| 컴포넌트 | 위치 | 루트 경로 |
|---|---|---|
| Django | `config/settings.py` | `BASE_DIR.parent / ".env"` |
| FastAPI | `config.py` | `Path(__file__).resolve().parents[1] / ".env"` |
| Worker | `main.py`/`config.py` | `Path(__file__).resolve().parents[1] / ".env"` |

Docker에서는 compose의 `env_file: .env` / `environment:`로 주입 → `load_dotenv`는 파일 없으면 무시(양쪽 호환).

## 명령어

### 로컬 개발 (컴포넌트별 개별 venv)
```powershell
# 각 컴포넌트: python -m venv .venv → .\.venv\Scripts\activate → pip install -r requirements.txt

# Django (포트 8000) — django/ 에서
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver

# FastAPI (포트 8001) — fastapi_app/ 에서
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8001
#   헬스: http://127.0.0.1:8001/ai/health · Swagger: /docs

# Worker (상시 폴링) — worker/ 에서. ※ STEP-02(jobs 테이블) 이후 정상 동작
.\.venv\Scripts\python.exe main.py
```
> Git Bash/macOS/Linux: `source .venv/bin/activate`

### Docker Compose (전체 한 번에)
```bash
docker compose up --build          # 접속 http://localhost/ (Nginx→Django)
docker compose exec django python manage.py createsuperuser
docker compose down                # (down -v : DB까지 삭제)
```

## 컨벤션 (지시문 규칙)

- **FastAPI 폴더명은 `fastapi_app`** — `fastapi`로 두면 `import fastapi`가 로컬 폴더를 잡는 shadowing 위험.
- **내부 통신 보안**: Django→FastAPI 호출은 `X-Internal-API-Key`(+ `X-Request-ID`) 헤더 필수.
  FastAPI 라우터는 `Depends(verify_internal)`로 검증, 불일치 시 401.
- **FastAPI 엔드포인트 prefix는 `/ai`** (예: `/ai/health`, `/ai/hint`). 라우터/스키마/서비스 계층 분리.
- **커스텀 유저**: `AUTH_USER_MODEL = accounts.CustomUser` (필드 `role`, `point`, `is_subscribed`).
  결제/구독은 MVP 제외 — `is_subscribed`는 확장 대비 필드로만 유지.
- **사용자 코드 실행 sandbox는 Python 3.11** 기준 (로컬 개발 파이썬 3.13과 구분).
- **`.env` 커밋 절대 금지**. 팀 공유는 `.env.example` 갱신으로.
- 새 컴포넌트 추가 체크리스트: ① 폴더 ② `.venv`+`requirements.txt` ③ 루트 `.env` 로드 코드 ④ docker-compose 등록.

## 설계 문서 (llm_wiki/)

- `0. ...구현방향_v0.3.docx` · `1. ...서비스기획서_v0.3.docx` · `2. ...코드생성_지시문_v0.7.docx` (기준 문서)
- `3. ...프로젝트_구조_및_환경관리_v0.1.md` — 구조/venv/.env 규칙 상세 (텍스트, 바로 읽기 가능)
- `4. ...데이터_소유권_및_의존구조_v0.1.md` — 볼륨/영속성·RDB/VDB 접근·의존 방향 규칙
- `5. ...로깅_시스템_v0.1.md` — logs/ 레이아웃·AI 연구용 JSONL·환경변수
- `6. ...데이터모델_문제_제출_Job_오답노트_v0.1.md` — STEP-02 모델 설계(§7 정합). **제출이력=Submission ≠ ExecutionJob 분리** 근거, `job_type=code_run`(worker의 `code_execution`은 STEP-04에서 정합)
- 지시문 v0.7 §5는 Django 앱을 레포 루트에 두는 구조였으나, **venv 분리 위해 `django/` 하위로 승격**함.
  app 이름·endpoint path 등 내부 규칙은 지시문을 그대로 따른다.
