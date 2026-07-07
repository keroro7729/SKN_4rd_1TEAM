"""ChromaDB indexing/search for user-scoped wrong notes.

리트리빙 고도화(v1) — 설계문서 9 §8-9(필드 단위 멀티 청크) 구현 + 섹션 mean/max 집계.

핵심 아이디어(v0 → v1):
- v0: 노트 전체(문제명·난이도·태그·회고·결과·에러·**코드**·분석)를 뭉쳐 **1벡터**로 임베딩.
      → 긴 노이즈(문제 원문/코드)가 섞여 벡터가 평균화되고 신호가 희석됨.
- v1: 매칭에 방해되는 정보(문제 원문·코드·난이도·에러·결과)를 **제외**하고,
      **회고 + AI 생성 코멘트(섹션들)** 를 각각 **짧은 청크로 분리 임베딩**(노트당 N벡터).
      문제 **카테고리·알고리즘 분류**만 짧은 `topic` 청크로 추가 고려.
      검색 시 후보 노트를 **섹션별 유사도**로 환원한 뒤 **mean·max 를 종합**해 최종 점수화.

임베딩 벡터는 외부 모델 없이 결정적 토큰-해시 BoW(MVP). 청킹/집계는 임베더와 독립적으로
정밀도를 올린다(실측: docs `llm_wiki/10. ...RAG_리트리빙_고도화_v0_vs_v1_성능평가.md`).
"""
from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timezone
from functools import lru_cache
from statistics import fmean
from typing import Dict, Iterable, List, Sequence, Tuple

import chromadb
from openai import OpenAI, OpenAIError

import config
from schemas.common import Evidence

VECTOR_DIM = 256  # 해시 폴백 임베더 차원(오프라인 전용)
TOKEN_RE = re.compile(r"[0-9A-Za-z_가-힣]+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。\n])\s+")
NAME_SANITIZE_RE = re.compile(r"[^A-Za-z0-9]+")

# 벡터에서 제외하는 노이즈(참고용 상수). 실제 제외는 payload 구성 단계(Django)에서 수행.
EXCLUDED_FROM_INDEX = ("problem_statement", "submitted_code", "difficulty", "error_message", "result")

Chunk = Tuple[str, str]  # (section, text)


def _use_openai() -> bool:
    backend = config.RAG_EMBED_BACKEND
    if backend == "openai":
        return bool(config.OPENAI_API_KEY)
    if backend == "hash":
        return False
    return bool(config.OPENAI_API_KEY)  # auto


def _collection_name() -> str:
    """임베더별로 컬렉션을 분리(벡터 차원 불일치 방지). 재인덱싱은 비파괴적."""
    sig = f"oa-{config.EMBED_MODEL}" if _use_openai() else f"hash{VECTOR_DIM}"
    sig = NAME_SANITIZE_RE.sub("-", sig).strip("-")
    return f"{config.CHROMA_COLLECTION}-{sig}"[:62].rstrip("-")


@lru_cache(maxsize=1)
def get_collection():
    """Return the wrong-note collection for the active embedding backend."""
    client = chromadb.HttpClient(host=config.CHROMA_HOST, port=config.CHROMA_PORT)
    return client.get_or_create_collection(
        name=_collection_name(),
        metadata={"hnsw:space": "cosine"},
    )


# --------------------------------------------------------------------------- #
# 순수 헬퍼 (임베딩/청킹/집계) — 라이브 검색과 오프라인 성능평가가 함께 사용                 #
# --------------------------------------------------------------------------- #
def _tokens(text: str) -> Iterable[str]:
    tokens = TOKEN_RE.findall((text or "").lower())
    return tokens or [(text or "").strip().lower() or "empty"]


