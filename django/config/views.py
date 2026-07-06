"""Top-level page views."""
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from gamification.models import Mission
from notices.models import Notice
from problems.services.recommendation import get_today_recommended_problems


class HomeView(TemplateView):
    """Home page with notices, missions, and daily-random recommendations."""

    template_name = "home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["notices"] = Notice.objects.filter(is_published=True)[:5]
        ctx["missions"] = Mission.objects.filter(is_active=True)[:5]
        ctx["recommended_problems"] = get_today_recommended_problems(
            self.request.user,
            limit=3,
        )
        return ctx


class HealthCheckView(View):
    """Lightweight container readiness endpoint."""

    def get(self, request, *args, **kwargs):
        return JsonResponse({"status": "ok"})
