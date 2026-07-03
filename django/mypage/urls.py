"""마이페이지 URL: /mypage/."""
from django.urls import path

from . import views

app_name = "mypage"

urlpatterns = [
    path("", views.MyPageView.as_view(), name="index"),
]
