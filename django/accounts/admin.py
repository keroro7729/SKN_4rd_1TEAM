"""회원 관리자 화면."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AccountChangeLog, CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Django admin에 CustomUser 등록 + 서비스 필드 노출."""

    list_display = (
        "username",
        "email",
        "role",
        "point",
        "level",
        "selected_avatar",
        "is_subscribed",
        "is_staff",
        "date_joined",
    )
    list_filter = ("role", "level", "selected_avatar", "is_subscribed", "is_staff", "is_superuser")
    search_fields = ("username", "email")
    ordering = ("-date_joined",)

    fieldsets = UserAdmin.fieldsets + (
        ("WOOK'S CODING", {"fields": ("role", "point", "level", "selected_avatar", "is_subscribed")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("WOOK'S CODING", {"fields": ("role", "point", "level", "selected_avatar", "is_subscribed")}),
    )


@admin.register(AccountChangeLog)
class AccountChangeLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "change_type", "field_name", "created_at")
    list_filter = ("change_type", "created_at")
    search_fields = ("user__username", "field_name", "old_value", "new_value")
    raw_id_fields = ("user", "changed_by")
    readonly_fields = (
        "user",
        "changed_by",
        "change_type",
        "field_name",
        "old_value",
        "new_value",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
