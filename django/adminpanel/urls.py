"""운영자 대시보드 URL: /adminpanel/, /adminpanel/logs/."""
from django.urls import path

from . import views

app_name = "adminpanel"

urlpatterns = [
    path("", views.AdminDashboardView.as_view(), name="dashboard"),
    path("logs/", views.AdminLogListView.as_view(), name="logs"),
    path("ai-lab/", views.AiLabView.as_view(), name="ai_lab"),
    path("ai-lab/run/", views.ai_lab_run, name="ai_lab_run"),
]
