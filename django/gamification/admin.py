"""게이미피케이션 관리자 화면."""
from django.contrib import admin

from .models import Mission, PointLog, UserMission


@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    list_display = ("title", "target_count", "reward_point", "is_active")
    list_filter = ("is_active",)


@admin.register(UserMission)
class UserMissionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "mission", "status", "progress_count", "is_completed")
    list_filter = ("status", "is_completed")
    raw_id_fields = ("user", "mission")


@admin.register(PointLog)
class PointLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "action_type", "point", "related_model", "created_at")
    list_filter = ("action_type", "created_at")
    raw_id_fields = ("user",)
