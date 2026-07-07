"""Forms for MyPage account management."""
from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import PasswordChangeForm


class AccountPasswordConfirmForm(forms.Form):
    password = forms.CharField(
        label="비밀번호",
        widget=forms.PasswordInput(attrs={"class": "game-input", "autocomplete": "current-password"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        password = self.cleaned_data["password"]
        if self.user is None:
            raise forms.ValidationError("사용자 정보를 확인할 수 없습니다.")
        authenticated = authenticate(username=self.user.get_username(), password=password)
        if authenticated is None:
            raise forms.ValidationError("비밀번호가 일치하지 않습니다.")
        return password


class AccountEmailChangeForm(forms.Form):
    email = forms.EmailField(
        label="이메일",
        max_length=254,
        widget=forms.EmailInput(attrs={"class": "game-input", "autocomplete": "email"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None and not self.is_bound:
            self.fields["email"].initial = user.email


class AccountPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": "game-input"})


class AccountDeleteConfirmForm(forms.Form):
    password = forms.CharField(
        label="비밀번호",
        widget=forms.PasswordInput(attrs={"class": "game-input", "autocomplete": "current-password"}),
    )
    confirm_delete = forms.BooleanField(
        label="탈퇴 시 모든 정보가 삭제됨을 확인했습니다.",
        required=True,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        password = self.cleaned_data["password"]
        if self.user is None:
            raise forms.ValidationError("사용자 정보를 확인할 수 없습니다.")
        authenticated = authenticate(username=self.user.get_username(), password=password)
        if authenticated is None:
            raise forms.ValidationError("비밀번호가 일치하지 않습니다.")
        return password