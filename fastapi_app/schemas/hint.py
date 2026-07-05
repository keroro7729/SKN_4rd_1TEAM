"""AI 힌트 스키마 (F-05 / LLM-01)."""
from pydantic import BaseModel, Field

from schemas.common import InternalResponse, LLMStatus


class HintRequest(BaseModel):
    user_id: int
    problem_id: int
    user_code: str = ""
    hint_level: int = Field(1, ge=1, le=3, description="1:접근 2:풀이과정 3:코드가이드")


class HintResponse(InternalResponse):
    status: LLMStatus = LLMStatus.success
    hint_level: int
    content: str
