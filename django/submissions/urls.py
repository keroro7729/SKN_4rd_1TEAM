"""Submission API URLs."""
from django.urls import path

from . import views

app_name = "submissions"

urlpatterns = [
    path("run/", views.run_submission, name="run"),
    path("submit/", views.submit_submission, name="submit"),
    path("<int:submission_id>/result/", views.submission_result, name="result"),
]
