"""회원 폼."""
from django.contrib.auth.forms import UserCreationForm

from .models import CustomUser


class SignupForm(UserCreationForm):
    """회원가입 폼 (F-01)."""

    class Meta:
        model = CustomUser
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 도트/레트로 톤 UI에 맞춘 placeholder
        self.fields["username"].widget.attrs.update({"placeholder": "아이디"})
        self.fields["email"].widget.attrs.update({"placeholder": "이메일 (선택)"})
        self.fields["email"].required = False
        self.fields["password1"].widget.attrs.update({"placeholder": "비밀번호"})
        self.fields["password2"].widget.attrs.update({"placeholder": "비밀번호 확인"})
