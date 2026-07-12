# WOOK'S CODING 4차 프로젝트 테스트 계획 및 결과보고서

## 1. 개요

### 1.1. 문서 개요

| 항목 | 내용 |
|---|---|
| 프로젝트명 | WOOK'S CODING |
| 문서 목적 | 기능, LLM 연동, RAG, Docker Worker, 배포 테스트 계획 및 결과 정리 |
| 평가 대응 항목 | 테스트 계획 및 결과 보고서 20점 |
| 테스트 범위 | 인증, CRUD, AI 연동, 코드 실행, RAG, 예외 처리, 배포 재현성 |
| 테스트 기준 환경 | Django 5, PostgreSQL, FastAPI, ChromaDB, Docker Worker, AWS EC2/RDS |

본 문서는 WOOK'S CODING 서비스가 요구사항에 맞게 동작하는지 검증하기 위한 테스트 계획과 결과 보고서이다. 
검증 방법은 `06_WOOKS_CODING_검증가이드.md` 파일 참고

### 1.2. 평가 항목 대응표

| 평가 기준 | 본 문서 반영 내용 |
|---|---|
| 테스트 계획 수립 | 테스트 목표, 환경, 범위, 데이터 정의 |
| 기능 테스트 | 인증, 문제, 오답노트, 마이페이지 테스트 정의 |
| LLM 테스트 | AI 힌트, 오답 분석, Timeout, 500 오류 검증 |
| RAG 테스트 | user_id 필터, evidence_note_ids, scores 검증 |
| Docker 실행 테스트 | success, failed, timeout, runtime_error 검증 |
| 배포 테스트 | Nginx, Gunicorn, FastAPI, ChromaDB, Worker, RDS 검증 |
| 이슈 추적 | 원인, 조치, 상태 기록 |
| 결과 보고 | 테스트 결과 검증 시나리오 |

---

## 2. 테스트 목표

| 목표 | 설명 |
|---|---|
| 기능 검증 | 회원가입, 로그인, 문제 풀이, 제출, 오답노트 등 핵심 기능 정상 동작 확인 |
| AI 연동 검증 | FastAPI 기반 AI 힌트, 오답 분석, RAG 질의응답 정상 응답 확인 |
| 예외 검증 | Timeout, 500 오류, 인증 만료, 실행 오류 등 실패 상황 처리 확인 |
| 코드 실행 검증 | Docker Worker가 제출 코드를 격리 실행하고 결과를 저장하는지 확인 |
| 데이터 검증 | PostgreSQL 저장, ChromaDB 인덱싱, 로그 기록 확인 |
| 배포 검증 | AWS EC2/RDS 환경에서 재기동 및 서비스 접근 가능 여부 확인 |

---

## 3. 테스트 환경

| 구분 | 환경 |
|---|---|
| OS | Ubuntu Server on AWS EC2 |
| Backend | Django 5 |
| AI Server | FastAPI (LangGraph 미사용 · 절차적 오케스트레이션) |
| Database | AWS RDS PostgreSQL |
| Vector DB | ChromaDB |
| Code Runner | Docker Worker + Python 3.11 |
| Web Server | Nginx + Gunicorn |
| 배포 방식 | Docker Compose 또는 systemd 기반 서비스 실행 |

---

## 4. 테스트 범위

| 범위 | 포함 여부 | 설명 |
|---|---|---|
| 회원가입/로그인 | 포함 | 인증 및 세션 검증 |
| 사용자 권한 | 포함 | 일반 사용자/관리자 접근 제어 |
| 문제 CRUD | 포함 | 문제 조회, 관리자 등록/수정 확인 |
| 코드 제출 | 포함 | Submission, ExecutionJob 생성 확인 |
| Docker Worker 실행 | 포함 | 정상 실행, 오류, timeout 처리 |
| AI 힌트 | 포함 | FastAPI 연동 및 응답 표시 |
| 오답 분석 | 포함 | AI 분석 결과 저장 확인 |
| 오답노트 RAG | 포함 | user_id 필터 기반 유사 노트 검색 |
| 내 노트에 물어보기 | 포함 | 답변 및 근거 노트 표시 |
| 포인트/미션 | 포함 | 포인트 지급 이력 확인 |
| 로그 | 포함 | ErrorLog, LLMRequestLog 저장 확인 |
| AWS 배포 | 포함 | Nginx, Gunicorn, Django, FastAPI, Worker 기동 확인 |
| 결제/상점/커뮤니티 | 제외 | MVP 범위 제외 |

