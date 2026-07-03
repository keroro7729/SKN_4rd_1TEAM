"""문제 URL: /problems/, /problems/<id>/."""
from django.urls import path

from . import views

app_name = "problems"

urlpatterns = [
    path("", views.ProblemListView.as_view(), name="list"),
    path("<int:pk>/", views.ProblemDetailView.as_view(), name="detail"),
]
