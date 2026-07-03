"""마이페이지 화면 (STEP-03). 본인 데이터만 조회(§6.1). 포인트/미션 보완은 STEP-08."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from gamification.models import PointLog, UserMission
from submissions.models import Submission
from wrongnotes.models import WrongNote


class MyPageView(LoginRequiredMixin, TemplateView):
    template_name = "mypage/mypage.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["submissions"] = (
            Submission.objects.filter(user=user)
            .select_related("problem")
            .order_by("-created_at")[:10]
        )
        ctx["wrong_notes"] = (
            WrongNote.objects.filter(user=user)
            .select_related("problem")
            .order_by("-created_at")[:10]
        )
        ctx["point_logs"] = PointLog.objects.filter(user=user).order_by("-created_at")[:10]
        ctx["user_missions"] = (
            UserMission.objects.filter(user=user).select_related("mission")
        )
        return ctx
