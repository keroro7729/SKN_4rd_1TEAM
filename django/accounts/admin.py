"""회원 관리자 화면 (기본 관리자 화면 / F-02, F-15 기반)."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Django admin에 CustomUser 등록 + 서비스 필드 노출."""

    list_display = (
        "username",
        "email",
        "role",
        "point",
        "is_subscribed",
        "is_staff",
        "date_joined",
    )
    list_filter = ("role", "is_subscribed", "is_staff", "is_superuser")
    search_fields = ("username", "email")
    ordering = ("-date_joined",)

    # 기존 UserAdmin 구성에 서비스 전용 필드 추가
    fieldsets = UserAdmin.fieldsets + (
        ("WOOK'S CODING", {"fields": ("role", "point", "is_subscribed")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("WOOK'S CODING", {"fields": ("role", "point", "is_subscribed")}),
    )
