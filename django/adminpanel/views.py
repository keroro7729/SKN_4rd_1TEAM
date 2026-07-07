"""운영자 대시보드/로그/AI 실험 랩 화면.

권한: role=admin 또는 is_staff (CustomUser.is_service_admin)만 접근(§6.1).
"""
import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from ai_proxy.client import call_fastapi

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


class AiLabView(AdminOnlyMixin, TemplateView):
    """AI 실험 랩: 에이전트 그래프 조회 + 단일 노드 프롬프트 주입/실행/비교."""

    template_name = "adminpanel/ai_lab.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        result = call_fastapi(
            user=self.request.user,
            request_type="ai_lab",
            path="/ai/lab/graph",
            payload={},
        )
        ctx["graph"] = result.data if result.status == "success" else {"agents": [], "nodes": {}}
        ctx["graph_ok"] = result.status == "success"
        ctx["graph_error"] = "" if result.status == "success" else (result.message or "FastAPI 연결 실패")
        return ctx


@login_required
@require_POST
def ai_lab_run(request):
    """단일 노드 실행 프록시 (관리자 전용). FastAPI /ai/lab/run 으로 전달."""
    if not request.user.is_service_admin:
        return JsonResponse({"status": "failed", "message": "forbidden", "data": {}}, status=403)
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"status": "failed", "message": "invalid_json", "data": {}}, status=400)

    result = call_fastapi(
        user=request.user,
        request_type="ai_lab",
        path="/ai/lab/run",
        payload={
            "node_id": body.get("node_id") or "",
            "inputs": body.get("inputs") or {},
            "system": body.get("system") or "",
            "user": body.get("user") or "",
            "model": body.get("model") or "",
        },
        timeout=90,
    )
    http_status = 200 if result.status in {"success", "empty"} else 502
    return JsonResponse(result.to_response(), status=http_status)
