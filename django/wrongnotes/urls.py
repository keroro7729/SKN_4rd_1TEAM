"""오답노트 URL: /wrongnotes/, /wrongnotes/create/<submission_id>/."""
from django.urls import path

from . import views

app_name = "wrongnotes"

urlpatterns = [
    path("", views.WrongNoteListView.as_view(), name="list"),
    path("create/<int:submission_id>/", views.WrongNoteCreateView.as_view(), name="create"),
    path("<int:note_id>/", views.WrongNoteDetailView.as_view(), name="detail"),
    path("<int:note_id>/review/", views.review_wrong_note, name="review"),
    path("<int:note_id>/hide/", views.hide_from_review_board, name="hide"),
    path("<int:note_id>/restore/", views.restore_to_review_board, name="restore"),
]
