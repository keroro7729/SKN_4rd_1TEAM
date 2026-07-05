"""OpenAI/LangGraph integration boundary.

This module intentionally does not return temporary success text. Until the
AI/RAG 담당자가 실제 OpenAI prompt and LangGraph flow를 연결하면 callers must
receive an explicit not_implemented status through the routers.
"""

from schemas.common import Evidence


class LLMNotImplementedError(NotImplementedError):
    """Raised when the AI generation layer has not been implemented yet."""


async def generate_hint(problem_id: int, user_code: str, hint_level: int) -> str:
    """Generate a level 1-3 hint without directly revealing the answer."""
    raise LLMNotImplementedError("not_implemented")


async def analyze_wrong_note(code: str, comment: str, evidence: list[Evidence]) -> dict:
    """Analyze a wrong note into core/cause/solution/caution sections."""
    raise LLMNotImplementedError("not_implemented")


async def answer_from_notes(question: str, evidence: list[Evidence]) -> str:
    """Generate a grounded answer from the user's wrong-note evidence."""
    raise LLMNotImplementedError("not_implemented")
