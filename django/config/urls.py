"""WOOK'S CODING - 최상위 URL 라우팅."""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

# 관리자 화면 헤더/타이틀 커스터마이즈
admin.site.site_header = "WOOK'S CODING 관리자"
admin.site.site_title = "WOOK'S CODING Admin"
admin.site.index_title = "서비스 운영 관리"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
]
