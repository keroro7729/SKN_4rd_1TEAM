# CLAUDE.md

WOOK'S CODING — AI 기반 코딩 학습 웹앱 (SKN 4차 프로젝트). 문제 풀이 · 코드 실행 · **AI 단계별 힌트** · **오답노트 RAG**.

## ⚠️ 이 저장소에서 가장 먼저 알아야 할 것

1. **현재 상태: STEP-01~08 실질 완료 + EC2/RDS 배포 완료.** (STEP 순차 빌드 단계는 이미 끝났다 — 아래 [현재 구현 상태](#현재-구현-상태-실측-2026-07) 표가 SSOT)
   - 초기 코드생성 지시문 v0.7은 STEP-01~10 순차 빌드 규칙이었으나, 이후 **문제 추천·coding_state 고도화·배포 스크립트 등 STEP 범위를 벗어난 작업**이 누적되며 실제 코드는 지시문 STEP 경계를 넘어섰다. **더는 STEP 번호로 진행을 추적하지 말 것** — 지시문 STEP은 히스토리로만 보고, 실제 상태는 코드/아래 표 기준.
   - `fastapi_app`은 스텁이 아니라 **완전 구현**(9개 라우터·서비스 전 계층, OpenAI 실호출·RAG v1 운영 동작). 5개 AI 기능(힌트·오답분석+RAG·coding_state·미니튜터·테스트케이스 생성) 모두 배선됨.
   - 단, **미사용 스텁·고아 엔드포인트가 남아 있다** → [정리 대상](#정리-대상-미사용--고아--stale) 참고. 신규 작업 전 이 목록부터 확인.
   - ⚠️ **"LangGraph 에이전트"는 실제로 미사용** — 절차적 오케스트레이션 + 프롬프트/RAG 파이프라인이다(문서 11 §2). 코드/문서에서 LangGraph로 서술된 부분은 부정확.

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
├─ fastapi_app/        # [AI/RAG] FastAPI (LangGraph 미사용, 절차적) — 힌트·오답분석·RAG·coding_state·튜터 (내부 전용)
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

## coding_state (사용자 상태 메모리) ⚠️

AI가 사용자별 학습 상태를 요약해 보관하는 **공유 컨텍스트(메모리)**. 힌트·튜터·오답분석의 개인화 기반. `codingstate` 앱(`CodingState` 모델, 사용자당 1행 `OneToOne`). **사용자에게 직접 노출 금지** — AI 프롬프트 참고용.

- **필드**: `summary`(진단 요약) · **`thinking_profile`(사고 추적 메모리: 사고/디버깅 방식)** · `level`(입문/초급/중급/고급) · `strengths`/`weaknesses`/`recurring_mistakes`/`recommended_focus`(JSON list) · `stats_snapshot`(집계 원본) · `source_submission_count`(staleness 기준) · **`refresh_count`(갱신 횟수)**.
- **입력(사고 추적)**: 집계 통계 + **`recent_code`(최근 제출 코드 스니펫) · `retrospections`(오답 회고 코멘트·AI `cause` 원문) · `recent_questions`(미니튜터 질문, `LLMRequestLog`)** + 롤링 메모리(`previous_summary`·`previous_thinking`). 크기 제한: 코드 600자·회고 300자·질문 200자, 최근 N건.
- **흐름**: Django `gather_stats`(결정적 집계 + 위 사고 입력) → `refresh()`가 직전 메모리 첨부 → FastAPI `/ai/coding-state/summarize`(`gpt-4o-mini`, JSON, **롤링/델타 갱신**) → `update_or_create` 저장 → `get_prompt_context(user)`로 힌트/튜터/오답분석 payload의 `coding_state` 키에 주입(`thinking_profile` 포함).
- **갱신 트리거**: ① 실시간 훅 `ensure_fresh(user)`(오답노트 완료 시, 신규 제출 5건 게이트) ② **배치** `codingstate.services.batch_refresh(...)` = 신규 활동 쌓인 사용자만 골라 갱신(스케줄/오프라인). 명령: `python manage.py refresh_coding_state --stale [--min-new N] [--limit N]` / `--all`(강제) / `<user_id>`(단일).
- ⚠️ `refresh()`/`batch_refresh()`는 사용자당 FastAPI(LLM) **동기 호출(최대 90s)** → **요청 스레드에서 배치 호출 금지**, 크론/관리 명령 전용. `batch_refresh`는 집계 2쿼리로 stale 판별 후 `limit`으로 LLM 호출 수 상한.
- 상세: `llm_wiki/11. WOOKS_CODING_AI_Agent_구조_및_핵심기술_v0.1.md` §4.2.

### coding_state 고도화 — 구현 완료 항목

아래는 모두 **구현됨**(사고 추적 메모리 + 요약 메모리 연속성):

1. ✅ **제출 코드 반영** — `gather_stats._recent_code`(최근 4건, 600자 truncate) → 코딩 스타일·패턴 추론.
2. ✅ **질문 로그 반영** — `_recent_questions`(`LLMRequestLog` `tutor_chat` 최근 5건) → 막히는 지점·오해 추적.
3. ✅ **오답 회고 원문 기반** — `_retrospections`(회고 코멘트 + AI `cause` 원문).
4. ✅ **사고 과정 추론** — FastAPI가 위 입력으로 `thinking_profile`(가설 세우는 방식·디버깅 습관·개념 공백) 생성.
5. ✅ **요약 메모리 연속성(rolling)** — `previous_summary`/`previous_thinking`를 프롬프트에 넣어 **변화점 위주 델타 갱신**(처음부터 새로 쓰지 않음).
6. ✅ **시스템 프롬프트 강화** — 근거 인용·직전 대비 변화점 우선·희박 데이터 과장 금지·메모리 일관성.

> ⚠️ 로그/코드가 프롬프트에 들어가므로 **PII·payload 크기** 주의(현재 truncate로 제한). 향후: 정답 diff 기반 코드 요약, 질문 클러스터링, `thinking_profile` 신뢰도 표기 등은 추가 고도화 여지.

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

## 설계 문서 (llm_wiki/) — 특징·신뢰도·활용도

> ⚠️ **문서 신뢰도에 편차가 있다.** `0~9`번 다수는 **구현 이전에 쓴 설계/예고 문서**라 실제 코드와 어긋나는 곳이 있다("미구현" 예고가 실제론 구현됨 등). **`10`·`11`·`12`는 코드 실측 후 작성 → 최신·최고 신뢰.** 상태 파악은 반드시 **문서 11 → 코드 → CLAUDE.md** 순으로 교차검증.

**기준 문서 (원천 규칙, `.docx` — 바로 못 읽음, 필요 시 변환)**
- `0. ...구현방향_v0.3.docx` · `1. ...서비스기획서_v0.3.docx` · `2. ...코드생성_지시문_v0.7.docx` — 프로젝트 최초 규칙. **STEP 순차 빌드·app 이름·endpoint 규칙의 근거**. 단 진행 상태 기준으로는 이미 초과 달성됨(위 참고).

**상시 참조 규약 문서 (`.md` — 신뢰 높음, 아키텍처 규칙의 SSOT)**
- `3. ...프로젝트_구조_및_환경관리_v0.1.md` — 구조/venv/.env 규칙 상세. **활용도 높음**.
- `4. ...데이터_소유권_및_의존구조_v0.1.md` — 볼륨/영속성·RDB/VDB 접근·의존 방향(SSOT). **활용도 높음**.
- `5. ...로깅_시스템_v0.1.md` — logs/ 레이아웃·AI 연구용 JSONL·환경변수.
- `6. ...데이터모델_문제_제출_Job_오답노트_v0.1.md` — 모델 설계. **제출이력=Submission ≠ ExecutionJob 분리** 근거.

**설계/예고 문서 (구현 前 작성 → 실제와 diff 있음, 참고용)**
- `7. ...STEP05-07_AI_RAG_FE_연계_가이드_v0.1.md` — FastAPI/RAG/프론트 연계 가이드. ⚠️ "LLM 생성층 의도적 미구현"·"LangGraph 예고" 등 **일부 예고가 실제 구현과 불일치**(문서 11이 정정).
- `8. ...테스트케이스_생성_에이전트_v0.1.md` — 정답코드/제너레이터 기반 TC 생성 설계. 실제 구현은 `problems/services/testcase_agent.py` + `/ai/authoring/*`.
- `9. ...오답노트_AI리포트_useflow_및_RAG설계_v0.1.md` — 오답노트/AI리포트 분리, **2단계 RAG** 설계 초안. ⚠️ `WrongNoteReport`·`/report` 배선은 **여전히 고아**(설계만 존재).

**실측 기반 문서 (코드 대조 후 작성 → 최신·최고 신뢰, 발표/평가 근거)**
- `10. ...오답노트_RAG_리트리빙_고도화_v0_vs_v1_성능평가.md` — 리트리빙 v1(섹션 멀티청킹+mean/max, OpenAI 임베딩) **정량 성능평가**(Precision@4 0.63→1.00). 임베딩 `text-embedding-3-small`(해시 폴백), 컬렉션 버저닝 `wrong_note_embeddings-<sig>`. 평가: `python -m services.rag_eval`. **★ RAG 근거 자료**.
- `11. ...AI_Agent_구조_및_핵심기술_v0.1.md` — **★★ 코드 실측 종합 문서. 상태 파악의 1차 기준.** 5개 Agent 실측 구조·협업, LangGraph 미사용 규명(§2), coding_state §4.2, **미사용/고아 목록(§7·§9)** 포함.
- `12. ...coding_state_사용자상태메모리_v0.1.md` — coding_state 단독 설명 + **발표 대본**.

**검증/산출물 문서 (평가 대응)**
- `STEP04_05_DB_VECTORDB_검증_가이드_v0.1.md` — DB/벡터DB 수동 검증 절차.
- `05_WOOKS_CODING_테스트계획및결과보고서_수정.md` — **테스트 계획·결과 보고서(평가 20점 대응)**. 76 TC 전건 PASS(수동). ⚠️ "AI Server: FastAPI + LangGraph" 등 **오기 잔존**(문서 11과 맞춰 정정 필요), 자동화 테스트 아님.
- `SKN 29기..._평가계획서.docx.pdf` — **채점 기준 원본**(화면설계서·LLM연동 웹앱·시스템 구성도 등 산출물 요구).
- `screenshots/` — 시연 캡처(README 임베드용).

> 지시문 v0.7 §5는 Django 앱을 레포 루트에 두는 구조였으나, **venv 분리 위해 `django/` 하위로 승격**함. app 이름·endpoint path 등 내부 규칙은 지시문을 그대로 따른다.

---

## 현재 구현 상태 (실측, 2026-07)

> ⚠️ 이 표가 진행 상태의 **SSOT**. 지시문 STEP 번호가 아니라 이 표로 판단할 것.

| 영역 | 상태 | 근거/위치 |
|---|:--:|---|
| 인증·권한·CRUD(문제/제출/오답노트/마이페이지) | ✅ | `django/{accounts,problems,submissions,wrongnotes,mypage}` |
| 코드 실행(Worker 격리 샌드박스 + 채점) | ✅ | `worker/`, jobs 폴링 `FOR UPDATE SKIP LOCKED` |
| FastAPI AI 서버(9 라우터·서비스 전 계층) | ✅ | `fastapi_app/{routers,services,schemas}` |
| AI 힌트(레벨 1~3 소크라테스식) | ✅ | `/ai/hint` |
| 오답노트 AI 분석(6섹션) + RAG v1 | ✅ | `/ai/wrong-note/{analyze,embed,search}` |
| coding_state(사용자 상태 메모리, rolling) | ✅ | `codingstate` 앱 + `/ai/coding-state/summarize` |
| 미니튜터(멀티턴·3중 개인화) | ✅ | `/ai/tutor/chat` |
| 테스트케이스 자동 생성 에이전트 | ✅ | `problems/services/testcase_agent.py` + `/ai/authoring/*` |
| 포인트·미션·게이미피케이션 | ✅ | `gamification` 앱(`PointLog`·`Mission`) |
| 문제 추천 | ✅ | `problems/services/recommend.py` |
| 프론트↔AI 연동(프록시) | ✅ | `ai_proxy` 앱(`/ai-proxy/*`) |
| EC2(app/worker 분리)+RDS 배포 | ✅ | `compose/{main,worker}.yml`, `deploy/*.sh` |
| 2단계 RAG 리포트(`/report`) | ⚠️ 고아 | 구현됐으나 Django 미배선 |
| `/analyze` ← RAG 근거 주입 | ⚠️ 부분 | search/analyze 독립 호출, analyze 프롬프트엔 `evidence=[]` |
| 자동화 테스트 | ⚠️ 부분 | django 6개 앱만 `tests.py`, FastAPI·worker·4개 앱 없음 |

### 정리 대상 (미사용 · 고아 · stale)

> 신규 작업이나 발표 前 정리 권장. 실측 확인됨.

1. **`fastapi_app/agents/langgraph_agents.py`** — `NotImplementedError` 스텁, `main.py`에서 import조차 안 됨. **완전 사문(死文)** → 삭제 또는 "미사용" 주석 명시.
2. **`fastapi_app/services/prompts.py`** — 어디서도 import 안 됨(실제 프롬프트는 `llm.py`·`authoring.py`·`coding_state.py`·`wrong_note_report.py`에 하드코딩). → 삭제 또는 실제 사용처로 통합.
3. **`fastapi_app/routers/health.py`의 `llm_status:"not_implemented"`, `rag_status:"vector_index_only"`** — 옛 하드코딩 문자열. LLM/RAG 실제 동작 중 → 실제 상태로 갱신.
4. **`/ai/wrong-note/report`(2단계 RAG 리포트)** — `main.py` 등록됐으나 **Django 호출자 없음(고아)**. 배선하거나 명시적 보류 표기.
5. **`/ai/wrong-note/ask`** — 프론트 UI는 제거됐으나 `ai_proxy` 프록시 라우트(`wrong-note/ask/`)+FastAPI 엔드포인트 잔존 → 유지/삭제 결정.
6. **`05_..._테스트계획및결과보고서`의 "FastAPI + LangGraph" 오기** — 문서 11과 맞춰 정정.

---

## 남은 작업 Plan (백로그)

> 진행 시 각 항목이 어느 산출물/평가기준에 대응하는지 병기. 상세 착수는 별도 지시로.

**A. 문서/산출물 정리 (평가 대응 — 진행 중)**
- [x] **CLAUDE.md 현행화** — STEP 상태·llm_wiki 활용도·남은 작업 Plan (이 문서).
- [ ] **평가계획서 대응 산출물 초안** — 화면설계서 / LLM 연동 웹앱 설명 / 시스템 구성도, 평가기준 매핑.
- [ ] `05_테스트계획및결과보고서` 오기(LangGraph 등) 정정 + 자동화 테스트 결과 반영.

**B. 코드 정리 (미사용·고아 제거) — [정리 대상](#정리-대상-미사용--고아--stale) 6건**
- [ ] `langgraph_agents.py`·`prompts.py` 삭제 또는 미사용 명시.
- [ ] `health.py` 상태 문자열을 실제 구현 기준으로 갱신.
- [ ] `/report`·`/ask` 고아 엔드포인트: 배선 or 보류 결정.

**C. 테스트 보강 (최소한)**
- [ ] **FastAPI 스모크 테스트** — `/ai/health`, 주요 라우터 인증(`verify_internal`) 401, 스키마 검증(현재 fastapi_app 테스트 0).
- [ ] Django 미커버 앱(`accounts`·`mypage`) 핵심 경로 최소 테스트.
- [ ] (선택) worker 채점 로직 단위 테스트.

**D. 기능 완성도 (선택 고도화)**
- [ ] `/analyze`에 `/search` RAG 근거 실제 주입(현재 `evidence=[]`).
- [ ] coding_state 갱신 트리거 확대(제출·정답 처리 시점) 검토.
- [ ] coding-state·authoring Agent `research.jsonl` 계측 추가.
- [ ] ⚠️ 운영 배포 시 host `5432`(PostgreSQL) 노출 차단.
