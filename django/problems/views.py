"""문제 목록/풀이 화면 (STEP-03).

권한: 로그인 필요(§6.1). 코드 실행(CodeRunView)·결과 조회는 STEP-04, Fetch 는 STEP-07.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, ListView

from config.choices import DIFFICULTY_CHOICES
from config.pagination import build_pagination_context

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
        self.f_q = (self.request.GET.get("q") or "").strip()

        if self.f_category:
            qs = qs.filter(category__slug=self.f_category)
        if self.f_difficulty:
            qs = qs.filter(difficulty=self.f_difficulty)
        if self.f_tag:
            qs = qs.filter(tags__slug=self.f_tag)
        if self.f_q:
            qs = qs.filter(title__icontains=self.f_q)
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
        ctx["q"] = self.f_q
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
        ctx["sample_cases"] = self.object.test_cases.filter(is_sample=True)
        return ctx