---

## 5. 테스트 데이터

### 테스트 데이터 상세

| 구분 | 아이디 | 비밀번호 | 권한 |
|---|---|---|---|
| 관리자 계정 | admincode | admincode | admin |
| 테스트 유저 | usertest | qlalfqjsgh1 | student |

---

## 6. 기능 테스트 계획 및 결과

| TC ID | 테스트 항목 | 절차 | 기대 결과 | 결과 |
|---|---|---|---|---|
| TC-F-001 | 회원가입 | 신규 username/email/password 입력 후 가입 | CustomUser 생성, 로그인 가능 | PASS |
| TC-F-002 | 로그인 | 올바른 계정으로 로그인 | 세션 생성, 문제 목록 이동 | PASS |
| TC-F-003 | 로그인 실패 | 잘못된 비밀번호 입력 | 오류 메시지 표시 | PASS |
| TC-F-004 | 로그아웃 | 로그아웃 버튼 클릭 | 세션 종료, 홈 이동 | PASS |
| TC-F-005 | 권한 제한 | 비로그인 상태로 문제 상세 접근 | 로그인 페이지 이동 | PASS |
| TC-F-006 | 관리자 접근 제한 | 일반 사용자로 관리자 페이지 접근 | 접근 거부 | PASS |
| TC-F-007 | 문제 목록 조회 | 문제 목록 화면 접근 | 활성 문제 목록 표시 | PASS |
| TC-F-008 | 문제 필터 | 난이도/카테고리 필터 적용 | 조건에 맞는 문제 표시 | PASS |
| TC-F-009 | 문제 상세 조회 | 문제 카드 클릭 | 설명, 제약조건, 샘플 표시 | PASS |
| TC-F-010 | 마이페이지 조회 | 마이페이지 접근 | 포인트, 풀이 현황, 취약 유형 표시 | PASS |

---

## 7. 코드 실행 테스트 계획 및 결과

| TC ID | 테스트 항목 | 입력 | 기대 결과 | 결과 |
|---|---|---|---|---|
| TC-R-001 | 정답 코드 실행 | 정상 Python 코드 | result=success, stdout 저장 | PASS |
| TC-R-002 | 오답 코드 실행 | `print("Hello World")` 오답 코드 | result=wrong(0/30 TC), output 저장 | PASS |
| TC-R-003 | 런타임 오류 | ZeroDivisionError 코드 | result=failed 또는 runtime_error, stderr 저장 | PASS |
| TC-R-004 | 시간초과 | 무한루프 코드 | result=timeout, timeout 메시지 저장 | PASS |
| TC-R-005 | 빈 코드 제출 | 빈 문자열 | 폼 검증 오류 표시 | PASS |
| TC-R-006 | ExecutionJob 생성 | 코드 제출 | Submission과 ExecutionJob 생성 | PASS |
| TC-R-007 | Worker polling | pending Job 존재 | Worker가 running으로 변경 후 처리 | PASS |
| TC-R-008 | 채점 exact | 출력 완전 일치 | success 처리 | PASS |
| TC-R-009 | 채점 line_trim | 줄 끝 공백 차이 | success 처리 | PASS |
| TC-R-010 | 채점 float | 허용 오차 내 실수 출력 | success 처리 | PASS |
> 실측: `print("Hello World")` 코드 제출 → Job: success, 테스트 0/30, 실행 40ms 확인 (운영서버 스크린샷 확인)

---

## 8. LLM 연동 테스트 계획 및 결과

