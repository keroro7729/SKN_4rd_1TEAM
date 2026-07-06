"""Notice URLs."""
from django.urls import path

from . import views

app_name = "notices"

urlpatterns = [
    path("", views.NoticeListView.as_view(), name="list"),
    path("<int:pk>/", views.NoticeDetailView.as_view(), name="detail"),
]
