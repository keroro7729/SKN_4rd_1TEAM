"""MyPage views and account management."""
from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import FormView, TemplateView

from accounts.models import AccountChangeLog, calculate_user_level
from gamification.models import PointLog, UserMission
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


def account_level(point: int) -> int:
    return calculate_user_level(point)


def mask_half(value: str) -> str:
    text = value or ""
    if not text:
        return "-"
    if len(text) <= 2:
        return text[0] + "*" * max(1, len(text) - 1)
    visible = max(1, len(text) // 2)
    return text[:visible] + "*" * (len(text) - visible)


def mask_email(email: str) -> str:
    text = email or ""
    if not text:
        return "-"
    if "@" not in text:
        return mask_half(text)
    local, domain = text.split("@", 1)
    return f"{mask_half(local)}@{domain}"


def mask_log_value(field_name: str, value: str) -> str:
    if field_name == "이메일":
        return mask_email(value)
    if field_name == "비밀번호":
        return "********"
    return mask_half(value)


def account_verified(request) -> bool:
    verified_at = request.session.get(ACCOUNT_VERIFIED_SESSION_KEY)
    if not verified_at:
        return False
    try:
        verified_time = timezone.datetime.fromisoformat(verified_at)
    except ValueError:
        return False
    if timezone.is_naive(verified_time):
        verified_time = timezone.make_aware(verified_time, timezone.get_current_timezone())
    return (timezone.now() - verified_time).total_seconds() <= ACCOUNT_VERIFY_TTL_SECONDS


def require_account_verification(view_func):
    def wrapped(self, request, *args, **kwargs):
        if not account_verified(request):
            messages.warning(request, "계정정보 확인을 위해 비밀번호를 다시 입력해주세요.")
            return redirect("mypage:account_verify")
        return view_func(self, request, *args, **kwargs)

    return wrapped


def record_account_change(user, changed_by, change_type: str, field_name: str, old_value: str, new_value: str) -> None:
    AccountChangeLog.objects.create(
        user=user,
        changed_by=changed_by if getattr(changed_by, "is_authenticated", False) else None,
        change_type=change_type,
        field_name=field_name,
        old_value=mask_log_value(field_name, old_value),
        new_value=mask_log_value(field_name, new_value),
    )


class MyPageView(LoginRequiredMixin, TemplateView):
    template_name = "mypage/mypage.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        submissions_qs = Submission.objects.filter(user=user, submission_type="submit")
        wrong_notes_qs = WrongNote.objects.filter(user=user)
        total_submissions = submissions_qs.count()
        success_count = submissions_qs.filter(result="success").count()
        ctx["recent_submissions"] = submissions_qs.select_related("problem").order_by("-created_at")[:6]
        ctx["wrong_notes"] = wrong_notes_qs.select_related("problem").order_by("-created_at")[:5]
        ctx["point_logs"] = PointLog.objects.filter(user=user).order_by("-created_at")[:5]
        ctx["user_missions"] = UserMission.objects.filter(user=user).select_related("mission")[:4]
        ctx["summary"] = {
            "total_submissions": total_submissions,
            "success_count": success_count,
            "wrong_note_count": wrong_notes_qs.count(),
            "reviewed_count": wrong_notes_qs.filter(is_reviewed=True).count(),
            "accuracy": round((success_count / total_submissions) * 100) if total_submissions else 0,
            "level": user.level,
        }
        ctx["weak_patterns"] = (
            wrong_notes_qs.exclude(error_pattern="")
            .values("error_pattern")
            .annotate(count=Count("id"))
            .order_by("-count")[:4]
        )
        return ctx


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
        self.request.session.modified = True
        return super().form_valid(form)


class AccountDetailView(LoginRequiredMixin, FormView):
    template_name = "mypage/account_detail.html"
    form_class = AccountEmailChangeForm
    success_url = reverse_lazy("mypage:account_detail")

    @require_account_verification
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["is_editing_email"] = self.request.GET.get("edit") == "email" or self.request.method == "POST"
        ctx["account"] = {
            "username": mask_half(user.get_username()),
            "full_name": (f"{user.last_name}{user.first_name}" or user.get_username()).strip(),
            "email": mask_email(user.email),
            "password": "********",
            "joined_at": user.date_joined,
            "last_login": user.last_login,
            "level": user.level,
            "point": user.point,
            "role": user.get_role_display() if hasattr(user, "get_role_display") else user.role,
            "is_subscribed": user.is_subscribed,
        }
        ctx["change_logs"] = AccountChangeLog.objects.filter(user=user).select_related("changed_by")[:10]
        return ctx

    def form_valid(self, form):
        user = self.request.user
        old_email = user.email or ""
        new_email = form.cleaned_data["email"]
        if old_email != new_email:
            user.email = new_email
            user.save(update_fields=["email"])
            record_account_change(user, user, AccountChangeLog.ChangeType.EMAIL, "이메일", old_email, new_email)
            messages.success(self.request, "이메일이 저장되었습니다.")
        else:
            messages.info(self.request, "변경된 이메일이 없습니다.")
        return super().form_valid(form)


class AccountPasswordChangeView(LoginRequiredMixin, FormView):
    template_name = "mypage/password_change.html"
    form_class = AccountPasswordChangeForm
    success_url = reverse_lazy("mypage:account_detail")

    @require_account_verification
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        update_session_auth_hash(self.request, form.user)
        record_account_change(
            form.user,
            self.request.user,
            AccountChangeLog.ChangeType.PASSWORD,
            "비밀번호",
            "********",
            "********",
        )
        messages.success(self.request, "비밀번호가 변경되었습니다.")
        return super().form_valid(form)


class AccountDeleteView(LoginRequiredMixin, FormView):
    template_name = "mypage/account_delete.html"
    form_class = AccountDeleteConfirmForm
    success_url = reverse_lazy("home")

    @require_account_verification
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = self.request.user
        username = user.get_username()
        logout(self.request)
        user.delete()
        messages.success(self.request, f"{username} 계정이 탈퇴 처리되었습니다.")
        return super().form_valid(form)