"""문제 목록/풀이 화면 (STEP-03).

권한: 로그인 필요(§6.1). 코드 실행(CodeRunView)·결과 조회는 STEP-04, Fetch 는 STEP-07.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, ListView

from config.choices import DIFFICULTY_CHOICES
from config.pagination import build_pagination_context
from submissions.models import Submission
from wrongnotes.models import WrongNote
from problems.services.recommendation import get_today_recommended_problems

from .models import Problem, ProblemCategory


class ProblemListView(LoginRequiredMixin, ListView):
    """문제 목록 + 카테고리/난이도/태그/검색 필터."""

    template_name = "problems/problem_list.html"
    context_object_name = "problems"
    paginate_by = 10

    def get_queryset(self):
        qs = (
            Problem.objects.filter(is_active=True)
            .select_related("category")
            .prefetch_related("tags")
            .order_by("id")
        )
        self.f_category = self.request.GET.get("category") or ""
        self.f_difficulty = self.request.GET.get("difficulty") or ""
        self.f_tag = self.request.GET.get("tag") or ""
        self.f_status = self.request.GET.get("status") or ""
        self.f_q = (self.request.GET.get("q") or "").strip()

        if self.f_category:
            qs = qs.filter(category__slug=self.f_category)
        if self.f_difficulty:
            qs = qs.filter(difficulty=self.f_difficulty)
        if self.f_tag:
            qs = qs.filter(tags__slug=self.f_tag)
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
            note_ids = WrongNote.objects.filter(user=user).values_list(
                "problem_id", flat=True
            )
            if self.f_status == "solved":
                qs = qs.filter(id__in=solved_ids)
            elif self.f_status == "unsolved":
                qs = qs.exclude(id__in=solved_ids)
            elif self.f_status == "wrong":
                qs = qs.filter(id__in=wrong_ids)
            elif self.f_status == "has_note":
                qs = qs.filter(id__in=note_ids)
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = ProblemCategory.objects.filter(is_active=True).order_by("name")
        ctx["difficulties"] = DIFFICULTY_CHOICES
        ctx["menu_items"] = [
            {
                "label": "전체",
                "category": "",
                "difficulty": "",
                "active": not self.f_category and not self.f_difficulty,
            },
            {
                "label": "자료구조",
                "category": "data-structures",
                "difficulty": "",
                "active": self.f_category == "data-structures" and not self.f_difficulty,
            },
            {
                "label": "알고리즘 초급",
                "category": "algorithms",
                "difficulty": "beginner",
                "active": self.f_category == "algorithms" and self.f_difficulty == "beginner",
            },
            {
                "label": "알고리즘 중급",
                "category": "algorithms",
                "difficulty": "intermediate",
                "active": self.f_category == "algorithms" and self.f_difficulty == "intermediate",
            },
            {
                "label": "알고리즘 고급",
                "category": "algorithms",
                "difficulty": "advanced",
                "active": self.f_category == "algorithms" and self.f_difficulty == "advanced",
            },
        ]
        ctx["cur_category"] = self.f_category
        ctx["cur_difficulty"] = self.f_difficulty
        ctx["cur_tag"] = self.f_tag
        ctx["cur_status"] = self.f_status
        ctx["q"] = self.f_q
        ctx["status_filters"] = [
            ("", "전체"),
            ("unsolved", "미해결"),
            ("solved", "해결 완료"),
            ("wrong", "오답 제출"),
            ("has_note", "오답노트 있음"),
        ]
        ctx["recommended_problems"] = get_today_recommended_problems(self.request.user, limit=3)
        ctx["recent_wrong_notes"] = (
            WrongNote.objects.filter(user=self.request.user)
            .select_related("problem")
            .order_by("-created_at")[:3]
        )
        ctx["today_problem"] = ctx["recommended_problems"][0] if ctx["recommended_problems"] else None
        if ctx.get("page_obj"):
            ctx["pagination"] = build_pagination_context(
                self.request,
                ctx["page_obj"],
            )
        return ctx


class ProblemDetailView(LoginRequiredMixin, DetailView):
    """문제 풀이 화면 (문제 + 샘플 테스트케이스 + 코드 에디터 DOM)."""

    model = Problem
    template_name = "problems/problem_solve.html"
    context_object_name = "problem"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sample_cases = list(self.object.test_cases.filter(is_sample=True).order_by("id")[:3])
        if len(sample_cases) < 3:
            extra_cases = list(
                self.object.test_cases.filter(is_sample=False)
                .order_by("id")[: 3 - len(sample_cases)]
            )
            sample_cases.extend(extra_cases)
        ctx["sample_cases"] = self.object.test_cases.filter(is_sample=True).order_by("id")
        ctx["visible_test_cases"] = sample_cases
        return ctx
