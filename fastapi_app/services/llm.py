"""OpenAI LLM 연동 (스캐폴딩 스텁).

실제 구현은 STEP-06. 지금은 인터페이스와 반환 형태만 고정한다.
"""
import config
from schemas.common import Evidence


async def generate_hint(problem_id: int, user_code: str, hint_level: int) -> str:
    """1~3단계 힌트 생성. 정답 직접 노출 지양."""
    # TODO(STEP-06): OpenAI API 호출 + LangGraph 힌트 에이전트 연결
    return (
        f"[stub] {hint_level}단계 힌트입니다. "
        f"(problem_id={problem_id}, model={config.OPENAI_MODEL})"
    )


async def analyze_wrong_note(code: str, comment: str, evidence: list[Evidence]) -> dict:
    """오답 분석: 문제 핵심 / 오답 원인 / 풀이 과정 / 주의사항."""
    # TODO(STEP-06): 프롬프트(prompts.py) + OpenAI 호출
    return {
        "problem_core": "[stub] 문제 핵심",
        "cause": "[stub] 오답 원인",
        "solution": "[stub] 풀이 과정",
        "caution": "[stub] 주의사항",
    }


async def answer_from_notes(question: str, evidence: list[Evidence]) -> str:
    """내 노트 질의응답. 근거 없는 단정 금지."""
    # TODO(STEP-06): 근거 노트 기반 RAG 답변 생성
    if not evidence:
        return "검색된 근거 오답노트가 없습니다."
    note_ids = ", ".join(str(item.note_id) for item in evidence)
    return f"[stub] 근거 오답노트 note_id {note_ids}를 바탕으로 한 답변입니다."
