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
    category = note.problem.category.name if note.problem.category_id else ""
    return {
        "wrong_note_id": note.id,
        "user_id": note.user_id,
        "problem_id": note.problem_id,
        "submission_id": note.submission_id,
        "problem_title": note.problem.title,
        "problem_statement": note.problem.description,
        "category": category,  # v1 검색: topic 청크(카테고리) 추가 고려
        "tags": tags,
        "user_comment": note.comment,
        "submitted_code": note.submission.code,
        "code": note.submission.code,
        "comment": note.comment,
        "coding_state": get_prompt_context(note.user),  # AI 참고: 사용자 코딩 상태
    }


def build_wrong_note_sections(note):
    """RAG v1 인덱싱용 섹션 구성.

    매칭에 방해되는 정보(문제 원문·제출 코드·난이도·에러·결과)는 **제외**하고,
    회고(retrospection) + AI 생성 코멘트(문제핵심/풀이/원인/개선/피드백/체크)만 섹션으로 넘긴다.
    카테고리·알고리즘 분류는 topic 청크로 FastAPI 가 추가 고려한다.
    반환: (sections: dict[str,str], category: str, algo_tags: list[str])
    """
    analysis = note.ai_analysis.get("analysis", {}) if note.ai_analysis else {}
    sections = {}
    if note.comment:
        sections["retrospection"] = note.comment
    for key in ("problem_core", "solution", "cause", "improvement", "ai_feedback"):
        value = (analysis.get(key) or "").strip()
        if value:
            sections[key] = value
    checklist = analysis.get("next_checklist") or []
    if checklist:
        sections["checklist"] = " / ".join(str(item) for item in checklist)

    category = note.problem.category.name if note.problem.category_id else ""
    algo_tags = [tag.name for tag in note.tags.all()]
    return sections, category, algo_tags


def embed_wrong_note(note) -> dict:
    """Index a saved wrong note through FastAPI (v1: 섹션 멀티 청킹) and update vector meta."""
    sections, category, algo_tags = build_wrong_note_sections(note)
    payload = {
        "wrong_note_id": note.id,
        "user_id": note.user_id,
        "problem_title": note.problem.title,
        "category": category,
        "algo_tags": algo_tags,
        "sections": sections,
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
            "solution": analyze.get("solution", ""),
            "cause": analyze.get("cause", ""),
            "improvement": analyze.get("improvement", ""),
            "ai_feedback": analyze.get("ai_feedback", ""),
            "next_checklist": analyze.get("next_checklist", []),
            "evidence": analyze.get("evidence", []),
        }
        result["analysis_status"] = analyze.get("status")
        result["analysis_request_id"] = analyze.get("request_id")
    except FastAPIClientError as exc:
        result["errors"].append({"stage": "analyze", "message": str(exc)})

    return result
