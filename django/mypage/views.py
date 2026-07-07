"""마이페이지 화면 (STEP-03). 본인 데이터만 조회(§6.1)."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
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
        ctx["avatar_items"] = user.avatar_items
        ctx["next_locked_avatar"] = user.next_locked_avatar
        return ctx


class AvatarUpdateView(LoginRequiredMixin, View):
    """포인트 조건을 만족한 동물 프로필만 선택한다."""

    def post(self, request, *args, **kwargs):
        avatar_key = request.POST.get("avatar_key", "").strip()
        avatar = request.user.get_avatar_config(avatar_key)
        if not avatar:
            messages.error(request, "존재하지 않는 프로필입니다.")
            return redirect("mypage:index")

        if not request.user.can_use_avatar(avatar_key):
            messages.warning(
                request,
                f"{avatar['name']} 프로필은 {avatar['required_point']}P부터 사용할 수 있습니다.",
            )
            return redirect("mypage:index")

        request.user.selected_avatar = avatar_key
        request.user.save(update_fields=["selected_avatar"])
        messages.success(request, f"프로필을 {avatar['icon']} {avatar['name']}로 변경했습니다.")
        return redirect("mypage:index")


class LearningHistoryView(LoginRequiredMixin, TemplateView):
    template_name = "mypage/learning_history.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        qs = (
            Submission.objects.filter(user=user, submission_type="submit")
            .select_related("problem", "problem__category")
            .prefetch_related("problem__tags")
            .order_by("-created_at")
        )

        self.f_result = self.request.GET.get("result") or ""
        self.f_q = (self.request.GET.get("q") or "").strip()
        self.f_category = self.request.GET.get("category") or ""

        if self.f_result:
            if self.f_result == "wrong_group":
                qs = qs.filter(result__in=["wrong", "error", "timeout"])
            elif self.f_result == "has_note":
                note_problem_ids = WrongNote.objects.filter(user=user).values_list(
                    "problem_id", flat=True
                )
                qs = qs.filter(problem_id__in=note_problem_ids)
            else:
                qs = qs.filter(result=self.f_result)
        if self.f_q:
            search_filter = (
                Q(problem__title__icontains=self.f_q)
                | Q(problem__tags__name__icontains=self.f_q)
            )
            if self.f_q.isdigit():
                search_filter |= Q(problem__id=int(self.f_q))
            qs = qs.filter(search_filter)
        if self.f_category:
            qs = qs.filter(problem__category__slug=self.f_category)

        all_submissions = Submission.objects.filter(
            user=user,
            submission_type="submit",
        )
        ctx["records"] = qs.distinct()[:50]
        ctx["q"] = self.f_q
        ctx["cur_result"] = self.f_result
        ctx["cur_category"] = self.f_category
        ctx["result_filters"] = [
            ("", "전체"),
            ("success", "정답"),
            ("wrong_group", "오답"),
            ("has_note", "오답노트 있음"),
        ]
        ctx["summary"] = {
            "total": all_submissions.count(),
            "success": all_submissions.filter(result="success").count(),
            "wrong": all_submissions.filter(result__in=["wrong", "error", "timeout"]).count(),
            "notes": WrongNote.objects.filter(user=user).count(),
        }
        ctx["review_needed"] = (
            WrongNote.objects.filter(user=user, is_reviewed=False)
            .select_related("problem")
            .order_by("-created_at")[:5]
        )
        return ctx
