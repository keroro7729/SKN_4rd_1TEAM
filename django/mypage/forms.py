from __future__ import annotations

from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError


class AccountPasswordConfirmForm(forms.Form):
    password = forms.CharField(
        label="비밀번호",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "placeholder": "현재 비밀번호"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user or not self.user.check_password(password):
            raise ValidationError("비밀번호가 올바르지 않습니다.")
        return password


class AccountEmailChangeForm(forms.Form):
    email = forms.EmailField(
        label="새 이메일",
        required=True,
        widget=forms.EmailInput(attrs={"placeholder": "새 이메일 주소", "autocomplete": "email"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if self.user and email == (self.user.email or ""):
            raise ValidationError("현재 이메일과 동일합니다.")
        UserModel = get_user_model()
        if UserModel.objects.exclude(pk=getattr(self.user, "pk", None)).filter(email=email).exists():
            raise ValidationError("이미 다른 계정에서 사용 중인 이메일입니다.")
        return email


class AccountPasswordChangeForm(PasswordChangeForm):
    pass


class AccountDeleteConfirmForm(forms.Form):
    password = forms.CharField(
        label="비밀번호 재입력",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "placeholder": "현재 비밀번호"}),
    )
    confirm = forms.BooleanField(
        label="회원 탈퇴 내용을 확인했습니다.",
        required=True,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user or not self.user.check_password(password):
            raise ValidationError("비밀번호가 올바르지 않습니다.")
        return password
