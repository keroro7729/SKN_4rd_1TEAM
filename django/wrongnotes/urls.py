"""오답노트 URL: /wrongnotes/, /wrongnotes/ask/, /wrongnotes/create/<submission_id>/."""
from django.urls import path

from . import views

app_name = "wrongnotes"

urlpatterns = [
    path("", views.WrongNoteListView.as_view(), name="list"),
    path("ask/", views.NoteAskView.as_view(), name="ask"),
    path("create/<int:submission_id>/", views.WrongNoteCreateView.as_view(), name="create"),
    path("<int:note_id>/review/", views.review_wrong_note, name="review"),
]