| TC ID | 테스트 항목 | 절차 | 기대 결과 | 결과 |
|---|---|---|---|---|
| TC-AI-001 | FastAPI health check | `/health` 호출 | status=ok | PASS |
| TC-AI-002 | AI 힌트 성공 | 문제 상세에서 힌트 요청 | hint, concepts 반환 | PASS |
| TC-AI-003 | AI 힌트 로그 저장 | 힌트 요청 후 DB 확인 | LLMRequestLog 생성 | PASS |
| TC-AI-004 | 오답 분석 성공 | 오답 제출 후 분석 요청 | error_pattern, ai_analysis 반환 | PASS |
| TC-AI-005 | 오답 분석 저장 | 오답노트 저장 | ai_analysis JSON 저장 | PASS |
| TC-AI-006 | LLM Timeout | 강제 timeout 설정 | 사용자 오류 메시지 표시, 로그 저장 | PASS |
| TC-AI-007 | FastAPI 500 | 서버 오류 유도 | ErrorLog, LLMRequestLog failed 저장 | PASS |
| TC-AI-008 | 긴 프롬프트 | 매우 긴 코드/설명 전달 | 길이 제한 또는 안정 처리 | PASS |
| TC-AI-009 | 포맷 오류 응답 | 잘못된 LLM 응답 mock | 기본 오류 메시지 처리 | PASS |
| TC-AI-010 | 인증 누락 | X-Internal-API-Key 없이 호출 | 401 또는 403 처리 | PASS |
> 실측: AI 힌트(1단계) 한국어 텍스트 정상 반환, 오답노트 AI분석 [문제핵심/풀이과정/오답원인/개선사항] 4섹션 출력 확인
---

## 9. RAG 테스트 계획 및 결과

| TC ID | 테스트 항목 | 절차 | 기대 결과 | 결과 |
|---|---|---|---|---|
| TC-RAG-001 | 오답노트 벡터 저장 | 오답노트 저장 후 embed 호출 | ChromaDB 저장, embedding_id 생성 | PASS |
| TC-RAG-002 | WrongNoteVector 저장 | embed 완료 후 postgreSQL DB 확인 | wrong_note_id, embedding_id 저장 | PASS |
| TC-RAG-003 | 유사 오답노트 검색 | 유사 질문 입력 | note_id, source, score 반환 | PASS |
| TC-RAG-004 | user_id 필터 | 다른 사용자 노트 존재 상태에서 검색 | 본인 노트만 반환 | PASS |
| TC-RAG-005 | 검색 결과 없음 | 관련 노트 없는 질문 입력 | 빈 결과 안내 메시지 표시 | PASS |
| TC-RAG-006 | 내 노트에 물어보기 | 자연어 질문 입력 | answer, evidence_note_ids, scores 반환 | PASS |
| TC-RAG-007 | 근거 노트 표시 | RAG 근거 확인 | 근거 표시 | PASS |
| TC-RAG-008 | 질의 로그 저장 | 질문 후 DB 확인 | WrongNoteQueryLog 생성 | PASS |
| TC-RAG-009 | ChromaDB 장애 | ChromaDB 중지 후 검색 | 오류 메시지와 ErrorLog 저장 | PASS |
> 실측: 오답노트 저장 후 ChromaDB에 `embedding_id`, `indexed_at` 정상 기록 확인. 챗봇 질의 시 내 오답노트 기반 RAG 응답 정상 반환
---

## 10. 오답노트 테스트 계획 및 결과

| TC ID | 테스트 항목 | 절차 | 기대 결과 | 결과 |
|---|---|---|---|---|
| TC-WN-001 | 오답노트 작성 화면 | 실패 제출 후 작성 버튼 클릭 | 제출 코드, 오류, 코멘트 폼 표시 | PASS |
| TC-WN-002 | 오답노트 저장 | 코멘트 입력 후 저장 | WrongNote 생성 | PASS |
| TC-WN-003 | 빈 코멘트 검증 | 코멘트 없이 저장 | 검증 오류 표시 | PASS |
| TC-WN-004 | 오답노트 목록 | 목록 화면 접근 | 본인 오답노트만 표시 | PASS |
| TC-WN-005 | 오답노트 상세 | 상세 클릭 | comment, ai_analysis 표시 | PASS |
| TC-WN-006 | 복습 완료 | 복습 완료 버튼 클릭 | is_reviewed=True, reviewed_at 저장 | PASS |
| TC-WN-007 | 복습 포인트 | 복습 완료 처리 | PointLog 10점 생성 | PASS |
> 실측: 오답노트 작성 후 복습 완료 클릭 → 마이페이지에서 `복습 완료`, 포인트 35P 누적 확인

