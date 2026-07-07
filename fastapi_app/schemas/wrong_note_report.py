"""오답노트 AI 리포트 스키마 (/ai/wrong-note/report).

설계: llm_wiki/9. WOOKS_CODING_오답노트_AI리포트_useflow_및_RAG설계_v0.1.md
"""
from typing import List, Optional

from pydantic import BaseModel, Field

from schemas.common import Evidence, InternalResponse, LLMStatus


class WrongNoteReportRequest(BaseModel):
    user_id: int
    wrong_note_id: Optional[int] = None  # 자기 자신 제외용
    problem_id: Optional[int] = None
    problem_title: str = ""
    difficulty: str = ""
    tags: List[str] = []
    submitted_code: str = ""
    result: str = ""
    error_message: str = ""
    user_comment: str = ""  # 사용자 회고


class ReportBody(BaseModel):
    retrospection_feedback: str = ""       # 회고 피드백
    missed_points: List[str] = []          # 놓친 부분
    learning_direction: List[str] = []     # 학습 방향
    summary: dict = Field(default_factory=dict)  # {problem_core, cause}


class WrongNoteReportResponse(InternalResponse):
    status: LLMStatus = LLMStatus.success
    report: ReportBody = Field(default_factory=ReportBody)
    stage1_evidence: List[Evidence] = []   # ① 회고기반 1차 리트리빙
    stage2_evidence: List[Evidence] = []   # ③ 전체기반 최종 리트리빙
