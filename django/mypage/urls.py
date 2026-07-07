"""MyPage URLs."""
from django.urls import path

from . import views

app_name = "mypage"

urlpatterns = [
    path("", views.MyPageView.as_view(), name="index"),
    path("account/", views.AccountVerifyView.as_view(), name="account_verify"),
    path("account/detail/", views.AccountDetailView.as_view(), name="account_detail"),
    path("account/password/", views.AccountPasswordChangeView.as_view(), name="password_change"),
    path("account/delete/", views.AccountDeleteView.as_view(), name="account_delete"),
]