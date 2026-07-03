"""공지사항 관리자 화면."""
from django.contrib import admin

from .models import Notice


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "is_published", "created_at", "updated_at")
    list_filter = ("is_published", "created_at")
    search_fields = ("title", "content")
    raw_id_fields = ("author",)
