"""Internal read-only diagnostics endpoints."""
from __future__ import annotations

from typing import Any

import chromadb
from fastapi import APIRouter, Depends

import config
from services.security import verify_internal

router = APIRouter(prefix="/ai/diagnostics", tags=["diagnostics"])

FORBIDDEN_COLLECTIONS = ("concept_embeddings", "pattern_embeddings")


def _collection_name(item: Any) -> str:
    return getattr(item, "name", str(item))


def _collection_count(client: Any, item: Any, name: str) -> int | None:
    try:
        if hasattr(item, "count"):
            return int(item.count())
        return int(client.get_collection(name).count())
    except Exception:
        return None


def _sample_metadata(client: Any, collection_name: str, limit: int = 3) -> list[dict]:
    try:
        collection = client.get_collection(collection_name)
        payload = collection.get(limit=limit, include=["metadatas"])
        metadatas = payload.get("metadatas") or []
        return [item for item in metadatas if isinstance(item, dict)]
    except Exception:
        return []


@router.get("/chroma")
async def chroma_diagnostics(ctx=Depends(verify_internal)):
    """Inspect ChromaDB state without creating collections."""
    request_id = ctx["request_id"]
    try:
        client = chromadb.HttpClient(host=config.CHROMA_HOST, port=config.CHROMA_PORT)
        collection_items = client.list_collections()
    except Exception as exc:
        return {
            "status": "failed",
            "request_id": request_id,
            "message": f"chroma_connection_failed: {exc.__class__.__name__}",
            "data": {
                "host": config.CHROMA_HOST,
                "port": config.CHROMA_PORT,
                "collections": [],
                "required": {
                    "name": config.CHROMA_COLLECTION,
                    "exists": False,
                    "sample_metadatas": [],
                },
                "forbidden": {
                    name: {"exists": False, "count": None}
                    for name in FORBIDDEN_COLLECTIONS
                },
            },
        }

    collections = []
    collection_names = set()
    for item in collection_items:
        name = _collection_name(item)
        collection_names.add(name)
        collections.append(
            {
                "name": name,
                "count": _collection_count(client, item, name),
            }
        )

    required_exists = config.CHROMA_COLLECTION in collection_names
    forbidden = {
        name: {
            "exists": name in collection_names,
            "count": next(
                (
                    collection["count"]
                    for collection in collections
                    if collection["name"] == name
                ),
                None,
            ),
        }
        for name in FORBIDDEN_COLLECTIONS
    }

    return {
        "status": "success" if required_exists else "empty",
        "request_id": request_id,
        "message": (
            "wrong_note_embeddings collection found"
            if required_exists
            else "wrong_note_embeddings collection not found"
        ),
        "data": {
            "host": config.CHROMA_HOST,
            "port": config.CHROMA_PORT,
            "collections": collections,
            "required": {
                "name": config.CHROMA_COLLECTION,
                "exists": required_exists,
                "sample_metadatas": (
                    _sample_metadata(client, config.CHROMA_COLLECTION)
                    if required_exists
                    else []
                ),
            },
            "forbidden": forbidden,
        },
    }
