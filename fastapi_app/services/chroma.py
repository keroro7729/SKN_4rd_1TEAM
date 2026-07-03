"""ChromaDB 벡터 검색 (스캐폴딩 스텁).

핵심 규칙:
- 반드시 metadata user_id 필터 적용 (다른 사용자 노트 검색 금지).
- similarity_score = 1 - distance 로 변환.
- RAG_SCORE_THRESHOLD 이상, 상위 TOP_K 만 반환.
실제 구현은 STEP-06.
"""
from typing import List

import config
from schemas.common import Evidence


def search_user_notes(
    user_id: int,
    query_text: str,
    top_k: int = config.RAG_TOP_K,
) -> List[Evidence]:
    """현재 오답과 유사한 '본인' 과거 오답노트 검색."""
    # TODO(STEP-06):
    #   collection.query(
    #       query_texts=[query_text],
    #       n_results=top_k,
    #       where={"user_id": user_id},          # 사용자별 필터 필수
    #   )
    #   score = 1 - distance; score >= RAG_SCORE_THRESHOLD 만 채택
    return []


def embed_note(user_id: int, wrong_note_id: int, content: str) -> dict:
    """저장된 오답노트를 wrong_note_embeddings 컬렉션에 반영 (F-14)."""
    # TODO(STEP-06): collection.add(ids=[...], documents=[content],
    #                metadatas=[{"user_id": user_id, "wrong_note_id": wrong_note_id}])
    return {"embedding_id": None, "indexed_at": None}