def _embed_hash(text: str) -> list[float]:
    """결정적 토큰-해시 BoW 벡터(오프라인 폴백, 단위정규화)."""
    vector = [0.0] * VECTOR_DIM
    for token in _tokens(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % VECTOR_DIM
        sign = 1.0 if digest[4] % 2 else -1.0
        weight = 1.0 + (len(token) % 7) / 10.0
        vector[index] += sign * weight
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


_oa_client: OpenAI | None = None


def _get_oa() -> OpenAI:
    global _oa_client
    if _oa_client is None:
        _oa_client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _oa_client


@lru_cache(maxsize=8192)
def _embed_openai(text: str) -> tuple:
    """OpenAI 임베딩(단위정규화). 동일 텍스트는 캐시(재계산/비용 절감)."""
    resp = _get_oa().embeddings.create(model=config.EMBED_MODEL, input=text or " ")
    vector = resp.data[0].embedding
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return tuple(value / norm for value in vector)


def embed_text(text: str) -> list[float]:
    """활성 백엔드로 임베딩. openai 실패 시 결정적 해시로 폴백."""
    if _use_openai():
        try:
            return list(_embed_openai(text or " "))
        except OpenAIError:
            pass
    return _embed_hash(text)


# 하위호환 별칭
_embed_text = embed_text


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """단위정규화 벡터 가정, 코사인 유사도(=내적)를 [0,1]로 클램프."""
    dot = sum(x * y for x, y in zip(a, b))
    return max(0.0, min(1.0, dot))


def chunk_text(text: str, max_chars: int = None) -> List[str]:
    """문장 경계로 쪼갠 뒤 max_chars 이하로 패킹한 짧은 청크 목록."""
    max_chars = int(max_chars or config.RAG_CHUNK_MAX_CHARS)
    text = re.sub(r"[ \t]+", " ", (text or "").strip())
    if not text:
        return []
    chunks: List[str] = []
    current = ""
    for sentence in SENTENCE_SPLIT_RE.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > max_chars:  # 아주 긴 문장은 하드 분할
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(sentence), max_chars):
                chunks.append(sentence[i:i + max_chars])
            continue
        if len(current) + len(sentence) + 1 <= max_chars:
            current = f"{current} {sentence}".strip()
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def build_topic_text(category: str, algo_tags: Sequence[str]) -> str:
    """문제 카테고리 + 알고리즘 분류를 짧은 topic 청크 텍스트로."""
    tags = ", ".join(t for t in (algo_tags or []) if t)
    parts = []
    if category:
        parts.append(f"카테고리 {category}")
    if tags:
        parts.append(f"알고리즘 {tags}")
    return " · ".join(parts)


def build_note_chunks(
    sections: Dict[str, str],
    category: str = "",
    algo_tags: Sequence[str] = (),
) -> List[Chunk]:
    """노트를 (섹션명, 청크텍스트) 목록으로. 회고/AI코멘트는 짧은 청크로 분리, topic 1청크 추가."""
    chunks: List[Chunk] = []
    topic = build_topic_text(category, algo_tags)
    if topic:
        chunks.append(("topic", topic))
    for name, text in (sections or {}).items():
        if not (text or "").strip():
            continue
        for piece in chunk_text(text):
            chunks.append((name, piece))
    return chunks


def aggregate_section_sims(section_sims: Dict[str, float]) -> float:
    """섹션별 유사도들을 mean·max 가중합으로 종합 점수화."""
    values = [v for v in section_sims.values() if v is not None]
    if not values:
        return 0.0
    score = config.RAG_W_MEAN * fmean(values) + config.RAG_W_MAX * max(values)
    denom = (config.RAG_W_MEAN + config.RAG_W_MAX) or 1.0
    return score / denom


