"""STEP-02 데이터 모델 공용 choices/상수 (지시문 v0.7 §7.1 확정값).

⚠️ 문자열 값은 임의 변경 금지 — Django/FastAPI/Worker 의 상태값이 이 값에 의존한다.
   (예: ExecutionJob.job_type 은 'code_run' — worker 스캐폴딩의 'code_execution' 은 STEP-04 에서 정합)
"""

DIFFICULTY_CHOICES = [
    ("basic", "언어기초"),
    ("beginner", "초급"),
    ("intermediate", "중급"),
    ("advanced", "고급"),
]

SUBMISSION_RESULT_CHOICES = [
    ("pending", "대기"),
    ("success", "정답"),
    ("wrong", "오답"),
    ("error", "오류"),
    ("timeout", "시간초과"),
]

SUBMISSION_TYPE_CHOICES = [
    ("run", "실행"),
    ("submit", "최종제출"),
]

JOB_TYPE_CHOICES = [
    ("code_run", "코드실행"),
    ("code_submit", "코드제출"),
    ("code_eval", "코드평가"),  # 시스템: 코드+입력을 실행해 출력만 캡처(비교 없음) — TC 생성 에이전트
]

JOB_STATUS_CHOICES = [
    ("pending", "대기"),
    ("running", "실행중"),
    ("success", "성공"),
    ("failed", "실패"),
    ("timeout", "시간초과"),
]

LLM_REQUEST_TYPE_CHOICES = [
    ("hint", "힌트"),
    ("wrong_note_search", "오답검색"),
    ("wrong_note_analyze", "오답분석"),
    ("wrong_note_embed", "오답임베딩"),
    ("note_ask", "내노트질의"),
    ("testcase_gen", "테스트케이스생성"),
    ("testcase_fix", "정답코드수정"),
    ("coding_state", "코딩상태요약"),
    ("ai_lab", "AI실험랩"),
    ("tutor_chat", "미니튜터"),
]

LLM_STATUS_CHOICES = [
    ("pending", "대기"),
    ("processing", "처리중"),
    ("success", "성공"),
    ("failed", "실패"),
    ("timeout", "시간초과"),
    ("empty", "결과없음"),
]

WRONG_NOTE_STATUS_CHOICES = [
    ("draft", "작성중"),
    ("completed", "완료"),
    ("indexed", "인덱싱완료"),
    ("index_failed", "인덱싱실패"),
]

TEST_COMPARE_MODE_CHOICES = [
    ("exact", "완전일치"),
    ("line_trim", "줄단위공백정리"),
    ("float", "부동소수점오차허용"),
]

MISSION_STATUS_CHOICES = [
    ("not_started", "미시작"),
    ("in_progress", "진행중"),
    ("completed", "완료"),
]

POINT_ACTION_TYPE_CHOICES = [
    ("submission_created", "문제풀이완료"),
    ("solve_success", "정답처리"),
    ("wrongnote_completed", "오답노트작성"),
    ("review_completed", "복습완료"),
    ("daily_mission_completed", "미션완료"),
    ("admin_adjustment", "관리자조정"),
]

POINT_REWARD_MAP = {
    "submission_created": 10,
    "solve_success": 20,
    "wrongnote_completed": 15,
    "review_completed": 10,
    "daily_mission_completed": 30,
}

ERROR_SOURCE_CHOICES = [
    ("django", "Django"),
    ("fastapi", "FastAPI"),
    ("worker", "Worker"),
    ("chromadb", "ChromaDB"),
    ("openai", "OpenAI"),
    ("deploy", "배포"),
]
