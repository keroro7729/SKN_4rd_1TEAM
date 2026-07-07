"""Fetch-facing Django endpoints for AI/RAG integration."""
from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .client import call_fastapi


def _load_json(request) -> tuple[dict, JsonResponse | None]:
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}, JsonResponse(
            {
                "status": "failed",
                "request_id": "",
                "message": "invalid_json",
                "data": {},
            },
            status=400,
        )
    if not isinstance(payload, dict):
        return {}, JsonResponse(
            {
                "status": "failed",
                "request_id": "",
                "message": "request body must be a JSON object",
                "data": {},
            },
            status=400,
        )
    return payload, None


def _normalize_search_data(data: dict) -> dict:
    results = []
    for item in data.get("results", []):
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "note_id": item.get("note_id"),
                "title": item.get("title") or "",
                "source": item.get("source") or "wrong_note",
                "score": item.get("score"),
                "matched_keywords": item.get("matched_keywords") or [],
            }
        )
    data["results"] = results
    return data


def _proxy_post(
    request,
    *,
    request_type: str,
    fastapi_path: str,
    required: tuple[str, ...],
    data_normalizer=None,
):
    payload, error_response = _load_json(request)
    if error_response is not None:
        return error_response

    missing = [field for field in required if payload.get(field) in (None, "")]
    if missing:
        return JsonResponse(
            {
                "status": "failed",
                "request_id": "",
                "message": f"missing required fields: {', '.join(missing)}",
                "data": {"missing_fields": missing},
            },
            status=400,
        )

    payload["user_id"] = request.user.id
    result = call_fastapi(
        user=request.user,
        request_type=request_type,
        path=fastapi_path,
        payload=payload,
    )
    if data_normalizer is not None:
        result.data = data_normalizer(result.data)
    http_status = 200 if result.status in {"success", "empty"} else 502
    return JsonResponse(result.to_response(), status=http_status)


@login_required
@require_POST
def hint(request):
    """문제 지문·사용자 코딩상태(레벨)로 enrich 후 힌트 에이전트 호출."""
    payload, error_response = _load_json(request)
    if error_response is not None:
        return error_response

    problem_id = payload.get("problem_id")
    hint_level = payload.get("hint_level")
    if not problem_id or not hint_level:
        return JsonResponse(
            {
                "status": "failed",
                "request_id": "",
                "message": "missing required fields: problem_id, hint_level",
                "data": {},
            },
            status=400,
        )

    from codingstate.models import CodingState
    from codingstate.services import get_prompt_context
    from problems.models import Problem

    problem = Problem.objects.filter(pk=problem_id).first()
    if problem is None:
        return JsonResponse(
            {"status": "failed", "request_id": "", "message": "problem_not_found", "data": {}},
            status=404,
        )
    state = CodingState.objects.filter(user=request.user).first()

    enriched = {
        "user_id": request.user.id,
        "problem_id": problem.id,
        "hint_level": int(hint_level),
        "user_code": payload.get("user_code") or "",
        "problem_title": problem.title,
        "description": problem.description,
        "constraints": problem.constraints,
        "difficulty": problem.get_difficulty_display(),
        "level": state.level if state else "",
        "coding_state": get_prompt_context(request.user),
    }
    result = call_fastapi(
        user=request.user,
        request_type="hint",
        path="/ai/hint",
        payload=enriched,
    )
    http_status = 200 if result.status in {"success", "empty"} else 502
    return JsonResponse(result.to_response(), status=http_status)


@login_required
@require_POST
def wrong_note_search(request):
    return _proxy_post(
        request,
        request_type="wrong_note_search",
        fastapi_path="/ai/wrong-note/search",
        required=("problem_id",),
        data_normalizer=_normalize_search_data,
    )


@login_required
@require_POST
def wrong_note_analyze(request):
    return _proxy_post(
        request,
        request_type="wrong_note_analyze",
        fastapi_path="/ai/wrong-note/analyze",
        required=("comment",),
    )


@login_required
@require_POST
def wrong_note_embed(request):
    return _proxy_post(
        request,
        request_type="wrong_note_embed",
        fastapi_path="/ai/wrong-note/embed",
        required=("wrong_note_id", "content"),
    )


@login_required
@require_POST
def note_ask(request):
    return _proxy_post(
        request,
        request_type="note_ask",
        fastapi_path="/ai/wrong-note/ask",
        required=("question",),
    )
