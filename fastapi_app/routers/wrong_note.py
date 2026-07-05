"""오답노트 RAG API (/ai/wrong-note/*)."""
from fastapi import APIRouter, Depends

import config
from schemas.common import LLMStatus
from schemas.wrong_note import (
    NoteAskRequest,
    NoteAskResponse,
    WrongNoteAnalyzeRequest,
    WrongNoteAnalyzeResponse,
    WrongNoteEmbedRequest,
    WrongNoteEmbedResponse,
    WrongNoteSearchRequest,
    WrongNoteSearchResponse,
)
from logging_setup import log_ai_event
from services import chroma, llm
from services.security import verify_internal

router = APIRouter(prefix="/ai/wrong-note", tags=["wrong-note"])


@router.post("/search", response_model=WrongNoteSearchResponse)
async def search(req: WrongNoteSearchRequest, ctx=Depends(verify_internal)):
    """유사 오답노트 검색 (user_id 필터 필수)."""
    query = f"{req.problem_title or ''} {req.user_comment} {' '.join(req.tags)}"
    results = chroma.search_user_notes(req.user_id, query)
    status = LLMStatus.success if results else LLMStatus.empty
    log_ai_event(
        "rag_search", user_id=req.user_id, top_k=config.RAG_TOP_K, hits=len(results)
    )
    return WrongNoteSearchResponse(
        request_id=ctx["request_id"],
        status=status,
        results=results,
    )


@router.post("/analyze", response_model=WrongNoteAnalyzeResponse)
async def analyze(req: WrongNoteAnalyzeRequest, ctx=Depends(verify_internal)):
    """오답 원인 분석."""
    result = await llm.analyze_wrong_note(req.code, req.comment, evidence=[])
    log_ai_event("analyze", model=config.OPENAI_MODEL)
    return WrongNoteAnalyzeResponse(
        request_id=ctx["request_id"],
        status=LLMStatus.success,
        **result,
    )


@router.post("/embed", response_model=WrongNoteEmbedResponse)
async def embed(req: WrongNoteEmbedRequest, ctx=Depends(verify_internal)):
    """저장된 오답노트를 ChromaDB에 인덱싱 (F-14)."""
    out = chroma.embed_note(
        req.user_id,
        req.wrong_note_id,
        req.content,
        problem_title=req.problem_title,
    )
    return WrongNoteEmbedResponse(
        request_id=ctx["request_id"],
        status=LLMStatus.success,
        **out,
    )


@router.post("/ask", response_model=NoteAskResponse)
async def ask(req: NoteAskRequest, ctx=Depends(verify_internal)):
    """내 노트에 물어보기 (본인 노트만, 근거 note_id 포함)."""
    evidence = chroma.search_user_notes(req.user_id, req.question)
    answer = await llm.answer_from_notes(req.question, evidence)
    log_ai_event("note_ask", user_id=req.user_id, hits=len(evidence))
    return NoteAskResponse(
        request_id=ctx["request_id"],
        status=LLMStatus.success if evidence else LLMStatus.empty,
        answer=answer,
        evidence_note_ids=[e.note_id for e in evidence],
        scores=[e.score for e in evidence],
    )