# --------------------------------------------------------------------------- #
# 라이브 인덱싱/검색 (ChromaDB)                                                    #
# --------------------------------------------------------------------------- #
def embed_note_chunked(
    user_id: int,
    wrong_note_id: int,
    sections: Dict[str, str],
    category: str = "",
    algo_tags: Sequence[str] = (),
    problem_title: str | None = None,
) -> dict:
    """노트를 섹션 단위 멀티 청크로 upsert. 재인덱싱 시 기존 청크 삭제 후 재생성."""
    note_id = int(wrong_note_id)
    indexed_at = datetime.now(timezone.utc).isoformat()
    collection = get_collection()

    # 재인덱싱: 이 노트의 이전 청크(및 v0 단일 문서) 전부 제거
    try:
        collection.delete(where={"wrong_note_id": note_id})
    except Exception:  # noqa: BLE001 - 최초 인덱싱 등 대상 없음
        pass

    chunks = build_note_chunks(sections, category, algo_tags)
    if not chunks:  # 인덱싱할 신호 텍스트가 없음
        return {"embedding_id": f"wrong_note:{note_id}", "indexed_at": indexed_at, "chunk_count": 0}

    ids, embeddings, documents, metadatas = [], [], [], []
    algo_str = ", ".join(t for t in (algo_tags or []) if t)
    for index, (section, text) in enumerate(chunks):
        ids.append(f"wrong_note:{note_id}#{section}:{index}")
        embeddings.append(embed_text(text))
        documents.append(text)
        metadatas.append({
            "user_id": int(user_id),
            "wrong_note_id": note_id,
            "source": "wrong_note",
            "section": section,
            "chunk_index": index,
            "indexed_at": indexed_at,
            "problem_title": problem_title or "",
            "category": category or "",
            "algo_tags": algo_str,
        })
    collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
    return {"embedding_id": f"wrong_note:{note_id}", "indexed_at": indexed_at, "chunk_count": len(chunks)}


def search_notes(
    user_id: int,
    query_chunks: Sequence[str],
    top_k: int = None,
    exclude_note_id: int | None = None,
) -> List[Evidence]:
    """쿼리 청크들로 후보 청크를 모아, 후보 노트를 섹션별 유사도로 환원 → mean/max 종합 랭킹."""
    query_chunks = [q for q in query_chunks if (q or "").strip()]
    if not query_chunks:
        return []
    collection = get_collection()
    per_query = max(1, int(config.RAG_PER_QUERY_K))

    # note_id -> {section -> best sim}, note_id -> title
    note_section_sim: Dict[int, Dict[str, float]] = {}
    note_title: Dict[int, str] = {}

    for qc in query_chunks:
        result = collection.query(
            query_embeddings=[embed_text(qc)],
            n_results=per_query,
            where={"user_id": int(user_id)},
            include=["distances", "metadatas"],
        )
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        for metadata, distance in zip(metadatas, distances):
            if not metadata:
                continue
            note_id = metadata.get("wrong_note_id")
            if note_id is None:
                continue
            note_id = int(note_id)
            if exclude_note_id is not None and note_id == int(exclude_note_id):
                continue
            sim = max(0.0, min(1.0, 1.0 - float(distance)))  # cosine distance -> sim
            section = metadata.get("section") or "_full"
            sect = note_section_sim.setdefault(note_id, {})
            if sim > sect.get(section, 0.0):
                sect[section] = sim
            note_title.setdefault(note_id, metadata.get("problem_title") or "")

    scored = [
        (note_id, aggregate_section_sims(sect))
        for note_id, sect in note_section_sim.items()
    ]
    scored = [(nid, sc) for nid, sc in scored if sc >= config.RAG_SCORE_THRESHOLD]
    scored.sort(key=lambda item: item[1], reverse=True)

    limit = max(1, int(top_k or config.RAG_TOP_K))
    return [
        Evidence(note_id=nid, source="wrong_note", score=round(sc, 4), title=note_title.get(nid) or None)
        for nid, sc in scored[:limit]
    ]


def search_user_notes(
    user_id: int,
    query_text: str,
    top_k: int = None,
) -> List[Evidence]:
    """단일 텍스트 쿼리 래퍼(내 노트 질의/리포트 호환). 쿼리도 짧은 청크로 분리 후 집계 검색."""
    chunks = chunk_text(query_text) or [query_text]
    return search_notes(user_id, chunks, top_k=top_k)
