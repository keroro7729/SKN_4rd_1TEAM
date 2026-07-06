"""마이페이지 URL: /mypage/."""
from django.urls import path

from . import views

app_name = "mypage"

urlpatterns = [
    path("", views.MyPageView.as_view(), name="index"),
    path("history/", views.LearningHistoryView.as_view(), name="history"),
    path("password/", views.MyPasswordChangeView.as_view(), name="password_change"),
]
