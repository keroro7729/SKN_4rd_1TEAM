"""WrongNote application services."""
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from ai_proxy.client import call_fastapi as proxy_call_fastapi
from .models import WrongNoteVector


class FastAPIClientError(RuntimeError):
    """Raised when the internal FastAPI call fails."""


def call_fastapi(
    *,
    user,
    request_type: str,
    path: str,
    payload: dict,
) -> dict:
    """Call FastAPI through the shared AI proxy client and return raw payload."""
    result = proxy_call_fastapi(
        user=user,
        request_type=request_type,
        path=path,
        payload=payload,
    )
    if result.status not in {"success", "empty"}:
        raise FastAPIClientError(result.message)
    return result.raw or result.to_response()


def build_wrong_note_payload(note) -> dict:
    """Build the common payload for wrong-note FastAPI endpoints."""
    from codingstate.services import get_prompt_context

    tags = [tag.name for tag in note.tags.all()]
    return {
        "wrong_note_id": note.id,
        "user_id": note.user_id,
        "problem_id": note.problem_id,
        "submission_id": note.submission_id,
        "problem_title": note.problem.title,
        "tags": tags,
        "user_comment": note.comment,
        "submitted_code": note.submission.code,
        "code": note.submission.code,
        "comment": note.comment,
        "coding_state": get_prompt_context(note.user),  # AI 참고: 사용자 코딩 상태
    }


def build_wrong_note_index_content(note) -> str:
    """Build the text stored in ChromaDB for wrong-note RAG."""
    tags = ", ".join(tag.name for tag in note.tags.all())
    submission = note.submission
    analysis = note.ai_analysis.get("analysis", {}) if note.ai_analysis else {}
    parts = [
        f"문제명: {note.problem.title}",
        f"난이도: {note.problem.difficulty}",
        f"태그: {tags}",
        f"사용자 코멘트: {note.comment}",
        f"제출 결과: {submission.result}",
        f"오류 메시지: {submission.error_message or ''}",
        f"제출 코드: {submission.code or ''}",
        f"문제 핵심: {analysis.get('problem_core', '')}",
        f"오답 원인: {analysis.get('cause', '')}",
        f"풀이 과정: {analysis.get('solution', '')}",
        f"주의사항: {analysis.get('caution', '')}",
    ]
    return "\n".join(part for part in parts if part.strip())


def embed_wrong_note(note) -> dict:
    """Index a saved wrong note through FastAPI and update local vector metadata."""
    payload = {
        "wrong_note_id": note.id,
        "user_id": note.user_id,
        "content": build_wrong_note_index_content(note),
        "problem_title": note.problem.title,
    }
    result = call_fastapi(
        user=note.user,
        request_type="wrong_note_embed",
        path="/ai/wrong-note/embed",
        payload=payload,
    )
    indexed_at = parse_datetime(result.get("indexed_at") or "")
    if indexed_at is None:
        indexed_at = timezone.now()
    WrongNoteVector.objects.update_or_create(
        wrong_note=note,
        defaults={
            "user": note.user,
            "embedding_id": result.get("embedding_id") or f"wrong_note:{note.id}",
            "source": "wrong_note",
            "indexed_at": indexed_at,
        },
    )
    note.status = "indexed"
    note.save(update_fields=["status"])
    return result


def analyze_wrong_note(note) -> dict:
    """Run similar-note search and AI analysis through FastAPI."""
    payload = build_wrong_note_payload(note)
    result = {
        "similar_notes": [],
        "analysis": {},
        "errors": [],
    }

    try:
        search = call_fastapi(
            user=note.user,
            request_type="wrong_note_search",
            path="/ai/wrong-note/search",
            payload=payload,
        )
        result["similar_notes"] = search.get("results", [])
        result["search_status"] = search.get("status")
        result["search_request_id"] = search.get("request_id")
    except FastAPIClientError as exc:
        result["errors"].append({"stage": "search", "message": str(exc)})

    try:
        analyze = call_fastapi(
            user=note.user,
            request_type="wrong_note_analyze",
            path="/ai/wrong-note/analyze",
            payload=payload,
        )
        result["analysis"] = {
            "problem_core": analyze.get("problem_core", ""),
            "cause": analyze.get("cause", ""),
            "solution": analyze.get("solution", ""),
            "caution": analyze.get("caution", ""),
            "evidence": analyze.get("evidence", []),
        }
        result["analysis_status"] = analyze.get("status")
        result["analysis_request_id"] = analyze.get("request_id")
    except FastAPIClientError as exc:
        result["errors"].append({"stage": "analyze", "message": str(exc)})

    return result
