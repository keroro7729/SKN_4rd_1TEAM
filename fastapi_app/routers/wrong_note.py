"""Wrong-note RAG APIs."""
from fastapi import APIRouter, Depends

import config
from logging_setup import log_ai_event
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
    WrongNotesAnalyzeRequest,
    WrongNotesAnalyzeResponse,
    WrongNotesIndexRequest,
    WrongNotesIndexResponse,
    WrongNotesSimilarItem,
    WrongNotesSimilarRequest,
    WrongNotesSimilarResponse,
)
from services import chroma, llm
from services.llm import LLMNotImplementedError
from services.security import verify_internal

router = APIRouter(prefix="/ai/wrong-note", tags=["wrong-note"])
compat_router = APIRouter(prefix="/wrongnotes", tags=["wrongnotes-compat"])


@router.post("/search", response_model=WrongNoteSearchResponse)
async def search(req: WrongNoteSearchRequest, ctx=Depends(verify_internal)):
    """Search similar wrong notes with the required user_id metadata filter."""
    query = f"{req.problem_title or ''} {req.user_comment} {' '.join(req.tags)}"
    results = chroma.search_user_notes(req.user_id, query)
    status = LLMStatus.success if results else LLMStatus.empty
    log_ai_event("rag_search", user_id=req.user_id, top_k=config.RAG_TOP_K, hits=len(results))
    return WrongNoteSearchResponse(
        request_id=ctx["request_id"],
        status=status,
        results=results,
    )


@router.post("/analyze", response_model=WrongNoteAnalyzeResponse)
async def analyze(req: WrongNoteAnalyzeRequest, ctx=Depends(verify_internal)):
    """Analyze a wrong note through the LLM boundary."""
    try:
        result = await llm.analyze_wrong_note(req.code, req.comment, evidence=[])
    except LLMNotImplementedError:
        log_ai_event("analyze", model=config.OPENAI_MODEL, status="not_implemented")
        return WrongNoteAnalyzeResponse(
            request_id=ctx["request_id"],
            status=LLMStatus.failed,
            message="not_implemented",
        )

    log_ai_event("analyze", model=config.OPENAI_MODEL)
    return WrongNoteAnalyzeResponse(
        request_id=ctx["request_id"],
        status=LLMStatus.success,
        **result,
    )


@router.post("/embed", response_model=WrongNoteEmbedResponse)
async def embed(req: WrongNoteEmbedRequest, ctx=Depends(verify_internal)):
    """Index a saved wrong note into ChromaDB."""
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
    """Answer from the authenticated user's own wrong-note evidence."""
    evidence = chroma.search_user_notes(req.user_id, req.question)
    if not evidence:
        log_ai_event("note_ask", user_id=req.user_id, hits=0)
        return NoteAskResponse(
            request_id=ctx["request_id"],
            status=LLMStatus.empty,
            message="not_enough_evidence",
            answer="",
            evidence_note_ids=[],
            scores=[],
        )

    try:
        answer = await llm.answer_from_notes(req.question, evidence)
    except LLMNotImplementedError:
        log_ai_event("note_ask", user_id=req.user_id, hits=len(evidence), status="not_implemented")
        return NoteAskResponse(
            request_id=ctx["request_id"],
            status=LLMStatus.failed,
            message="not_implemented",
            answer="",
            evidence_note_ids=[item.note_id for item in evidence],
            scores=[item.score for item in evidence],
        )

    log_ai_event("note_ask", user_id=req.user_id, hits=len(evidence))
    return NoteAskResponse(
        request_id=ctx["request_id"],
        status=LLMStatus.success,
        answer=answer,
        evidence_note_ids=[item.note_id for item in evidence],
        scores=[item.score for item in evidence],
    )


def _index_text(req: WrongNotesIndexRequest) -> str:
    return "\n".join(
        part
        for part in [
            f"problem_title: {req.problem_title}",
            f"algorithm_keywords: {', '.join(req.algorithm_keywords)}",
            f"user_comment: {req.user_comment}",
            f"error_message: {req.error_message}",
            f"wrong_code: {req.wrong_code}",
        ]
        if part.strip()
    )


@compat_router.post("/index", response_model=WrongNotesIndexResponse)
async def compat_index(req: WrongNotesIndexRequest, ctx=Depends(verify_internal)):
    """Compatibility endpoint for Django wrong-note indexing."""
    try:
        chroma.embed_note(
            req.user_id,
            req.wrongnote_id,
            _index_text(req),
            problem_title=req.problem_title,
        )
        return WrongNotesIndexResponse(ok=True, wrongnote_id=req.wrongnote_id, indexed=True)
    except Exception as exc:  # noqa: BLE001
        return WrongNotesIndexResponse(
            ok=False,
            wrongnote_id=req.wrongnote_id,
            indexed=False,
            error=str(exc),
        )


@compat_router.post("/similar", response_model=WrongNotesSimilarResponse)
async def compat_similar(req: WrongNotesSimilarRequest, ctx=Depends(verify_internal)):
    """Compatibility endpoint for similar wrong-note search."""
    try:
        evidence = chroma.search_user_notes(req.user_id, req.query, top_k=req.limit)
        items = [
            WrongNotesSimilarItem(
                wrongnote_id=item.note_id,
                problem_title=item.title or "",
                algorithm_keywords=[],
                similarity_reason="유사한 오답노트 근거로 검색되었습니다.",
                score=item.score,
            )
            for item in evidence
            if item.note_id != req.wrongnote_id
        ]
        return WrongNotesSimilarResponse(ok=True, items=items[: max(1, req.limit)])
    except Exception as exc:  # noqa: BLE001
        return WrongNotesSimilarResponse(ok=False, items=[], error=str(exc))


@compat_router.post("/analyze", response_model=WrongNotesAnalyzeResponse)
async def compat_analyze(req: WrongNotesAnalyzeRequest, ctx=Depends(verify_internal)):
    """Compatibility endpoint for review analysis with fallback."""
    fallback = {
        "mistake_type": "분석 준비 중",
        "core_concept": ", ".join(req.algorithm_keywords) or req.problem_title,
        "review_hint": "사용자 코멘트, 오류 메시지, 코드의 실패 지점을 다시 확인하세요.",
        "similar_note_summary": "RAG 근거가 충분하지 않으면 기본 복습 안내를 제공합니다.",
    }
    try:
        result = await llm.analyze_wrong_note(req.wrong_code, req.user_comment, evidence=[])
        return WrongNotesAnalyzeResponse(
            ok=True,
            analysis={
                "mistake_type": result.get("cause", ""),
                "core_concept": result.get("problem_core", ""),
                "review_hint": result.get("caution", ""),
                "similar_note_summary": result.get("solution", ""),
            },
        )
    except Exception:  # noqa: BLE001
        return WrongNotesAnalyzeResponse(ok=True, analysis=fallback)
