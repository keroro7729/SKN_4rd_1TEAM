"""제출/실행 URL: /submissions/run/, /submissions/<id>/result/."""
from django.urls import path

from . import views

app_name = "submissions"

urlpatterns = [
    path("run/", views.CodeRunView.as_view(), name="run"),
    path("<int:pk>/result/", views.SubmissionResultView.as_view(), name="result"),
]
