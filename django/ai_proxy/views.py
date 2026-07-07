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


@login_required
@require_POST
def tutor_ask(request):
    """미니튜터: 대화 이력 + 현재 활동 + 코딩 상태 + 최근 7~30일 오답을 모아 FastAPI 호출."""
    payload, error_response = _load_json(request)
    if error_response is not None:
        return error_response

    question = (payload.get("question") or "").strip()
    if not question:
        return JsonResponse(
            {"status": "failed", "request_id": "", "message": "missing required fields: question", "data": {}},
            status=400,
        )

    from datetime import timedelta

    from django.utils import timezone

    from codingstate.services import get_prompt_context
    from problems.models import Problem
    from wrongnotes.models import WrongNote

    user = request.user
    now = timezone.now()
    since = now - timedelta(days=30)

    # 최근 30일 오답 기록(최신순). days_ago 로 7일/1달 구간 정보를 함께 전달.
    recent_notes = []
    for note in (
        WrongNote.objects.filter(user=user, created_at__gte=since)
        .select_related("problem")
        .order_by("-created_at")[:8]
    ):
        analysis = (note.ai_analysis or {}).get("analysis", {}) if note.ai_analysis else {}
        summary = (note.comment or analysis.get("cause") or "").strip()
        recent_notes.append({
            "note_id": note.id,
            "title": note.problem.title,
            "error_pattern": note.error_pattern or "",
            "days_ago": (now - note.created_at).days,
            "summary": summary[:120],
        })

    # 현재 활동(클라이언트가 보낸 페이지/문제 컨텍스트 정리)
    activity_in = payload.get("activity") or {}
    activity_lines = []
    page_title = (activity_in.get("title") or "").strip()
    if page_title:
        activity_lines.append(f"현재 페이지: {page_title}")
    problem_id = activity_in.get("problem_id")
    if problem_id:
        problem = Problem.objects.filter(pk=problem_id).select_related("category").first()
        if problem:
            tags = ", ".join(t.name for t in problem.tags.all()[:5])
            activity_lines.append(
                f"풀고 있는 문제: #{problem.id} {problem.title} "
                f"(난이도 {problem.get_difficulty_display()}{', 태그 ' + tags if tags else ''})"
            )
    elif (activity_in.get("path") or "").strip():
        activity_lines.append(f"경로: {activity_in['path'].strip()}")

    # 대화 컨텍스트(최근 8턴, 길이 제한)
    history = []
    for turn in (payload.get("history") or [])[-8:]:
        if not isinstance(turn, dict):
            continue
        content = (turn.get("content") or "").strip()
        if content:
            role = "assistant" if turn.get("role") == "assistant" else "user"
            history.append({"role": role, "content": content[:1000]})

    result = call_fastapi(
        user=user,
        request_type="tutor_chat",
        path="/ai/tutor/chat",
        payload={
            "user_id": user.id,
            "question": question,
            "history": history,
            "coding_state": get_prompt_context(user),
            "activity": "\n".join(activity_lines),
            "recent_notes": recent_notes,
            "recent_window_days": 30,
        },
        timeout=90,
    )
    http_status = 200 if result.status in {"success", "empty"} else 502
    return JsonResponse(result.to_response(), status=http_status)
