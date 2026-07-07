"""AI 실험 랩 API (/ai/lab/*). 그래프 조회 + 단일 노드 실행(프롬프트 주입)."""
from fastapi import APIRouter, Depends

from schemas.common import LLMStatus
from schemas.lab import LabGraphResponse, LabRunRequest, LabRunResponse
from services import lab
from services.security import verify_internal

router = APIRouter(prefix="/ai/lab", tags=["lab"])


@router.post("/graph", response_model=LabGraphResponse)
async def graph(ctx=Depends(verify_internal)):
    """에이전트 그래프(노드/에지) + 노드별 기본 프롬프트/샘플."""
    g = lab.get_graph()
    return LabGraphResponse(
        request_id=ctx["request_id"], status=LLMStatus.success,
        agents=g["agents"], nodes=g["nodes"],
    )


@router.post("/run", response_model=LabRunResponse)
async def run(req: LabRunRequest, ctx=Depends(verify_internal)):
    """단일 LLM 노드를 (주입 프롬프트로) 실행."""
    try:
        out = await lab.run_node(
            req.node_id, req.inputs, system=req.system, user=req.user, model=req.model
        )
    except lab.LabError as exc:
        return LabRunResponse(
            request_id=ctx["request_id"], status=LLMStatus.failed,
            message=str(exc), node_id=req.node_id,
        )
    return LabRunResponse(request_id=ctx["request_id"], status=LLMStatus.success, **out)
