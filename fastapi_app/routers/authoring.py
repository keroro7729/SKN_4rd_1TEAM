"""테스트케이스 생성 에이전트 API (/ai/authoring/*)."""
from fastapi import APIRouter, Depends

from schemas.authoring import (
    AuthoringFixRequest,
    AuthoringFixResponse,
    AuthoringGenerateRequest,
    AuthoringGenerateResponse,
)
from schemas.common import LLMStatus
from services import authoring
from services.security import verify_internal

router = APIRouter(prefix="/ai/authoring", tags=["authoring"])


@router.post("/generate", response_model=AuthoringGenerateResponse)
async def generate(req: AuthoringGenerateRequest, ctx=Depends(verify_internal)):
    """정답코드 + 제너레이터 + 엣지/시간 입력 생성 (LLM)."""
    rid = ctx["request_id"]
    try:
        out = await authoring.generate(req.model_dump())
        return AuthoringGenerateResponse(request_id=rid, status=LLMStatus.success, **out)
    except authoring.AuthoringError as exc:
        return AuthoringGenerateResponse(
            request_id=rid, status=LLMStatus.failed, message=str(exc)
        )


@router.post("/fix", response_model=AuthoringFixResponse)
async def fix(req: AuthoringFixRequest, ctx=Depends(verify_internal)):
    """실행 오류/불일치를 바탕으로 정답코드 수정 (디버깅 루프)."""
    rid = ctx["request_id"]
    try:
        out = await authoring.fix(
            req.model_dump(), req.solution_code, req.error, req.sample_input
        )
        return AuthoringFixResponse(request_id=rid, status=LLMStatus.success, **out)
    except authoring.AuthoringError as exc:
        return AuthoringFixResponse(
            request_id=rid, status=LLMStatus.failed, message=str(exc)
        )
