# WOOK'S CODING — 개발된 LLM 연동 웹 애플리케이션 설명

> SKN 4차 프로젝트 산출물 · 실제 코드 기준(`django/`, `fastapi_app/`, `compose/`, `nginx/`).

---

## 0. 평가 기준 대응

| 평가 요소 | 본 문서 반영 | 근거 위치 |
|---|---|---|
| 프론트엔드 구현 완성도 (HTML5/CSS3 반응형, ES6+, DOM/이벤트) | §2 | `templates/*.html`, `static/js/*.js`, `static/css/**` |
| 비동기 LLM 연동 (Async/Await·Fetch·예외·로딩) | §3 | `static/js/{chatbot,problem_solve}.js`, `ai_proxy/views.py` |
| Django 백엔드 (MVT/ORM/FBV·CBV/폼검증/인증·권한) | §4 | `*/views.py`, `*/models.py`, `*/forms.py` |
| 배포·운영 (AWS EC2·RDS·S3 + Docker) | §5 | `compose/*.yml`, `deploy/*.sh`, `nginx/nginx.conf`, `settings.py` |

---

## 1. 애플리케이션 개요

WOOK'S CODING은 **Django 5(웹/서비스 로직)** 와 **FastAPI(AI/RAG 전용)** 를 분리한 컴포넌트형 모노레포다.
사용자의 코드 제출·오답노트·질문을 바탕으로 **AI 단계별 힌트 · 오답노트 6섹션 분석 + RAG · coding_state 학습 메모리 · 미니튜터**를 제공한다.

- **호출 방향(단방향)**: `사용자 → Nginx → Django(/ai-proxy/*) → FastAPI(/ai/*) → (ChromaDB/OpenAI)`.
- **LLM**: OpenAI `gpt-4o-mini`(생성) · `text-embedding-3-small`(임베딩, 해시 폴백).
- **AI 기능 5종**: 힌트 · 오답분석+RAG · coding_state · 미니튜터 · 테스트케이스 자동 생성.

---

## 2. 프론트엔드 구현

### 2.1 HTML5 / CSS3 반응형 마크업
- **HTML5 시맨틱**: `base.html`이 `<header><nav><main><footer>`, `role="dialog"`, `aria-*`(`aria-label`·`aria-modal`·`aria-expanded`·`aria-busy`) 적용 → 접근성 고려.
- **CSS3 반응형**: `core/{base,layout,components}.css` + `pages/*.css` 레이어 분리. **Grid/Flex 기반**(`display:grid` 약 145곳·`flex` 107곳·`@media` 53곳·`minmax()` 133곳). 카드 목록은 `repeat(auto-fill, minmax())`로 열 수 자동 조정.
- **캐시 무효화**: 정적 링크에 버전 쿼리(`?v=...`)로 배포 시 갱신.

### 2.2 ES6+ 문법 / DOM·이벤트 처리
- **ES6+**: 화살표 함수, `const/let`, 템플릿 리터럴, 구조분해, `async/await`, `Array.map/find`, 옵셔널 체이닝, 즉시실행 모듈 패턴(IIFE).
- **DOM/이벤트**(`chatbot.js` 예):
  - `getElementById`/`querySelector`로 요소 취득, `addEventListener("submit"|"click"|"keydown")` 바인딩.
  - `e.preventDefault()`로 폼 기본 제출 차단 후 Fetch, `Escape` 키로 패널 닫기.
  - `escapeHtml()`로 사용자/LLM 텍스트 이스케이프(XSS 방어), `innerHTML` 안전 렌더.
  - 상태 클래스 토글(`classList.add/remove`), `hidden` 속성 제어, `input.focus()` 포커스 관리.

### 2.3 페이지별 스크립트
`problem_solve.js`(코드실행 Job 폴링+힌트), `chatbot.js`(미니튜터), `wrongnote_form.js`/`wrongnote_detail.js`(오답 분석·RAG), `mypage.js`·`profile_avatar.js`(게이미피케이션 UI).

---

## 3. 비동기 LLM 연동 구현 (핵심)

### 3.1 클라이언트 — Fetch + Async/Await + 예외·로딩

`chatbot.js`의 대표 흐름(미니튜터):

