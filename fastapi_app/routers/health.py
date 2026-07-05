"""헬스 체크 (/ai/health)."""
from fastapi import APIRouter

import config

router = APIRouter(prefix="/ai", tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "model": config.OPENAI_MODEL,
        "rag_status": "vector_index_only",
        "llm_status": "not_implemented",
        "collection": config.CHROMA_COLLECTION,
    }
