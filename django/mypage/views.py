"""마이페이지 및 계정관리 화면."""
from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import FormView, TemplateView

from accounts.models import AccountChangeLog
from gamification.models import PointLog, UserMission
from problems.services.recommend import recommend_problems
from submissions.models import Submission
from wrongnotes.models import WrongNote

from .forms import (
    AccountDeleteConfirmForm,
    AccountEmailChangeForm,
    AccountPasswordChangeForm,
    AccountPasswordConfirmForm,
)

ACCOUNT_VERIFIED_SESSION_KEY = "mypage_account_verified_at"
ACCOUNT_VERIFY_TTL_SECONDS = 10 * 60


def mask_half(value: str) -> str:
    if not value:
        return "-"
    text = str(value)
    if len(text) <= 2:
        return text[0] + "*"
    visible = max(2, len(text) // 2)
    return text[:visible] + "*" * (len(text) - visible)


def mask_email(value: str) -> str:
    if not value or "@" not in value:
        return "-"
    local, domain = value.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[:2] + "*" * max(1, len(local) - 2)
    return f"{masked_local}@{domain}"


def mask_log_value(value: str, kind: str = "text") -> str:
    if kind == "password":
        return "********"
    if kind == "email":
        return mask_email(value)
    return mask_half(value)


def record_account_change(user, changed_by, change_type, field_name, old_value, new_value):
    AccountChangeLog.objects.create(
        user=user,
        changed_by=changed_by,
        change_type=change_type,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
    )


def account_verified(request) -> bool:
    raw_value = request.session.get(ACCOUNT_VERIFIED_SESSION_KEY)
    if not raw_value:
        return False
    try:
        verified_at = timezone.datetime.fromisoformat(raw_value)
        if timezone.is_naive(verified_at):
            verified_at = timezone.make_aware(verified_at, timezone.get_current_timezone())
    except (TypeError, ValueError):
        return False
    return timezone.now() - verified_at <= timedelta(seconds=ACCOUNT_VERIFY_TTL_SECONDS)


def require_account_verification(request):
    if not account_verified(request):
        messages.info(request, "계정정보 접근 전 비밀번호를 다시 확인해주세요.")
        return redirect("mypage:account_verify")
    return None


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
        visible_wrong_notes = wrong_notes_qs.filter(is_review_hidden=False) if hasattr(WrongNote, "is_review_hidden") else wrong_notes_qs
        ctx["submissions"] = (
            submissions_qs.select_related("problem").order_by("-created_at")[:10]
        )
        ctx["wrong_notes"] = (
            visible_wrong_notes.select_related("problem").order_by("-created_at")[:10]
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
            "wrong_note_count": visible_wrong_notes.count(),
            "reviewed_count": visible_wrong_notes.filter(is_reviewed=True).count(),
            "accuracy": round((success_count / total_submissions) * 100) if total_submissions else 0,
        }
        ctx["weak_patterns"] = (
            visible_wrong_notes.exclude(error_pattern="")
            .values("error_pattern")
            .annotate(count=Count("id"))
            .order_by("-count")[:4]
        )
        ctx["review_needed"] = (
            visible_wrong_notes.filter(is_reviewed=False)
            .select_related("problem")
            .order_by("-created_at")[:5]
        )
        ctx["recommended_problems"] = recommend_problems(user, limit=4)
        return ctx


class AvatarUpdateView(LoginRequiredMixin, View):
    """상단 프로필 팝업에서 동물 프로필을 선택한다."""

    def post(self, request, *args, **kwargs):
        user = request.user
        avatar_key = request.POST.get("avatar_key", "")
        catalog = {str(item["key"]): item for item in user.avatar_items}
        item = catalog.get(avatar_key)
        if not item:
            messages.error(request, "존재하지 않는 동물 프로필입니다.")
            return redirect(request.META.get("HTTP_REFERER") or "mypage:index")
        if not item["unlocked"]:
            messages.error(request, f"{item['name']} 프로필은 {item['required_point']}P부터 사용할 수 있습니다.")
            return redirect(request.META.get("HTTP_REFERER") or "mypage:index")
        user.selected_avatar = avatar_key
        user.save(update_fields=["selected_avatar"])
        messages.success(request, f"{item['icon']} {item['name']} 프로필로 변경했습니다.")
        return redirect(request.META.get("HTTP_REFERER") or "mypage:index")


class AccountVerifyView(LoginRequiredMixin, FormView):
    template_name = "mypage/account_verify.html"
    form_class = AccountPasswordConfirmForm
    success_url = reverse_lazy("mypage:account_detail")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        self.request.session[ACCOUNT_VERIFIED_SESSION_KEY] = timezone.now().isoformat()
        messages.success(self.request, "비밀번호 확인이 완료되었습니다.")
        return super().form_valid(form)


class AccountDetailView(LoginRequiredMixin, TemplateView):
    template_name = "mypage/account_detail.html"

    def dispatch(self, request, *args, **kwargs):
        redirect_response = require_account_verification(request)
        if redirect_response:
            return redirect_response
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["email_form"] = AccountEmailChangeForm(user=user, initial={"email": user.email})
        ctx["masked_user"] = {
            "username": mask_half(user.username),
            "email": mask_email(user.email),
            "password": "********",
            "first_name": mask_half(user.first_name) if user.first_name else "-",
        }
        ctx["account_logs"] = user.account_change_logs.all()[:10]
        return ctx

    def post(self, request, *args, **kwargs):
        redirect_response = require_account_verification(request)
        if redirect_response:
            return redirect_response
        form = AccountEmailChangeForm(request.POST, user=request.user)
        if not form.is_valid():
            ctx = self.get_context_data()
            ctx["email_form"] = form
            return self.render_to_response(ctx)
        old_email = request.user.email or ""
        new_email = form.cleaned_data["email"]
        request.user.email = new_email
        request.user.save(update_fields=["email"])
        record_account_change(
            request.user,
            request.user,
            AccountChangeLog.ChangeType.EMAIL,
            "email",
            mask_log_value(old_email, "email"),
            mask_log_value(new_email, "email"),
        )
        messages.success(request, "이메일을 변경했습니다.")
        return redirect("mypage:account_detail")


class AccountPasswordChangeView(LoginRequiredMixin, FormView):
    template_name = "mypage/password_change.html"
    form_class = AccountPasswordChangeForm
    success_url = reverse_lazy("mypage:account_detail")

    def dispatch(self, request, *args, **kwargs):
        redirect_response = require_account_verification(request)
        if redirect_response:
            return redirect_response
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = form.save()
        update_session_auth_hash(self.request, user)
        record_account_change(
            user,
            user,
            AccountChangeLog.ChangeType.PASSWORD,
            "password",
            "********",
            "********",
        )
        messages.success(self.request, "비밀번호를 변경했습니다.")
        return super().form_valid(form)


class AccountDeleteView(LoginRequiredMixin, FormView):
    template_name = "mypage/account_delete.html"
    form_class = AccountDeleteConfirmForm
    success_url = reverse_lazy("home")

    def dispatch(self, request, *args, **kwargs):
        redirect_response = require_account_verification(request)
        if redirect_response:
            return redirect_response
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = self.request.user
        logout(self.request)
        user.delete()
        messages.success(self.request, "회원 탈퇴가 완료되었습니다.")
        return super().form_valid(form)
