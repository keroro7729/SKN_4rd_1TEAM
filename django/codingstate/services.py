"""코딩 상태 집계·생성·소비 서비스.

- gather_stats(user)      : 학습 전과정 산출물을 집계(제출/정답률/태그강약/오류패턴/오답노트...)
- refresh(user)           : 집계 → FastAPI(LLM 요약) → CodingState 저장
- ensure_fresh(user)      : 신규 제출이 충분히 쌓였을 때만 refresh (저비용 스킵)
- get_prompt_context(user): AI 프롬프트에 주입할 컴팩트 텍스트(없으면 "") — 소비 지점 공용
"""
from django.db.models import Count, Q

from ai_proxy.client import FastAPIClientError, call_fastapi
from problems.models import ProblemTag
from submissions.models import Submission
from wrongnotes.models import WrongNote

from .models import CodingState

_FAIL = ["wrong", "error", "timeout"]


def gather_stats(user) -> dict:
    subs = Submission.objects.filter(user=user, submission_type="submit")
    total = subs.count()
    success = subs.filter(result="success").count()

    by_difficulty = {}
    for row in subs.values("problem__difficulty").annotate(
        attempted=Count("id"),
        solved=Count("id", filter=Q(result="success")),
    ):
        by_difficulty[row["problem__difficulty"] or "?"] = {
            "attempted": row["attempted"],
            "solved": row["solved"],
        }

    solved_pids = set(subs.filter(result="success").values_list("problem_id", flat=True))
    failed_pids = set(
        subs.filter(result__in=_FAIL).values_list("problem_id", flat=True)
    ) - solved_pids

    solved_tags = list(
        ProblemTag.objects.filter(problems__id__in=solved_pids)
        .values_list("name", flat=True).distinct()[:10]
    )
    failed_tags = list(
        ProblemTag.objects.filter(problems__id__in=failed_pids)
        .values_list("name", flat=True).distinct()[:10]
    )

    notes = WrongNote.objects.filter(user=user)
    patterns = [
        {"pattern": r["error_pattern"], "count": r["c"]}
        for r in notes.exclude(error_pattern="")
        .values("error_pattern").annotate(c=Count("id")).order_by("-c")[:8]
    ]
    recent = [
        {"title": r["problem__title"], "result": r["result"]}
        for r in subs.order_by("-created_at").values("problem__title", "result")[:10]
    ]

    return {
        "total_submissions": total,
        "success_count": success,
        "accuracy": round(success / total, 3) if total else 0.0,
        "by_difficulty": by_difficulty,
        "solved_tags": solved_tags,
        "failed_tags": failed_tags,
        "recurring_error_patterns": patterns,
        "wrong_note_count": notes.count(),
        "reviewed_count": notes.filter(is_reviewed=True).count(),
        "recent_activity": recent,
        "point": user.point,
    }


def refresh(user) -> CodingState | None:
    """집계 → FastAPI 요약 → CodingState 저장. 실패 시 None(예외 억제)."""
    stats = gather_stats(user)
    try:
        result = call_fastapi(
            user=user,
            request_type="coding_state",
            path="/ai/coding-state/summarize",
            payload={"user_id": user.id, "stats": stats},
            timeout=90,
            raise_on_error=True,
        )
    except FastAPIClientError:
        return None
    data = result.data
    state, _ = CodingState.objects.update_or_create(
        user=user,
        defaults={
            "summary": data.get("summary", ""),
            "level": data.get("level", ""),
            "strengths": data.get("strengths", []),
            "weaknesses": data.get("weaknesses", []),
            "recurring_mistakes": data.get("recurring_mistakes", []),
            "recommended_focus": data.get("recommended_focus", []),
            "stats_snapshot": stats,
            "source_submission_count": stats["total_submissions"],
            "model": data.get("model", ""),
        },
    )
    return state


def ensure_fresh(user, *, min_new_submissions: int = 5) -> CodingState | None:
    """제출이 충분히 쌓였을 때만 refresh(저비용 스킵). 학습 이벤트 훅에서 호출."""
    submit_count = Submission.objects.filter(
        user=user, submission_type="submit"
    ).count()
    if submit_count == 0:
        return None
    state = CodingState.objects.filter(user=user).first()
    if state is None:
        return refresh(user)
    if submit_count - state.source_submission_count >= min_new_submissions:
        return refresh(user)
    return state


def get_prompt_context(user) -> str:
    """AI 프롬프트 주입용 컴팩트 컨텍스트(사용자 비노출). 상태 없으면 빈 문자열."""
    state = CodingState.objects.filter(user=user).first()
    if state is None or not state.summary:
        return ""
    return "\n".join([
        "[사용자 코딩 상태 — AI 참고용, 사용자에게 노출 금지]",
        f"추정 수준: {state.level or '-'}",
        f"강점: {', '.join(state.strengths) or '-'}",
        f"약점: {', '.join(state.weaknesses) or '-'}",
        f"반복 실수: {', '.join(state.recurring_mistakes) or '-'}",
        f"학습 방향: {', '.join(state.recommended_focus) or '-'}",
        f"요약: {state.summary}",
    ])
