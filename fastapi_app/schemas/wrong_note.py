"""오답노트 RAG 스키마 (F-06/07/08/14, LLM-02/03/04)."""
from typing import List, Optional

from pydantic import BaseModel, Field

from schemas.common import Evidence, InternalResponse, LLMStatus


# --- /ai/wrong-note/search ---
class WrongNoteSearchRequest(BaseModel):
    user_id: int
    problem_id: int
    submission_id: Optional[int] = None
    problem_title: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    user_comment: str = ""
    submitted_code: str = ""


class WrongNoteSearchResponse(InternalResponse):
    status: LLMStatus = LLMStatus.success
    results: List[Evidence] = Field(default_factory=list)


# --- /ai/wrong-note/analyze ---
class WrongNoteAnalyzeRequest(BaseModel):
    wrong_note_id: Optional[int] = None
    user_id: int
    code: str = ""
    comment: str = ""


class WrongNoteAnalyzeResponse(InternalResponse):
    status: LLMStatus = LLMStatus.success
    problem_core: str = ""      # 문제 핵심
    cause: str = ""             # 오답 원인
    solution: str = ""          # 풀이 과정
    caution: str = ""           # 주의사항
    evidence: List[Evidence] = Field(default_factory=list)


# --- /ai/wrong-note/embed ---
class WrongNoteEmbedRequest(BaseModel):
    wrong_note_id: int
    user_id: int
    content: str
    problem_title: Optional[str] = None


class WrongNoteEmbedResponse(InternalResponse):
    status: LLMStatus = LLMStatus.success
    embedding_id: Optional[str] = None
    indexed_at: Optional[str] = None


# --- /ai/wrong-note/ask (내 노트에 물어보기) ---
class NoteAskRequest(BaseModel):
    user_id: int
    question: str


class NoteAskResponse(InternalResponse):
    status: LLMStatus = LLMStatus.success
    answer: str = ""
    evidence_note_ids: List[int] = Field(default_factory=list)
    scores: List[float] = Field(default_factory=list)



# --- /wrongnotes/* compatibility endpoints ---
class WrongNotesIndexRequest(BaseModel):
    wrongnote_id: int
    user_id: int
    problem_id: Optional[int] = None
    problem_title: str = ""
    algorithm_keywords: List[str] = Field(default_factory=list)
    wrong_code: str = ""
    error_message: str = ""
    user_comment: str = ""
    created_at: Optional[str] = None


class WrongNotesIndexResponse(BaseModel):
    ok: bool = True
    wrongnote_id: int
    indexed: bool = False
    error: Optional[str] = None


class WrongNotesSimilarRequest(BaseModel):
    user_id: int
    wrongnote_id: Optional[int] = None
    query: str = ""
    limit: int = 3


class WrongNotesSimilarItem(BaseModel):
    wrongnote_id: int
    problem_title: str = ""
    algorithm_keywords: List[str] = Field(default_factory=list)
    similarity_reason: str = ""
    score: float = 0.0


class WrongNotesSimilarResponse(BaseModel):
    ok: bool = True
    items: List[WrongNotesSimilarItem] = Field(default_factory=list)
    error: Optional[str] = None


class WrongNotesAnalyzeRequest(BaseModel):
    user_id: int
    wrongnote_id: int
    problem_title: str = ""
    algorithm_keywords: List[str] = Field(default_factory=list)
    wrong_code: str = ""
    error_message: str = ""
    user_comment: str = ""


class WrongNotesAnalyzeResponse(BaseModel):
    ok: bool = True
    analysis: dict = Field(default_factory=dict)
    error: Optional[str] = None
