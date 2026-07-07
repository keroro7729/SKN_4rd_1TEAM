"""코딩 상태 요약 스키마 (/ai/coding-state/summarize)."""
from typing import List

from pydantic import BaseModel

from schemas.common import InternalResponse, LLMStatus


class CodingStateRequest(BaseModel):
    user_id: int
    stats: dict = {}  # Django 가 집계한 학습 통계


class CodingStateResponse(InternalResponse):
    status: LLMStatus = LLMStatus.success
    summary: str = ""
    level: str = ""
    strengths: List[str] = []
    weaknesses: List[str] = []
    recurring_mistakes: List[str] = []
    recommended_focus: List[str] = []
    model: str = ""
