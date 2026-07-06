"""Problem recommendation services."""
from __future__ import annotations

import hashlib
import random
from datetime import date

from submissions.models import Submission

from problems.models import Problem


def _recommendation_seed(user, today: date) -> int:
    user_key = f"user:{user.id}" if getattr(user, "is_authenticated", False) else "anonymous"
    digest = hashlib.sha256(f"{today.isoformat()}:{user_key}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def get_today_recommended_problems(user=None, limit=3):
    """Return daily-random recommendations.

    The policy intentionally does not use view_count or rating because those
    fields are not reliable in the current MVP data model.
    """
    qs = Problem.objects.filter(is_active=True).select_related("category").prefetch_related("tags")
    if getattr(user, "is_authenticated", False):
        solved_ids = Submission.objects.filter(
            user=user,
            submission_type="submit",
            result="success",
        ).values_list("problem_id", flat=True)
        unsolved = list(qs.exclude(id__in=solved_ids))
        candidates = unsolved or list(qs)
    else:
        candidates = list(qs)

    rng = random.Random(_recommendation_seed(user, date.today()))
    rng.shuffle(candidates)
    return candidates[: max(1, int(limit or 3))]
