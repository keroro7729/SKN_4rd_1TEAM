"""마이페이지 화면 (STEP-03). 본인 데이터만 조회(§6.1). 포인트/미션 보완은 STEP-08."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from gamification.models import PointLog, UserMission
from submissions.models import Submission
from wrongnotes.models import WrongNote


class MyPageView(LoginRequiredMixin, TemplateView):
    template_name = "mypage/mypage.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        submissions_qs = Submission.objects.filter(
            user=user,
            submission_type="submit",
        )
        wrong_notes_qs = WrongNote.objects.filter(user=user)
        ctx["submissions"] = (
            submissions_qs
            .select_related("problem")
            .order_by("-created_at")[:10]
        )
        ctx["wrong_notes"] = (
            wrong_notes_qs
            .select_related("problem")
            .order_by("-created_at")[:10]
        )
        ctx["point_logs"] = PointLog.objects.filter(user=user).order_by("-created_at")[:10]
        ctx["user_missions"] = (
            UserMission.objects.filter(user=user).select_related("mission")
        )
        total_submissions = submissions_qs.count()
        success_count = submissions_qs.filter(result="success").count()
        wrong_count = submissions_qs.filter(result__in=["wrong", "error", "timeout"]).count()
        ctx["summary"] = {
            "total_submissions": total_submissions,
            "success_count": success_count,
            "wrong_count": wrong_count,
            "wrong_note_count": wrong_notes_qs.count(),
            "reviewed_count": wrong_notes_qs.filter(is_reviewed=True).count(),
            "accuracy": round((success_count / total_submissions) * 100)
            if total_submissions
            else 0,
        }
        ctx["weak_patterns"] = (
            wrong_notes_qs.exclude(error_pattern="")
            .values("error_pattern")
            .annotate(count=Count("id"))
            .order_by("-count")[:4]
        )
        ctx["review_needed"] = (
            wrong_notes_qs.filter(is_reviewed=False)
            .select_related("problem")
            .order_by("-created_at")[:5]
        )
        return ctx


class AvatarUpdateView(LoginRequiredMixin, View):
    """상단 프로필 팝업에서 동물 프로필을 선택한다."""

    def post(self, request, *args, **kwargs):
        user = request.user
        avatar_key = request.POST.get("avatar_key", "")
        catalog = {str(item["key"]): item for item in user.avatar_catalog()}
        item = catalog.get(avatar_key)
        if not item:
            messages.error(request, "존재하지 않는 동물 프로필입니다.")
            return redirect(request.META.get("HTTP_REFERER") or "mypage:index")

        required_point = int(item["required_point"])
        if (user.point or 0) < required_point:
            messages.error(request, f"{item['name']} 프로필은 {required_point}P부터 사용할 수 있습니다.")
            return redirect(request.META.get("HTTP_REFERER") or "mypage:index")

        user.selected_avatar = avatar_key
        user.save(update_fields=["selected_avatar"])
        messages.success(request, f"{item['icon']} {item['name']} 프로필로 변경했습니다.")
        return redirect(request.META.get("HTTP_REFERER") or "mypage:index")
