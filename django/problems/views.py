"""문제 목록/풀이 화면 (STEP-03).

권한: 로그인 필요(§6.1). 코드 실행(CodeRunView)·결과 조회는 STEP-04, Fetch 는 STEP-07.
"""
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
    """문제 목록 + 난이도/상태/검색/정렬 필터.

    기획 변경(2026-07): 카테고리 드롭다운은 제거하고 난이도 하나로 통일했다.
    상태 필터는 전체/미해결/오답제출/해결완료/즐겨찾기 5종으로 구성한다.
    """

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
            favorite_ids = ProblemFavorite.objects.filter(user=user).values_list(
                "problem_id", flat=True
            )
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

        # 상태 필터: 전체 / 미해결 / 오답 제출 / 해결 완료 / 즐겨찾기
        ctx["status_filters"] = [
            ("", "전체"),
            ("unsolved", "미해결"),
            ("wrong", "오답 제출"),
            ("solved", "해결 완료"),
            ("favorite", "즐겨찾기"),
        ]

        # 상단 빠른 탭: 전체 + 난이도 4종 (select box와 동일한 축을 다른 UI로 한 번 더 제공)
        menu_items = [
            {"label": "전체", "difficulty": "", "active": not self.f_difficulty}
        ]
        for value, label in DIFFICULTY_CHOICES:
            menu_items.append(
                {
                    "label": label,
                    "difficulty": value,
                    "active": self.f_difficulty == value,
                }
            )
        ctx["menu_items"] = menu_items

        favorite_ids = set(
            ProblemFavorite.objects.filter(user=user).values_list("problem_id", flat=True)
        )
        ctx["favorite_ids"] = favorite_ids

        user_submissions = Submission.objects.filter(user=user, submission_type="submit")
        ctx["quick_links"] = {
            "solved_count": user_submissions.filter(result="success")
            .values("problem_id").distinct().count(),
            "favorite_count": len(favorite_ids),
            "recent_count": user_submissions.order_by("-created_at")
            .values("problem_id").distinct()[:20].count(),
            "note_count": WrongNote.objects.filter(user=user).count(),
        }
        ctx["recent_submissions"] = (
            user_submissions.select_related("problem")
            .order_by("-created_at")[:4]
        )
        ctx["today_problem"] = (
            Problem.objects.filter(is_active=True)
            .select_related("category")
            .prefetch_related("tags")
            .order_by("?")
            .first()
        )
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
        ctx["is_favorited"] = ProblemFavorite.objects.filter(
            user=self.request.user, problem=self.object
        ).exists()
        return ctx


class ToggleFavoriteView(LoginRequiredMixin, View):
    """문제 목록/풀이 화면의 ☆ 버튼용 즐겨찾기 토글 API.

    POST만 허용한다. 이미 즐겨찾기면 삭제(해제), 없으면 생성(등록)한다.
    응답: {"is_favorite": true|false}
    """

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