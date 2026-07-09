"""코딩 상태 집계·생성·소비 서비스.

- gather_stats(user)      : 학습 전과정 산출물을 집계(제출/정답률/태그강약/오류패턴/오답노트...)
- refresh(user)           : 집계 → FastAPI(LLM 요약) → CodingState 저장
- ensure_fresh(user)      : 신규 제출이 충분히 쌓였을 때만 refresh (저비용 스킵) — 실시간 훅용
- batch_refresh(...)      : 신규 활동이 쌓인 사용자만 골라 배치 갱신 (스케줄/오프라인용)
- get_prompt_context(user): AI 프롬프트에 주입할 컴팩트 텍스트(없으면 "") — 소비 지점 공용
"""
import json

from django.contrib.auth import get_user_model
from django.db.models import Count, Q

from ai_proxy.client import FastAPIClientError, call_fastapi
from logs.models import LLMRequestLog
from problems.models import ProblemTag
from submissions.models import Submission
from wrongnotes.models import WrongNote

from .models import CodingState

_FAIL = ["wrong", "error", "timeout"]

# 사고 추적 입력은 프롬프트 크기를 위해 최근 N건·문자수로 제한한다.
_CODE_SNIPPET_CHARS = 600
_RETRO_CHARS = 300
_QUESTION_CHARS = 200


def _recent_code(subs) -> list[dict]:
    """최근 제출 코드 스니펫(코딩 스타일·패턴 추론용)."""
    return [
        {
            "problem": s.problem.title,
            "result": s.result,
            "code": (s.code or "")[:_CODE_SNIPPET_CHARS],
        }
        for s in subs.select_related("problem").order_by("-created_at")[:4]
    ]


def _retrospections(notes) -> list[dict]:
    """최근 오답노트 회고 원문 + AI가 진단한 cause(약점 서술 근거)."""
    rows = []
    for note in notes.select_related("problem").order_by("-created_at")[:4]:
        analysis = note.ai_analysis if isinstance(note.ai_analysis, dict) else {}
        cause = (analysis.get("analysis", {}) or {}).get("cause", "")
        rows.append({
            "problem": note.problem.title,
            "error_pattern": note.error_pattern,
            "comment": (note.comment or "")[:_RETRO_CHARS],
            "cause": (cause or "")[:_RETRO_CHARS],
        })
    return rows


def _recent_questions(user) -> list[str]:
    """미니튜터에 던진 최근 질문(어디서 막히는지·오해 지점 추적)."""
    questions = []
    for row in (
        LLMRequestLog.objects.filter(user=user, request_type="tutor_chat")
        .order_by("-id")[:5]
    ):
        try:
            payload = json.loads(row.input_text or "{}")
        except (ValueError, TypeError):
            continue
        question = (payload.get("question") or "").strip()
        if question:
            questions.append(question[:_QUESTION_CHARS])
    return questions


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
        # 사고 추적 입력(제출 코드·회고 원문·질문) — 사고 방식/막히는 지점 추론용
        "recent_code": _recent_code(subs),
        "retrospections": _retrospections(notes),
        "recent_questions": _recent_questions(user),
    }


def refresh(user) -> CodingState | None:
    """집계 → FastAPI 요약 → CodingState 저장. 실패 시 None(예외 억제).

    요약 메모리 연속성: 직전 summary/thinking_profile 을 입력으로 넘겨 '처음부터 새로'가
    아니라 변화점 위주로 누적 갱신하게 한다(rolling memory).
    """
    prev = CodingState.objects.filter(user=user).first()
    stats = gather_stats(user)
    # rolling memory — 직전 상태(메모리)를 근거로 델타 갱신
    stats["previous_summary"] = prev.summary if prev else ""
    stats["previous_thinking"] = prev.thinking_profile if prev else ""
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
            "thinking_profile": data.get("thinking_profile", ""),
            "level": data.get("level", ""),
            "strengths": data.get("strengths", []),
            "weaknesses": data.get("weaknesses", []),
            "recurring_mistakes": data.get("recurring_mistakes", []),
            "recommended_focus": data.get("recommended_focus", []),
            "stats_snapshot": stats,
            "source_submission_count": stats["total_submissions"],
            "refresh_count": (prev.refresh_count + 1) if prev else 1,
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