---

## 11. 포인트/미션 테스트 계획 및 결과

| TC ID | 테스트 항목 | 절차 | 기대 결과 | 결과 |
|---|---|---|---|---|
| TC-G-001 | 문제 풀이 완료 포인트 | 코드 실행 완료 | 10점 지급 | PASS |
| TC-G-002 | 정답 포인트 | 정답 제출 | 추가 20점 지급 | PASS |
| TC-G-003 | 오답노트 작성 포인트 | 오답노트 저장 | 15점 지급 | PASS |
| TC-G-004 | 복습 완료 포인트 | 복습 완료 클릭 | 10점 지급 | PASS |
| TC-G-005 | 미션 완료 포인트 | 미션 목표 달성 | 30점 지급 | PASS |
> 실측: 유저 계정 기준 오답노트 작성(+15P) → 복습 완료(+10P) → 마이페이지 35P 최종 누적 확인

---

## 12. 배포 및 운영 테스트 계획 및 결과

| TC ID | 테스트 항목 | 절차 | 기대 결과 | 결과 |
|---|---|---|---|---|
| TC-D-001 | PostgreSQL 연결 | RDS 연결 및 migration 확인 | RDS 연결 성공 | PASS |
| TC-D-002 | Django 기동 | `docker compose -f compose/main.yml up` 실행 | Django 정상 기동 | PASS |
| TC-D-003 | Nginx 프록시 | 브라우저로 `http://3.34.96.25/` 접속 | Django 화면 표시 | PASS |
| TC-D-004 | Static 파일 | CSS/JS 로딩 확인 | 스타일 정상 표시 | PASS |
| TC-D-005 | FastAPI 기동 | AI 힌트 요청으로 내부 연동 확인 | 힌트 응답 반환 | PASS |
| TC-D-006 | ChromaDB 기동 | 오답노트 저장 후 embedding_id 확인 | wrong_note_embeddings 접근 가능 | PASS |
| TC-D-007 | Worker 기동 | 코드 제출 후 채점 결과 확인 | pending job 처리 가능 | PASS |
| TC-D-008 | 재시작 테스트 | docker compose restart | 서비스 재기동 후 정상 접근 | PASS |
| TC-D-009 | 배포 재현성 | GitHub에서 clone 후 `.env` 설정, compose 실행 | 동일 구조로 기동 가능 | PASS |
| TC-D-010 | 보안그룹 | 외부 DB 직접 접근 차단 확인 | 허용 IP 외 접근 불가 | PASS |
> 실측: AWS EC2(`http://3.34.96.25/`) 에서 Nginx→Gunicorn→Django→FastAPI→ChromaDB→Worker 전 컴포넌트 정상 연동 확인. RDS 엔드포인트 `postgres.cbem0yo0kxs5.ap-northeast-2.rds.amazonaws.com` 연결 성공

---


## 13. 비기능 요구사항(권한, 성능, 이슈추적 등) 테스트 계획 및 결과

| TC ID | 테스트 항목 | 절차 | 기대 결과 | 결과 |
|---|---|---|---|---|
| NF-01 | 보안(인증권한) | 비로그인 접근 → 로그인 페이지 리다이렉트(@login_required) | 리다이렉트 연결 성공 | PASS |
| NF-02 | RAG 격리 | user_id 기반 서로 다른 계정의 검색 결과 제공 금지 | 검색 불가 확인 | PASS |
| NF-03 | 내부 API 보안 | X-Internal-API-Key 없이 FastAPI 직접 호출 | 403 에러 처리 표시 | PASS |
| NF-04 | 요청 추적(X-Request-ID) | `request_id` 컬럼에 UUID 값 저장 여부| UUID 저장 확인 | PASS |
| NF-05 | 코드 실행 격리 | 무한루프 시 처리방법 |  5초 후 timeout | PASS |
| NF-06 | 응답 안정성 (LLMCallError) | FastAPI 오류 시 Django 레벨 응답 | 500 아닌 안전 응답 처리 | PASS |
| NF-07 | 배포 재현성 | 배포재현성(TC-D-009) 확인 | 동일 구조 기동 확인 | PASS |
| NF-08 | 운영 로그 Admin 확인 | LLM, FastAPI 로그 이슈추적 | 이슈추적 상태 목록 확인 | PASS |
| NF-09 | 반응형 UI | 반응형 레이아웃 확인 | F12 레이아웃 변환, 버튼 접근 확인 | PASS |
| NF-10 | 서비스 분리 | EC2 SSH 독립 | 서비스별 서버 분리 확인 | PASS |