```js
const askBot = async (question) => {
  const activity = { path: location.pathname, title: document.title, problem_id: getProblemId() };
  const res = await fetch(askUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json",
               "X-CSRFToken": getCookie("csrftoken"), "Accept": "application/json" },
    body: JSON.stringify({ question, history: history.slice(-8), activity }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok || (body.status && body.status !== "success" && body.status !== "empty"))
    throw new Error(body.message || "답변을 불러오지 못했어요.");
  return body.data?.answer ?? "지금은 답변을 만들지 못했어요.";
};

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  sendBtn.disabled = true;                       // ① 로딩 진입
  renderAnswer(question, typingHtml, {loading:true});
  try   { renderAnswer(question, escapeHtml(await askBot(question))); }  // ② 응답
  catch (err) { renderAnswer(question, escapeHtml(err.message)); }       // ③ 예외
  finally { sendBtn.disabled = false; input.focus(); }                   // ④ 항상 복구
});
```

- **로딩 상태**: 타이핑 인디케이터 말풍선 + 버튼 `disabled`.
- **예외 처리**: `res.ok`/`status` 이중 확인, `.json().catch()`로 파싱 실패 방어, `try/catch/finally`.
- **비동기 Job 폴링**(`problem_solve.js`): 코드 실행은 `fetch(run)` → `submission_id` → 1초 간격 `pollResult()` 재폴링 → 완료 시 결과 렌더(장기 작업 비동기 처리 경험 반영).

### 3.2 서버 — Django AI 프록시 → FastAPI

`ai_proxy/views.py`(FBV, `@login_required @require_POST`)가 Fetch 요청을 받아 **입력 검증 → payload enrich → 내부 호출**:

- `hint`: 문제 지문·제약·난이도·`coding_state`·`level`을 서버에서 enrich 후 `/ai/hint` 호출.
- `tutor_ask`: 최근 30일 오답 최대 8건 + 현재 활동 + `coding_state` + 대화 이력(6턴)을 조립해 `/ai/tutor/chat` 호출(타임아웃 90s).
- 공통 계약: 응답을 `{status, request_id, message, data}`로 고정, 실패 시 HTTP 502 + `status`로 표준화.

### 3.3 내부 통신 — 계약 · 예외 매핑 (`ai_proxy/client.py`)

`call_fastapi()`가 외부 API 입출력 형식·비동기 호출·예외를 **일원화**:

- **입력**: `X-Internal-API-Key`(내부 인증) + `X-Request-ID`(추적) 헤더 + JSON body.
- **예외 매핑**(외부 API 실패 상황 전부 분기):
  | 예외 | 매핑 status | 로그 |
  |---|---|---|
  | `HTTPError` | `failed` (`HTTP_<code>`) | `ErrorLog` |
  | `socket.timeout/TimeoutError` | **`timeout`** | `ErrorLog`+traceback |
  | `URLError`/`JSONDecodeError`/`ValueError` | `failed` | `ErrorLog`+traceback |
  | 응답에 `[stub]` 포함 | `failed`(not_implemented) | — |
- **감사 로그**: 호출마다 `LLMRequestLog`(요청/응답/상태/`request_id`) 생성·완료 갱신, 실패 시 `ErrorLog` 별도 저장 → 이슈 추적 가능.

---

## 4. Django 백엔드 구현

### 4.1 MVT 구조
- **Model**: `accounts.CustomUser`, `problems.{Problem,ProblemCategory,ProblemTag,TestCase}`, `submissions.{Submission,ExecutionJob}`, `wrongnotes.WrongNote`, `codingstate.CodingState`, `gamification.{PointLog,Mission,UserMission}`, `logs.{LLMRequestLog,ErrorLog}` 등 9개 앱.
- **View**: 페이지는 CBV, 비동기 액션·AI 프록시는 FBV(§4.2).
- **Template**: `templates/` 하위 앱별 디렉토리 + `base.html` 상속.

### 4.2 CBV / FBV 혼용 (역할 분리)
- **CBV**: `ProblemListView`·`ProblemDetailView`(`ListView`/`DetailView`), `WrongNoteList/Detail/CreateView`, `MyPageView`·`Account*View`, `SignupView`, `NoticeList/DetailView`, `Admin*View`. → 목록/상세/폼의 정형 흐름.
- **FBV**: `run_submission`·`submit_submission`·`submission_result`(코드실행 Job), `review/hide/restore_wrong_note`, `ai_proxy.*`(AI 프록시). → 커스텀 비동기/JSON 응답.

