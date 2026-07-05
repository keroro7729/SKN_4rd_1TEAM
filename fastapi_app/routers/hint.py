"""AI 힌트 API (/ai/hint)."""
from fastapi import APIRouter, Depends

import config
from logging_setup import log_ai_event
from schemas.common import LLMStatus
from schemas.hint import HintRequest, HintResponse
from services import llm
from services.llm import LLMNotImplementedError
from services.security import verify_internal

router = APIRouter(prefix="/ai", tags=["hint"])


@router.post("/hint", response_model=HintResponse)
async def create_hint(req: HintRequest, ctx=Depends(verify_internal)) -> HintResponse:
    try:
        content = await llm.generate_hint(req.problem_id, req.user_code, req.hint_level)
    except LLMNotImplementedError:
        log_ai_event(
            "hint",
            problem_id=req.problem_id,
            hint_level=req.hint_level,
            model=config.OPENAI_MODEL,
            status="not_implemented",
        )
        return HintResponse(
            request_id=ctx["request_id"],
            status=LLMStatus.failed,
            message="not_implemented",
            hint_level=req.hint_level,
            content="",
        )
    log_ai_event(
        "hint",
        problem_id=req.problem_id,
        hint_level=req.hint_level,
        model=config.OPENAI_MODEL,
    )
    return HintResponse(
        request_id=ctx["request_id"],
        status=LLMStatus.success,
        hint_level=req.hint_level,
        content=content,
    )
