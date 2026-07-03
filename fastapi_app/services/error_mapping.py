"""LLM 예외 -> 사용자 안내 메시지 매핑 (LLM-01~05).

Timeout, FastAPI 500, OpenAI 오류, 응답 포맷 오류, ChromaDB 실패, 근거 부족 등을
사용자에게 보일 메시지로 변환한다. error_logs 저장은 Django 측에서 수행.
"""

USER_MESSAGES = {
    "timeout": "AI 응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.",
    "openai_error": "AI 서비스 호출에 실패했습니다. 잠시 후 다시 시도해 주세요.",
    "format_error": "AI 응답 형식 오류가 발생했습니다. 다시 시도해 주세요.",
    "chroma_error": "유사 오답노트 검색에 실패했습니다. 노트는 저장할 수 있습니다.",
    "empty": "유사한 오답노트가 없습니다.",
    "not_enough_evidence": "근거가 부족하여 정확히 답변드리기 어렵습니다.",
}


def to_user_message(kind: str) -> str:
    return USER_MESSAGES.get(kind, "요청 처리 중 오류가 발생했습니다.")
