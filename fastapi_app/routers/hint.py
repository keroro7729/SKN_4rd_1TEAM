"""AI 힌트 API (/ai/hint)."""
from fastapi import APIRouter, Depends

from schemas.common import LLMStatus
from schemas.hint import HintRequest, HintResponse
from services import llm
from services.security import verify_internal

router = APIRouter(prefix="/ai", tags=["hint"])


@router.post("/hint", response_model=HintResponse)
async def create_hint(req: HintRequest, _=Depends(verify_internal)) -> HintResponse:
    content = await llm.generate_hint(req.problem_id, req.user_code, req.hint_level)
    return HintResponse(
        status=LLMStatus.success,
        hint_level=req.hint_level,
        content=content,
    )
