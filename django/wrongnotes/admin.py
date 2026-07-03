"""오답노트 관리자 화면."""
from django.contrib import admin

from .models import WrongNote, WrongNoteQueryLog, WrongNoteVector


@admin.register(WrongNote)
class WrongNoteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "problem", "status", "is_reviewed", "created_at")
    list_filter = ("status", "is_reviewed", "created_at")
    search_fields = ("user__username", "problem__title", "comment")
    filter_horizontal = ("tags",)
    raw_id_fields = ("user", "problem", "submission")


@admin.register(WrongNoteVector)
class WrongNoteVectorAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "wrong_note", "embedding_id", "source", "indexed_at")
    raw_id_fields = ("user", "wrong_note")


@admin.register(WrongNoteQueryLog)
class WrongNoteQueryLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "query", "created_at")
    search_fields = ("user__username", "query")
    raw_id_fields = ("user",)
