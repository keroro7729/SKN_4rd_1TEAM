"""코딩 상태 요약 API (POST /ai/coding-state/summarize)."""
from fastapi import APIRouter, Depends

from schemas.coding_state import CodingStateRequest, CodingStateResponse
from schemas.common import LLMStatus
from services import coding_state
from services.security import verify_internal

router = APIRouter(prefix="/ai/coding-state", tags=["coding-state"])


@router.post("/summarize", response_model=CodingStateResponse)
async def summarize(req: CodingStateRequest, ctx=Depends(verify_internal)):
    rid = ctx["request_id"]
    try:
        out = await coding_state.summarize(req.stats)
    except coding_state.CodingStateError as exc:
        return CodingStateResponse(request_id=rid, status=LLMStatus.failed, message=str(exc))
    return CodingStateResponse(request_id=rid, status=LLMStatus.success, **out)
