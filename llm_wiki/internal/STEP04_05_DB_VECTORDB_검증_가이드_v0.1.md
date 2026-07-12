# STEP04-05 DB/VectorDB 검증 가이드 v0.1

## 목적

이 문서는 WOOK'S CODING의 PostgreSQL/RDS와 ChromaDB 상태를 배포 후 안전하게 확인하기 위한 조회 전용 진단 절차를 정리한다. 진단 도구는 아키텍처, 모델명, 기존 URL, Worker 구조를 변경하지 않는다.

## 저장소 역할

- PostgreSQL/RDS: 서비스의 원본 데이터 저장소다. 사용자, 문제, 테스트케이스, 제출, 실행 Job, 오답노트, 포인트, 미션, 공지, 로그를 저장한다.
- ChromaDB: 오답노트 RAG 검색용 벡터 인덱스다. MVP에서는 `wrong_note_embeddings` 컬렉션만 사용한다.
- `wrongnotes_wrongnotevector`: PostgreSQL의 오답노트와 ChromaDB 문서 ID를 연결하는 매핑 테이블이다.

## 금지 규칙

- 진단 도구에서 ChromaDB 컬렉션을 생성하지 않는다.
- `concept_embeddings`, `pattern_embeddings`는 MVP에서 생성하지 않는다.
- 조회 결과에 DB 비밀번호, API Key, Secret Key를 출력하지 않는다.
- 운영 메뉴나 공개 URL에 진단 기능을 노출하지 않는다.

## PostgreSQL 스키마 확인

```bash
docker compose exec -T django python manage.py inspect_postgres_schema
docker compose exec -T django python manage.py inspect_postgres_schema --core-only
docker compose exec -T django python manage.py inspect_postgres_schema --core-only --row-counts
docker compose exec -T django python manage.py inspect_postgres_schema --table problems_problem
docker compose exec -T django python manage.py inspect_postgres_schema --json
```

확인 기준:

- DB 정보가 출력되어야 한다.
- 핵심 테이블이 `MISSING`이면 배포 또는 migration 상태를 먼저 확인한다.
- `problems_problem`, `problems_testcase` row count가 0이면 문제 seed 적재 상태를 확인한다.

## ChromaDB 확인

FastAPI 내부 진단 API:

```text
GET /ai/diagnostics/chroma
Headers:
  X-Internal-API-Key: <INTERNAL_API_KEY>
  X-Request-ID: <trace-id>
```

Django 명령:

```bash
docker compose exec -T django python manage.py inspect_vector_db
docker compose exec -T django python manage.py inspect_vector_db --json
```

확인 기준:

- `wrong_note_embeddings`가 있으면 정상 인덱싱 경로를 사용할 수 있다.
- `wrong_note_embeddings`가 없으면 아직 오답노트가 인덱싱되지 않은 상태일 수 있으므로 `WARN`으로 본다.
- `concept_embeddings`, `pattern_embeddings`가 있으면 MVP 범위를 벗어난 상태이므로 제거 계획을 세운다.

## 통합 상태 확인

```bash
docker compose exec -T django python manage.py inspect_storage_state
```

판정 기준:

- `PASS`: 현재 요구 기준 충족
- `WARN`: 서비스가 일부 동작할 수 있으나 데이터 적재 또는 인덱싱 확인 필요
- `FAIL`: migration, 배포, 설정, 금지 컬렉션 등 즉시 조치 필요

## AI/RAG 담당자 체크리스트

| 확인 항목 | 확인 명령/화면 | 기대 결과 |
| --- | --- | --- |
| 내부 API Key 차단 | `GET /ai/diagnostics/chroma` 호출 시 Key 생략 | 401 반환 |
| Request ID 필수 | `X-Request-ID` 생략 | 400 반환 |
| Chroma 조회 전용 | 진단 API 호출 전후 컬렉션 수 비교 | 컬렉션 자동 생성 없음 |
| 필수 컬렉션 | `inspect_vector_db` | `wrong_note_embeddings` 상태 확인 가능 |
| 금지 컬렉션 | `inspect_vector_db` | `concept_embeddings`, `pattern_embeddings` 미존재 |
| RAG 검색 | `/ai/wrong-note/search` | `user_id` metadata filter 적용 |
| 검색 결과 계약 | `/ai/wrong-note/search` | `note_id`, `source`, `score` 반환 |
| 질의응답 근거 | `/ai/wrong-note/ask` | `evidence_note_ids`, `scores` 반환 |

## BE 담당자 체크리스트

| 확인 항목 | 확인 명령/화면 | 기대 결과 |
| --- | --- | --- |
| PostgreSQL 연결 | `inspect_postgres_schema --core-only` | DB 정보와 핵심 테이블 출력 |
| migration 상태 | `inspect_storage_state` | 핵심 테이블 `PASS` |
| 문제 데이터 | `inspect_postgres_schema --table problems_problem --row-counts` | row count 1 이상 |
| 테스트케이스 데이터 | `inspect_postgres_schema --table problems_testcase --row-counts` | row count 1 이상 |
| 실행 Job 테이블 | `inspect_storage_state` | `submissions_executionjob exists` |
| Secret 출력 금지 | 진단 명령 전체 출력 확인 | 비밀번호/API Key 미출력 |

## FE 담당자 체크리스트

| 확인 항목 | 확인 명령/화면 | 기대 결과 |
| --- | --- | --- |
| 문제 목록 | `/problems/` | PostgreSQL 문제 데이터 표시 |
| 문제 풀이 | `/problems/<id>/` | 실행/제출 결과 표시 |
| 오답노트 작성 | 오답 후 작성 화면 | 저장 후 인덱싱 상태 확인 가능 |
| 내 노트 질의 | `/wrongnotes/ask/` | empty/failed/timeout/success 상태 UI 분기 |
| 오류 표시 | request_id 포함 응답 | 화면 또는 로그에 추적 ID 표시 |

## 운영 확인 순서

1. `docker compose ps`로 컨테이너 상태를 확인한다.
2. `docker compose exec -T django python manage.py check`를 실행한다.
3. `inspect_postgres_schema --core-only --row-counts`로 RDS 테이블과 데이터 적재를 확인한다.
4. `inspect_vector_db`로 ChromaDB 컬렉션 상태를 확인한다.
5. `inspect_storage_state`로 PASS/WARN/FAIL 요약을 확인한다.
6. 문제 제출, 오답노트 저장, 오답노트 질의를 화면에서 1회씩 확인한다.
