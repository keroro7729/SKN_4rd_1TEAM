"""운영자 대시보드/로그 화면 (STEP-03).

권한: role=admin 또는 is_staff (CustomUser.is_service_admin)만 접근(§6.1). 로그 조회 보완은 STEP-08.
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView

from accounts.models import CustomUser
from logs.models import ErrorLog, LLMRequestLog
from problems.models import Problem
from submissions.models import ExecutionJob, Submission
from wrongnotes.models import WrongNote


class AdminOnlyMixin(LoginRequiredMixin, UserPassesTestMixin):
    """서비스 관리자(role=admin 또는 staff)만 허용."""

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.is_service_admin


class AdminDashboardView(AdminOnlyMixin, TemplateView):
    template_name = "adminpanel/admin_dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["stats"] = {
            "users": CustomUser.objects.count(),
            "problems": Problem.objects.count(),
            "submissions": Submission.objects.count(),
            "wrong_notes": WrongNote.objects.count(),
            "pending_jobs": ExecutionJob.objects.filter(status="pending").count(),
            "unresolved_errors": ErrorLog.objects.filter(is_resolved=False).count(),
        }
        return ctx


class AdminLogListView(AdminOnlyMixin, TemplateView):
    template_name = "adminpanel/logs.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["error_logs"] = ErrorLog.objects.order_by("-created_at")[:50]
        ctx["llm_logs"] = LLMRequestLog.objects.order_by("-created_at")[:50]
        ctx["jobs"] = (
            ExecutionJob.objects.select_related("submission").order_by("-created_at")[:50]
        )
        return ctx
