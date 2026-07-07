"""AI 힌트 스키마 (F-05 / LLM-01)."""
from pydantic import BaseModel, Field

from schemas.common import InternalResponse, LLMStatus


class HintRequest(BaseModel):
    user_id: int
    problem_id: int
    user_code: str = ""
    hint_level: int = Field(1, ge=1, le=3, description="1:접근 2:풀이과정 3:코드가이드")
    # Django 가 enrich 해서 전달 (FastAPI 는 DB 미접근)
    problem_title: str = ""
    description: str = ""
    constraints: str = ""
    difficulty: str = ""
    level: str = ""          # 사용자 추정 수준(입문/초급/중급/고급)
    coding_state: str = ""   # AI 참고: 사용자 코딩 상태 컨텍스트


class HintResponse(InternalResponse):
    status: LLMStatus = LLMStatus.success
    hint_level: int
    content: str
