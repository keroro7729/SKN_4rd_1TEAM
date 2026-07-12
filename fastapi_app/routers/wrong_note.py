"""오답노트 RAG API (/ai/wrong-note/*)."""
from fastapi import APIRouter, Depends

import config
from schemas.common import LLMStatus
from schemas.wrong_note import (
    WrongNoteAnalyzeRequest,
    WrongNoteAnalyzeResponse,
    WrongNoteEmbedRequest,
    WrongNoteEmbedResponse,
    WrongNoteSearchRequest,
    WrongNoteSearchResponse,
)
from logging_setup import log_ai_event
from services import chroma, llm
from services.llm import LLMCallError, LLMNotImplementedError
from services.security import verify_internal

router = APIRouter(prefix="/ai/wrong-note", tags=["wrong-note"])


@router.post("/search", response_model=WrongNoteSearchResponse)
async def search(req: WrongNoteSearchRequest, ctx=Depends(verify_internal)):
    """유사 오답노트 검색 (user_id 필터 필수).

    v1: 문제 원문/코드는 쿼리에서 제외. 회고(user_comment)를 짧은 청크로 분리하고,
        카테고리·알고리즘 분류는 topic 청크로 추가 고려해 섹션 mean/max 집계로 랭킹.
    """
    query_chunks = list(chroma.chunk_text(req.user_comment))
    topic = chroma.build_topic_text(req.category, req.tags)
    if topic:
        query_chunks.append(topic)
    results = chroma.search_notes(
        req.user_id, query_chunks, exclude_note_id=req.wrong_note_id
    )
    status = LLMStatus.success if results else LLMStatus.empty
    log_ai_event(
        "rag_search", user_id=req.user_id, top_k=config.RAG_TOP_K,
        query_chunks=len(query_chunks), hits=len(results),
    )
    return WrongNoteSearchResponse(
        request_id=ctx["request_id"],
        status=status,
        results=results,
    )


@router.post("/analyze", response_model=WrongNoteAnalyzeResponse)
async def analyze(req: WrongNoteAnalyzeRequest, ctx=Depends(verify_internal)):
    """오답 원인 분석."""
    try:
        result = await llm.analyze_wrong_note(
            req.code,
            req.comment,
            evidence=[],
            coding_state=req.coding_state,
            problem_title=req.problem_title,
            tags=req.tags,
            problem_statement=req.problem_statement,
        )
    except LLMNotImplementedError:
        log_ai_event("analyze", model=config.OPENAI_MODEL, status="not_implemented")
        return WrongNoteAnalyzeResponse(
            request_id=ctx["request_id"],
            status=LLMStatus.failed,
            message="not_implemented",
        )
    except LLMCallError as exc:
        log_ai_event("analyze", model=config.OPENAI_MODEL, status="failed")
        return WrongNoteAnalyzeResponse(
            request_id=ctx["request_id"],
            status=LLMStatus.failed,
            message=str(exc),
        )
    log_ai_event("analyze", model=config.OPENAI_MODEL)
    return WrongNoteAnalyzeResponse(
        request_id=ctx["request_id"],
        status=LLMStatus.success,
        **result,
    )


@router.post("/embed", response_model=WrongNoteEmbedResponse)
async def embed(req: WrongNoteEmbedRequest, ctx=Depends(verify_internal)):
    """저장된 오답노트를 ChromaDB에 인덱싱 (F-14).

    v1: 회고+AI코멘트 섹션을 짧은 청크로 분리 임베딩(멀티 벡터). 문제 원문/코드/난이도/에러는
        인덱스에서 제외(Django payload 단계에서 미포함), 카테고리·알고리즘만 topic 청크로 추가.
    """
    out = chroma.embed_note_chunked(
        req.user_id,
        req.wrong_note_id,
        req.sections,
        category=req.category,
        algo_tags=req.algo_tags,
        problem_title=req.problem_title,
    )
    log_ai_event(
        "rag_embed", user_id=req.user_id, wrong_note_id=req.wrong_note_id,
        chunk_count=out.get("chunk_count", 0),
    )
    return WrongNoteEmbedResponse(
        request_id=ctx["request_id"],
        status=LLMStatus.success,
        **out,
    )
