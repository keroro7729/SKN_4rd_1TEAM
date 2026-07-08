"""Problem list/detail views."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View
from django.views.generic import DetailView, ListView

from config.choices import DIFFICULTY_CHOICES
from config.pagination import build_pagination_context
from submissions.models import Submission
from wrongnotes.models import WrongNote

from .models import Problem, ProblemFavorite


class ProblemListView(LoginRequiredMixin, ListView):
    """Problem list with difficulty, status, search, and favorite filters."""

    template_name = "problems/problem_list.html"
    context_object_name = "problems"
    paginate_by = 5

    def get_queryset(self):
        qs = (
            Problem.objects.filter(is_active=True)
            .select_related("category")
            .prefetch_related("tags")
            .order_by("id")
        )
        self.f_difficulty = self.request.GET.get("difficulty") or ""
        self.f_status = self.request.GET.get("status") or ""
        self.f_q = (self.request.GET.get("q") or "").strip()

        if self.f_difficulty:
            qs = qs.filter(difficulty=self.f_difficulty)
        if self.f_q:
            qs = qs.filter(title__icontains=self.f_q)

        if self.f_status:
            user = self.request.user
            solved_ids = Submission.objects.filter(
                user=user,
                submission_type="submit",
                result="success",
            ).values_list("problem_id", flat=True)
            wrong_ids = Submission.objects.filter(
                user=user,
                submission_type="submit",
                result__in=["wrong", "error", "timeout"],
            ).values_list("problem_id", flat=True)
            favorite_ids = ProblemFavorite.objects.filter(user=user).values_list("problem_id", flat=True)
            if self.f_status == "unsolved":
                qs = qs.exclude(id__in=solved_ids)
            elif self.f_status == "wrong":
                qs = qs.filter(id__in=wrong_ids)
            elif self.f_status == "solved":
                qs = qs.filter(id__in=solved_ids)
            elif self.f_status == "favorite":
                qs = qs.filter(id__in=favorite_ids)

        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["difficulties"] = DIFFICULTY_CHOICES
        ctx["cur_difficulty"] = self.f_difficulty
        ctx["cur_status"] = self.f_status
        ctx["q"] = self.f_q
        ctx["status_filters"] = [
            ("", "전체"),
            ("unsolved", "미해결"),
            ("wrong", "오답 제출"),
            ("solved", "해결 완료"),
            ("favorite", "즐겨찾기"),
        ]
        ctx["menu_items"] = [{"label": "전체", "difficulty": "", "active": not self.f_difficulty}]
        for value, label in DIFFICULTY_CHOICES:
            ctx["menu_items"].append({"label": label, "difficulty": value, "active": self.f_difficulty == value})

        favorite_ids = set(ProblemFavorite.objects.filter(user=user).values_list("problem_id", flat=True))
        user_submissions = Submission.objects.filter(user=user, submission_type="submit")
        ctx["favorite_ids"] = favorite_ids
        ctx["quick_links"] = {
            "solved_count": user_submissions.filter(result="success").values("problem_id").distinct().count(),
            "favorite_count": len(favorite_ids),
            "recent_count": user_submissions.order_by("-created_at").values("problem_id").distinct()[:20].count(),
            "note_count": WrongNote.objects.filter(user=user).count(),
        }
        ctx["recent_submissions"] = user_submissions.select_related("problem").order_by("-created_at")[:4]
        ctx["today_problem"] = (
            Problem.objects.filter(is_active=True)
            .select_related("category")
            .prefetch_related("tags")
            .order_by("?")
            .first()
        )
        if ctx.get("page_obj"):
            ctx["pagination"] = build_pagination_context(self.request, ctx["page_obj"])
        return ctx


class ProblemDetailView(LoginRequiredMixin, DetailView):
    """Problem detail and code execution page."""

    model = Problem
    template_name = "problems/problem_solve.html"
    context_object_name = "problem"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sample_cases = list(self.object.test_cases.filter(is_sample=True).order_by("id")[:3])
        if len(sample_cases) < 3:
            existing_ids = [case.id for case in sample_cases]
            extra_cases = list(
                self.object.test_cases.exclude(id__in=existing_ids).order_by("id")[: 3 - len(sample_cases)]
            )
            sample_cases.extend(extra_cases)

        slots = []
        for index in range(3):
            case = sample_cases[index] if index < len(sample_cases) else None
            slots.append(
                {
                    "index": index + 1,
                    "case": case,
                    "is_ready": case is not None,
                    "label": "연동 완료" if case is not None else "RAG 연동 예정",
                }
            )

        ctx["sample_cases"] = sample_cases
        ctx["test_case_slots"] = slots
        ctx["is_favorited"] = ProblemFavorite.objects.filter(user=self.request.user, problem=self.object).exists()
        ctx.update(self._pre_solve_checklist())
        return ctx

    def _pre_solve_checklist(self):
        """지난 오답노트에서 생성된 '다음 풀이 전 체크'를 문제풀이 페이지로 가져온다.

        1순위: 같은 문제의 최근 오답노트, 없으면 전체 최근 오답노트에서 최신 체크리스트.
        """
        user = self.request.user

        def pick(note):
            if note and note.ai_analysis:
                items = note.ai_analysis.get("analysis", {}).get("next_checklist", [])
                if items:
                    return list(items), note
            return None

        same = (
            WrongNote.objects.filter(user=user, problem=self.object)
            .order_by("-created_at")
            .first()
        )
        found = pick(same)
        source = "this_problem"
        if not found:
            source = "recent"
            for note in WrongNote.objects.filter(user=user).order_by("-created_at")[:10]:
                found = pick(note)
                if found:
                    break
        if not found:
            return {"pre_solve_checklist": [], "pre_solve_note": None, "pre_solve_source": ""}
        items, note = found
        return {"pre_solve_checklist": items, "pre_solve_note": note, "pre_solve_source": source}


class ToggleFavoriteView(LoginRequiredMixin, View):
    """Toggle one problem as favorite for the authenticated user."""

    def post(self, request, pk):
        problem = Problem.objects.filter(pk=pk, is_active=True).first()
        if not problem:
            return JsonResponse({"error": "문제를 찾을 수 없습니다."}, status=404)

        favorite = ProblemFavorite.objects.filter(user=request.user, problem=problem)
        if favorite.exists():
            favorite.delete()
            return JsonResponse({"is_favorite": False})

        ProblemFavorite.objects.create(user=request.user, problem=problem)
        return JsonResponse({"is_favorite": True})