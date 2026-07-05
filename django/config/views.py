"""최상위 화면 뷰."""
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from gamification.models import Mission
from notices.models import Notice
from problems.models import Problem
from submissions.models import Submission
from wrongnotes.models import WrongNote


class HomeView(TemplateView):
    """홈: 공지 + 진행 가능한 미션 노출 (비로그인 접근 허용)."""

    template_name = "home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["notices"] = Notice.objects.filter(is_published=True)[:5]
        ctx["missions"] = Mission.objects.filter(is_active=True)[:5]
        ctx["recommended_problems"] = (
            Problem.objects.filter(is_active=True)
            .select_related("category")
            .prefetch_related("tags")
            .order_by("id")[:3]
        )
        if self.request.user.is_authenticated:
            ctx["recent_wrong_notes"] = (
                WrongNote.objects.filter(user=self.request.user)
                .select_related("problem")
                .order_by("-created_at")[:3]
            )
            ctx["recent_submissions"] = (
                Submission.objects.filter(
                    user=self.request.user,
                    submission_type="submit",
                )
                .select_related("problem")
                .order_by("-created_at")[:3]
            )
        return ctx


class HealthCheckView(View):
    """컨테이너 준비 상태 확인용 경량 엔드포인트."""

    def get(self, request, *args, **kwargs):
        return JsonResponse({"status": "ok"})
