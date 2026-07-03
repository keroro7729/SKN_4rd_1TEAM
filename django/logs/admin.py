"""운영 로그 관리자 화면."""
from django.contrib import admin

from .models import ErrorLog, LLMRequestLog


@admin.register(LLMRequestLog)
class LLMRequestLogAdmin(admin.ModelAdmin):
    list_display = ("id", "request_type", "request_id", "status", "user", "created_at")
    list_filter = ("request_type", "status", "created_at")
    search_fields = ("request_id",)
    raw_id_fields = ("user",)


@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "level", "error_type", "is_resolved", "created_at")
    list_filter = ("source", "level", "is_resolved", "created_at")
    search_fields = ("message", "error_type")
    raw_id_fields = ("user",)