def select_stale_user_ids(*, min_new_submissions: int = 5, force: bool = False) -> list[int]:
    """배치 갱신이 필요한 사용자 id 목록(제출 순 안정 정렬).

    - 상태가 없거나(최초), 마지막 갱신 이후 신규 제출이 min_new_submissions 이상이면 대상.
    - force=True 면 제출 이력이 있는 전체 사용자를 대상으로 한다.
    per-user 카운트 쿼리 대신 집계 2번으로 판별한다(대량 사용자 대비).
    """
    submit_counts = {
        row["user_id"]: row["c"]
        for row in Submission.objects.filter(submission_type="submit")
        .values("user_id").annotate(c=Count("id"))
    }
    source_counts = dict(
        CodingState.objects.values_list("user_id", "source_submission_count")
    )
    stale = []
    for user_id, count in submit_counts.items():
        if count == 0:
            continue
        base = source_counts.get(user_id)
        if force or base is None or (count - base) >= min_new_submissions:
            stale.append((user_id, count))
    # 활동 많은 사용자부터
    stale.sort(key=lambda item: item[1], reverse=True)
    return [user_id for user_id, _ in stale]


def batch_refresh(
    *, min_new_submissions: int = 5, limit: int | None = None, force: bool = False, log=None
) -> dict:
    """활동이 쌓인 사용자들의 coding_state를 배치 갱신. 스케줄/오프라인 실행용.

    ⚠️ refresh() 는 사용자당 FastAPI(LLM) 동기 호출(최대 90s)이므로 순차 처리된다.
       요청 스레드가 아닌 관리 명령/크론에서만 호출할 것. limit 로 1회 LLM 호출 수를 제한한다.
    반환: {"candidates","stale","processed","refreshed","failed","skipped_fresh"}
    """
    emit = log or (lambda *a: None)
    stale_ids = select_stale_user_ids(min_new_submissions=min_new_submissions, force=force)
    candidates = (
        Submission.objects.filter(submission_type="submit")
        .values("user_id").distinct().count()
    )
    stale_total = len(stale_ids)
    if limit is not None:
        stale_ids = stale_ids[:limit]

    users = {u.id: u for u in get_user_model().objects.filter(id__in=stale_ids)}
    refreshed = failed = 0
    for user_id in stale_ids:  # 정렬 순서 유지
        user = users.get(user_id)
        if user is None:
            continue
        state = refresh(user)
        if state is not None:
            refreshed += 1
            emit(f"[OK] u{user_id} {user.username}: {state.level or '미평가'}")
        else:
            failed += 1
            emit(f"[FAIL] u{user_id} {user.username}: 갱신 실패/데이터 없음")

    return {
        "candidates": candidates,
        "stale": stale_total,
        "processed": len(stale_ids),
        "refreshed": refreshed,
        "failed": failed,
        "skipped_fresh": candidates - stale_total,
    }


def get_prompt_context(user) -> str:
    """AI 프롬프트 주입용 컴팩트 컨텍스트(사용자 비노출). 상태 없으면 빈 문자열."""
    state = CodingState.objects.filter(user=user).first()
    if state is None or not state.summary:
        return ""
    lines = [
        "[사용자 코딩 상태 — AI 참고용, 사용자에게 노출 금지]",
        f"추정 수준: {state.level or '-'}",
        f"강점: {', '.join(state.strengths) or '-'}",
        f"약점: {', '.join(state.weaknesses) or '-'}",
        f"반복 실수: {', '.join(state.recurring_mistakes) or '-'}",
        f"학습 방향: {', '.join(state.recommended_focus) or '-'}",
    ]
    if state.thinking_profile:
        lines.append(f"사고 특성: {state.thinking_profile}")
    lines.append(f"요약: {state.summary}")
    return "\n".join(lines)
