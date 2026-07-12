"""헬스 체크 (/ai/health)."""
from fastapi import APIRouter

import config

router = APIRouter(prefix="/ai", tags=["health"])


@router.get("/health")
async def health() -> dict:
    # 실제 구현 상태를 반영(옛 하드코딩 "not_implemented" 문자열 정리).
    llm_status = "operational" if config.OPENAI_API_KEY else "no_api_key"
    if config.RAG_EMBED_BACKEND == "hash" or (
        config.RAG_EMBED_BACKEND == "auto" and not config.OPENAI_API_KEY
    ):
        embed_backend = "hash"  # 오프라인 결정적 해시 폴백
    else:
        embed_backend = "openai"
    return {
        "status": "ok",
        "model": config.OPENAI_MODEL,
        "llm_status": llm_status,
        "rag_status": "operational",
        "embed_model": config.EMBED_MODEL,
        "embed_backend": embed_backend,
        "collection": config.CHROMA_COLLECTION,
    }
