"""회원 URL: /accounts/signup/, /accounts/login/, /accounts/logout/."""
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from .views import SignupView

app_name = "accounts"

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path(
        "login/",
        LoginView.as_view(template_name="accounts/login.html"),
        name="login",
    ),
    path("logout/", LogoutView.as_view(), name="logout"),
]
