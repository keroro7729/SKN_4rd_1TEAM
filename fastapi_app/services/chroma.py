"""ChromaDB indexing and search for user-scoped wrong notes."""
from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timezone
from functools import lru_cache
from typing import Iterable, List

import chromadb

import config
from schemas.common import Evidence

VECTOR_DIM = 64
TOKEN_RE = re.compile(r"[0-9A-Za-z_가-힣]+")


@lru_cache(maxsize=1)
def get_collection():
    """Return the wrong-note collection without relying on external embedding models."""
    client = chromadb.HttpClient(host=config.CHROMA_HOST, port=config.CHROMA_PORT)
    return client.get_or_create_collection(
        name=config.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def _tokens(text: str) -> Iterable[str]:
    tokens = TOKEN_RE.findall((text or "").lower())
    return tokens or [(text or "").strip().lower() or "empty"]


def _embed_text(text: str) -> list[float]:
    """Create a deterministic lightweight vector for MVP RAG verification."""
    vector = [0.0] * VECTOR_DIM
    for token in _tokens(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % VECTOR_DIM
        sign = 1.0 if digest[4] % 2 else -1.0
        weight = 1.0 + (len(token) % 7) / 10.0
        vector[index] += sign * weight

    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _score_from_distance(distance: float | None) -> float:
    if distance is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - float(distance)))


def search_user_notes(
    user_id: int,
    query_text: str,
    top_k: int = config.RAG_TOP_K,
) -> List[Evidence]:
    """Search only the authenticated user's wrong-note vectors."""
    collection = get_collection()
    limit = max(1, int(top_k or config.RAG_TOP_K))
    result = collection.query(
        query_embeddings=[_embed_text(query_text)],
        n_results=limit,
        where={"user_id": int(user_id)},
        include=["distances", "metadatas"],
    )

    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    evidence: list[Evidence] = []
    for metadata, distance in zip(metadatas, distances):
        score = _score_from_distance(distance)
        if score < config.RAG_SCORE_THRESHOLD:
            continue
        note_id = metadata.get("wrong_note_id") if metadata else None
        if note_id is None:
            continue
        evidence.append(
            Evidence(
                note_id=int(note_id),
                source=(metadata or {}).get("source") or "wrong_note",
                score=round(score, 4),
                title=(metadata or {}).get("problem_title"),
            )
        )
    return evidence


def embed_note(
    user_id: int,
    wrong_note_id: int,
    content: str,
    problem_title: str | None = None,
) -> dict:
    """Upsert a saved wrong note into ChromaDB."""
    embedding_id = f"wrong_note:{int(wrong_note_id)}"
    indexed_at = datetime.now(timezone.utc).isoformat()
    metadata = {
        "user_id": int(user_id),
        "wrong_note_id": int(wrong_note_id),
        "source": "wrong_note",
        "indexed_at": indexed_at,
        "problem_title": problem_title or "",
    }
    collection = get_collection()
    collection.upsert(
        ids=[embedding_id],
        embeddings=[_embed_text(content)],
        documents=[content],
        metadatas=[metadata],
    )
    return {"embedding_id": embedding_id, "indexed_at": indexed_at}
