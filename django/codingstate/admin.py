"""코딩 상태 관리자(운영 확인용)."""
from django.contrib import admin

from .models import CodingState


@admin.register(CodingState)
class CodingStateAdmin(admin.ModelAdmin):
    list_display = ("user", "level", "source_submission_count", "updated_at")
    search_fields = ("user__username",)
    readonly_fields = ("created_at", "updated_at")