| TC ID | 항목 | 절차 | 합격 기준 | 결과 | 실측값 |
|---|---|---|---|---|---|
| TC-P-001 | Django 응답시간 | `/problems/` 5회 접속 후 평균 측정 | 평균 < 1초 | PASS | 실측 평균: 0.056초 (홈 0.034초, 마이페이지 0.051초) |
| TC-P-002 | Worker 실행시간 | 정답 코드 제출 후 결과까지 시간 측정 | < 10초 | PASS | 실측 40ms (채점 포함) |
| TC-P-003 | AI 힌트 응답시간 | 힌트 버튼 클릭 후 응답까지 측정 | < 10초 (API Key 설정 시) | PASS | OpenAI 응답 정상, 수 초 이내 |
| TC-P-004 | 코드 강제 종료 | 무한루프 코드 제출 | 5초 이내 timeout 처리 | PASS | `CODE_TIMEOUT_SEC=5` 설정 동작 확인 |
| TC-P-005 | RAG 검색 응답 | 챗봇 질의 후 응답 시간 측정 | < 15초 | PASS | ChromaDB 검색 + LLM 응답 정상 완료 |

---

## 14. 테스트 결과 요약

| 테스트 구분 | 테스트 수 | PASS | FAIL | 결과 |
|---|---:|---:|---:|---|
| 기능 테스트 | 10 | 10 | 0 | PASS |
| 코드 실행 테스트 | 10 | 10 | 0 | PASS |
| LLM 연동 테스트 | 10 | 10 | 0 | PASS |
| RAG 테스트 | 9 | 9 | 0 | PASS |
| 오답노트 테스트 | 7 | 7 | 0 | PASS |
| 포인트/미션 테스트 | 5 | 5 | 0 | PASS |
| 배포/운영 테스트 | 10 | 10 | 0 | PASS |
| 비기능(NF) | 10 | 10 | 0 | PASS |
| 성능(TC-P) | 5 | 5 | 0 | PASS |
| 합계 | 76 | 76 | 0 | PASS |

---

## 15. 최종 검증 시나리오

### 사용자 핵심 플로우

```text
1. 회원가입
2. 로그인
3. 문제 목록 조회
4. 문제 선택
5. 코드 작성 실행 및 제출
6. Docker Worker 실행 결과 확인
7. AI 힌트 요청
8. 오답 발생 시 오답노트 작성
9. AI 오답 분석 확인
10. 오답노트 저장 및 ChromaDB 인덱싱
11. 내 노트에 물어보기 질문
12. RAG 답변과 근거 노트 확인
13. 마이페이지에서 학습 현황 확인
```

### 최종 결과(작성 완료)

| 항목 | 결과 | 비고 |
|---|---|---|
| 핵심 사용자 흐름 | PASS | 회원가입~RAG 복습까지 전 단계 정상 완료 |
| Django CRUD | PASS | 문제/제출/오답노트/포인트 DB 정상 저장 |
| FastAPI AI 연동 | PASS | 힌트 1단계 한국어 텍스트 즉시 반환 확인 |
| ChromaDB RAG 검색 | PASS | 오답노트 저장 즉시 인덱싱, 챗봇 RAG 정상 동작 |
| Docker Worker 코드 실행 | PASS | Python 코드 격리 실행, 40ms 이내 채점 결과 반환 |
| PostgreSQL 저장 | PASS | RDS(ap-northeast-2) 연결 안정적, 986개 문제 데이터 탑재 |
| 로그 기록 | PASS | LLMRequestLog, WrongNoteQueryLog 정상 저장 확인 |
| AWS 배포 재현성 | PASS | GitHub clone → `.env` 설정 → compose 실행으로 재현 가능 |


---