### 4.3 ORM
- 관계형 모델링: `Submission`↔`ExecutionJob` 분리(제출이력≠실행잡), `CodingState` `OneToOne(User)`, `Problem`↔`ProblemTag` M2M.
- 쿼리 최적화: `select_related("problem")`·`prefetch`(튜터 최근 오답 조회), 소유자 필터(`filter(user=...)`), 집계(`gather_stats`의 정답률/태그 top-N).
- Worker 잡 선점: `FOR UPDATE SKIP LOCKED`로 동시성 제어(1건 원자적 선점).

### 4.4 폼 검증 / 인증·권한
- **폼**: `accounts/forms.py`(회원가입), `mypage/forms.py`(계정), 오답노트 작성 폼 — 서버측 필드 검증 + 템플릿 오류 표시.
- **인증**: `AUTH_USER_MODEL=accounts.CustomUser`, 세션 인증, `LOGIN_URL`, `@login_required`/`LoginRequiredMixin`.
- **권한**: 역할(`role`)·`is_service_admin` 기반 운영 화면 분리, 데이터 소유자 격리(오답노트·RAG `user_id` 필터), CSRF 미들웨어 + `X-CSRFToken`.
- **API 입력 검증**: `ai_proxy`가 필수 필드 누락 시 400, JSON 파싱 실패 시 400.

---

## 5. 배포·운영 구현

### 5.1 컨테이너 구성 (Docker Compose)
- **앱 서버**(`compose/main.yml`): `nginx` · `django`(Gunicorn) · `fastapi` · `chromadb` 4개 서비스.
  - `django` 기동 커맨드: `migrate --no-input` → `collectstatic` → `gunicorn config.wsgi:application --bind 0.0.0.0:8000`(WSGI).
  - **헬스체크**: `/health/` 폴링(interval 5s, retries 20) → `nginx`는 `django healthy` 조건에서 기동.
- **워커 서버**(`compose/worker.yml`): `worker` 단독(코드 격리 실행), `restart: unless-stopped`. **별도 EC2**.

### 5.2 리버스 프록시 (Nginx → Gunicorn → Django)
`nginx/nginx.conf`:
- `location /static/` → 공유 볼륨(`/staticfiles/`)에서 직접 서빙(`expires 7d`).
- `location /` → `proxy_pass http://django:8000`(Gunicorn), `X-Forwarded-*` 헤더 전달, Docker 내장 DNS `resolver`로 컨테이너 재생성 IP 재조회.
- **FastAPI/Worker/DB는 외부 미노출**(내부 네트워크 전용).

### 5.3 AWS 배포
- **EC2**: 앱 서버 / 워커 서버 **2개 인스턴스 분리**(신뢰 불가 코드 실행 격리).
- **RDS(PostgreSQL)**: 원천 데이터 공유(`settings.py` `ENGINE=postgresql`). 운영 확인 엔드포인트 `postgres.*.rds.amazonaws.com`(테스트보고서).
- **배포 스크립트**(`deploy/deploy_main.sh`·`deploy_worker.sh`·`_lib.sh`): `git fetch` → `reset --hard origin/<branch>` → `.env` 점검 → `compose up --build -d` → **헬스 검증** → 마이그레이션 성공 확인. 실패 시 위치·명령·종료코드 출력.
- **정적 파일 서빙(S3 미사용)**: 정적 파일은 `collectstatic` → Docker `staticfiles` 볼륨 → **Nginx가 직접 서빙**한다. 사용자 업로드 미디어가 없어(아바타는 이모지 기반) 별도 오브젝트 스토리지가 필요하지 않다. 프론트 정적 자원을 S3+CloudFront로 이전하는 것은 확장 포인트로 둔다(§6).

### 5.4 로깅·운영
- `volumes/logs/{django,fastapi,worker}/app.log`(bind mount, 컨테이너 삭제에도 보존) + `logs/ai/research.jsonl`(AI 연구용 JSONL).
- 운영 화면(`/adminpanel/logs/`)에서 `LLMRequestLog`·`ErrorLog` 조회 → 이슈 추적.

---

## 6. 확장 포인트

- **정적/미디어 S3 이전**: 프론트 정적 자원을 `django-storages`+S3+CloudFront로 이전(CDN 확장).
- LLM 응답 스트리밍(현재 단일 호출).
- CI 자동화 테스트 파이프라인 확대.

*작성 근거: `ai_proxy/{views,client}.py`, `static/js/{chatbot,problem_solve}.js`, `*/views.py`·`models.py`, `compose/*.yml`, `nginx/nginx.conf`, `config/settings.py`.*
