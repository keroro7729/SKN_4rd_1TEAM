"""간단한 문제 추천 서비스.

LLM 없이 결정적으로 계산한다(문제 풀이 페이지의 '추천 퀘스트'에 사용).
신호는 CodingState.weaknesses 를 만들어내는 것과 동일한 '실패 태그':
사용자가 제출했지만 아직 정답 처리하지 못한 문제들의 태그를 취약 유형으로 보고,
그 태그를 가진 '아직 못 푼 문제'를 우선 추천한다. 부족하면 남은 미해결 문제로 채운다.
"""
from django.db.models import Case, IntegerField, Value, When

from submissions.models import Submission

from ..models import Problem

_FAIL_RESULTS = ["wrong", "error", "timeout"]

# 난이도 의미 순서(쉬운 것부터). CharField 알파벳순과 다르므로 명시적으로 매핑한다.
_DIFFICULTY_ORDER = Case(
    When(difficulty="basic", then=Value(0)),
    When(difficulty="beginner", then=Value(1)),
    When(difficulty="intermediate", then=Value(2)),
    When(difficulty="advanced", then=Value(3)),
    default=Value(9),
    output_field=IntegerField(),
)


def recommend_problems(user, current=None, limit=3):
    """추천 문제 리스트를 반환. 각 항목: {"problem": Problem, "reason": str}."""
    submits = Submission.objects.filter(user=user, submission_type="submit")
    attempted_ids = set(submits.values_list("problem_id", flat=True))
    solved_ids = set(
        submits.filter(result="success").values_list("problem_id", flat=True)
    )
    # 취약 태그 = 틀렸지만(wrong/error/timeout) 끝내 못 푼 문제들의 태그
    failed_ids = set(
        submits.filter(result__in=_FAIL_RESULTS).values_list("problem_id", flat=True)
    ) - solved_ids
    weak_tag_ids = set(
        Problem.objects.filter(id__in=failed_ids).values_list("tags__id", flat=True)
    )
    weak_tag_ids.discard(None)

    # 후보 = 아직 제출한 적 없는(새로운) 활성 문제(현재 문제 제외)
    base = (
        Problem.objects.filter(is_active=True)
        .exclude(id__in=attempted_ids)
        .select_related("category")
        .prefetch_related("tags")
        .annotate(_diff=_DIFFICULTY_ORDER)
    )
    if current is not None:
        base = base.exclude(id=current.id)

    picks = []
    seen = set()

    def take(queryset, reason):
        for problem in queryset:
            if problem.id in seen or len(picks) >= limit:
                continue
            picks.append({"problem": problem, "reason": reason})
            seen.add(problem.id)

    # 1) 취약 유형 보강 — 취약 태그를 가진 미해결 문제(쉬운 난이도 우선)
    if weak_tag_ids:
        take(
            base.filter(tags__id__in=weak_tag_ids).distinct().order_by("_diff", "id")[:limit],
            "취약 유형 보강",
        )

    # 2) 채우기 — 남은 미해결 문제(쉬운 난이도 우선)
    if len(picks) < limit:
        take(
            base.exclude(id__in=seen).order_by("_diff", "id")[:limit],
            "새 도전",
        )

    return picks
