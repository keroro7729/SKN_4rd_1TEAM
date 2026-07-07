"""미니튜터 챗 API (/ai/tutor/*).

대화 컨텍스트 + 현재 활동 + 코딩 상태 + 최근 오답(RAG) 기반 간단 문답.
RAG(ChromaDB) + LLM(OpenAI) 모두 FastAPI 도메인. Django는 컨텍스트만 payload로 전달.
"""
from fastapi import APIRouter, Depends

import config
from logging_setup import log_ai_event
from schemas.common import LLMStatus
from schemas.tutor import TutorChatRequest, TutorChatResponse
from services import chroma, llm
from services.llm import LLMCallError, LLMNotImplementedError
from services.security import verify_internal

router = APIRouter(prefix="/ai/tutor", tags=["tutor"])


@router.post("/chat", response_model=TutorChatResponse)
async def chat(req: TutorChatRequest, ctx=Depends(verify_internal)):
    """미니튜터 문답. 질문으로 유사 오답노트(RAG)를 끌어와 개인화 답변 생성."""
    # 질문 기반 RAG (사용자 노트 스코프). 실패해도 답변은 진행.
    try:
        evidence = chroma.search_user_notes(req.user_id, req.question)
    except Exception:  # noqa: BLE001 - 검색 실패가 대화를 막지 않도록
        evidence = []

    try:
        answer = await llm.tutor_reply(
            req.question,
            req.history,
            coding_state=req.coding_state,
            activity=req.activity,
            recent_notes=req.recent_notes,
            evidence=evidence,
            window_days=req.recent_window_days,
        )
    except (LLMNotImplementedError, LLMCallError) as exc:
        msg = "not_implemented" if isinstance(exc, LLMNotImplementedError) else str(exc)
        log_ai_event("tutor_chat", user_id=req.user_id, status="failed", rag_hits=len(evidence))
        return TutorChatResponse(
            request_id=ctx["request_id"],
            status=LLMStatus.failed,
            message=msg,
            answer="",
        )

    log_ai_event(
        "tutor_chat", user_id=req.user_id, model=config.OPENAI_MODEL,
        history_turns=len(req.history), rag_hits=len(evidence),
        recent_notes=len(req.recent_notes),
    )
    return TutorChatResponse(
        request_id=ctx["request_id"],
        status=LLMStatus.success if answer else LLMStatus.empty,
        answer=answer,
        used_notes=evidence,
    )
