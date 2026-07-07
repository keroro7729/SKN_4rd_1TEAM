"""오답노트 RAG 스키마 (F-06/07/08/14, LLM-02/03/04)."""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from schemas.common import Evidence, InternalResponse, LLMStatus


# --- /ai/wrong-note/search ---
class WrongNoteSearchRequest(BaseModel):
    user_id: int
    problem_id: int
    wrong_note_id: Optional[int] = None  # 자기 자신 제외용
    submission_id: Optional[int] = None
    problem_title: Optional[str] = None
    category: str = ""            # v1: topic 청크(카테고리) 추가 고려
    tags: List[str] = Field(default_factory=list)  # v1: topic 청크(알고리즘 분류)
    user_comment: str = ""        # v1: 회고 = 검색 쿼리 신호
    submitted_code: str = ""      # v1: 검색 쿼리에서 제외(노이즈)


class WrongNoteSearchResponse(InternalResponse):
    status: LLMStatus = LLMStatus.success
    results: List[Evidence] = Field(default_factory=list)


# --- /ai/wrong-note/analyze ---
class WrongNoteAnalyzeRequest(BaseModel):
    wrong_note_id: Optional[int] = None
    user_id: int
    code: str = ""
    comment: str = ""
    problem_title: str = ""
    tags: List[str] = Field(default_factory=list)
    problem_statement: str = ""  # 문제 설명(문제핵심/풀이과정 품질 향상용)
    coding_state: str = ""  # AI 참고: 사용자 코딩 상태 컨텍스트(사용자 비노출)


class WrongNoteAnalyzeResponse(InternalResponse):
    status: LLMStatus = LLMStatus.success
    problem_core: str = ""       # 문제 핵심(문제 이해)
    solution: str = ""           # 풀이 과정(정석 접근법)
    cause: str = ""              # 오답 원인(코드에서 잘못된 부분)
    improvement: str = ""        # 개선사항(구체적 개선/재시도 방법)
    ai_feedback: str = ""        # AI 자유 형식 피드백
    next_checklist: List[str] = Field(default_factory=list)  # 다음 풀이 전 체크(2~4)
    evidence: List[Evidence] = Field(default_factory=list)


# --- /ai/wrong-note/embed ---
class WrongNoteEmbedRequest(BaseModel):
    wrong_note_id: int
    user_id: int
    problem_title: Optional[str] = None
    category: str = ""                                   # v1: topic 청크
    algo_tags: List[str] = Field(default_factory=list)   # v1: topic 청크
    sections: Dict[str, str] = Field(default_factory=dict)  # v1: 회고+AI코멘트 섹션들
    content: str = ""                                    # v0 호환(미사용)


class WrongNoteEmbedResponse(InternalResponse):
    status: LLMStatus = LLMStatus.success
    embedding_id: Optional[str] = None
    indexed_at: Optional[str] = None
    chunk_count: int = 0


# --- /ai/wrong-note/ask (내 노트에 물어보기) ---
class NoteAskRequest(BaseModel):
    user_id: int
    question: str


class NoteAskResponse(InternalResponse):
    status: LLMStatus = LLMStatus.success
    answer: str = ""
    evidence_note_ids: List[int] = Field(default_factory=list)
    scores: List[float] = Field(default_factory=list)
