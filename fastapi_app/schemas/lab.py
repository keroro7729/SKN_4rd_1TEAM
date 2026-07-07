"""AI 실험 랩 스키마 (/ai/lab/*)."""
from typing import List

from pydantic import BaseModel

from schemas.common import InternalResponse, LLMStatus


class LabGraphResponse(InternalResponse):
    status: LLMStatus = LLMStatus.success
    agents: List[dict] = []
    nodes: dict = {}


class LabRunRequest(BaseModel):
    node_id: str
    inputs: dict = {}
    system: str = ""   # 프롬프트 주입(비우면 노드 기본 system)
    user: str = ""     # 프롬프트 주입(비우면 템플릿+inputs 렌더)
    model: str = ""


class LabRunResponse(InternalResponse):
    status: LLMStatus = LLMStatus.success
    node_id: str = ""
    output: str = ""
    system_used: str = ""
    user_used: str = ""
    model: str = ""
    latency_ms: int = 0
