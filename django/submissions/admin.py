"""제출/실행 관리자 화면."""
from django.contrib import admin

from .models import ExecutionJob, Submission


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "problem",
        "submission_type",
        "result",
        "elapsed_ms",
        "created_at",
    )
    list_filter = ("submission_type", "result", "created_at")
    search_fields = ("user__username", "problem__title")
    raw_id_fields = ("user", "problem")


@admin.register(ExecutionJob)
class ExecutionJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "submission",
        "job_type",
        "status",
        "retry_count",
        "worker_id",
        "created_at",
    )
    list_filter = ("status", "job_type", "created_at")
    raw_id_fields = ("user", "submission")
