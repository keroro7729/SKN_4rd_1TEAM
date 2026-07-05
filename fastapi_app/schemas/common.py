"""공통 Pydantic 스키마."""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class LLMStatus(str, Enum):
    """LLM 처리 상태 (F-13). Django llm_request_logs.status와 동기화."""

    success = "success"
    failed = "failed"
    timeout = "timeout"
    empty = "empty"


class Evidence(BaseModel):
    """RAG 근거 노트 1건. note_id/source/score 필수 (지시문 규칙)."""

    note_id: int
    source: str = "wrong_note"
    score: float
    title: Optional[str] = None


class InternalResponse(BaseModel):
    """내부 API 공통 응답 추적 필드."""

    request_id: Optional[str] = Field(default=None, description="X-Request-ID")
    message: Optional[str] = None
