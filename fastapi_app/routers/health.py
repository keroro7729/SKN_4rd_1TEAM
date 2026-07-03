"""헬스 체크 (/ai/health)."""
from fastapi import APIRouter

import config

router = APIRouter(prefix="/ai", tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "model": config.OPENAI_MODEL,
        "rag_status": "stub",  # STEP-06에서 ChromaDB 연결 상태로 대체
    }
