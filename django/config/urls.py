"""WOOK'S CODING URL routing."""
from django.contrib import admin
from django.urls import include, path

from config.views import HealthCheckView, HomeView

admin.site.site_header = "WOOK'S CODING 관리자"
admin.site.site_title = "WOOK'S CODING Admin"
admin.site.index_title = "서비스 운영 관리"

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("ai-proxy/", include("ai_proxy.urls")),
    path("problems/", include("problems.urls")),
    path("submissions/", include("submissions.urls")),
    path("wrongnotes/", include("wrongnotes.urls")),
    path("mypage/", include("mypage.urls")),
    path("notices/", include("notices.urls")),
    path("adminpanel/", include("adminpanel.urls")),
    path("", HomeView.as_view(), name="home"),
]