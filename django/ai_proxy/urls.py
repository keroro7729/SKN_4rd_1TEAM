"""Django AI/RAG proxy URLs for frontend Fetch calls."""
from django.urls import path

from . import views

app_name = "ai_proxy"

urlpatterns = [
    path("hint/", views.hint, name="hint"),
    path("wrong-note/search/", views.wrong_note_search, name="wrong_note_search"),
    path("wrong-note/analyze/", views.wrong_note_analyze, name="wrong_note_analyze"),
    path("wrong-note/embed/", views.wrong_note_embed, name="wrong_note_embed"),
    path("wrong-note/ask/", views.note_ask, name="note_ask"),
]
