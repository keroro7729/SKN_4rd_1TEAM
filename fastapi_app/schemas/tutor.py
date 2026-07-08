"""미니튜터 챗 스키마 (/ai/tutor/chat).

대화 컨텍스트 + 현재 활동 + 코딩 상태 + 최근 오답(RAG) 기반 간단 문답.
FastAPI는 stateless — 대화 이력/컨텍스트는 Django가 payload로 넘긴다.
"""
from typing import List, Optional

from pydantic import BaseModel, Field

from schemas.common import Evidence, InternalResponse, LLMStatus


class TutorTurn(BaseModel):
    role: str = "user"      # "user" | "assistant"
    content: str = ""


class TutorNote(BaseModel):
    note_id: Optional[int] = None
    title: str = ""
    error_pattern: str = ""
    days_ago: Optional[int] = None
    summary: str = ""


class TutorChatRequest(BaseModel):
    user_id: int
    question: str
    history: List[TutorTurn] = Field(default_factory=list)   # 대화 컨텍스트(최근 N턴)
    coding_state: str = ""                                    # 사용자 코딩 상태(내부 참고)
    activity: str = ""                                        # 현재 활동(페이지/문제)
    recent_notes: List[TutorNote] = Field(default_factory=list)  # 최근 7~30일 오답 기록
    recent_window_days: int = 30


class TutorChatResponse(InternalResponse):
    status: LLMStatus = LLMStatus.success
    answer: str = ""
    used_notes: List[Evidence] = Field(default_factory=list)  # RAG로 참고한 노트(근거)
