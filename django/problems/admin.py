"""문제 도메인 관리자 화면."""
from django.contrib import admin

from .models import Problem, ProblemCategory, ProblemChecker, ProblemFavorite, ProblemTag, TestCase


class TestCaseInline(admin.TabularInline):
    model = TestCase
    extra = 1


@admin.register(ProblemCategory)
class ProblemCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ProblemTag)
class ProblemTagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "difficulty", "is_active", "created_at")
    list_filter = ("category", "difficulty", "is_active")
    search_fields = ("title", "description")
    filter_horizontal = ("tags",)
    inlines = [TestCaseInline]


@admin.register(TestCase)
class TestCaseAdmin(admin.ModelAdmin):
    list_display = ("__str__", "problem", "is_sample", "compare_mode")
    list_filter = ("is_sample", "compare_mode")


@admin.register(ProblemFavorite)
class ProblemFavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "problem", "created_at")
    list_filter = ("created_at",)

@admin.register(ProblemChecker)
class ProblemCheckerAdmin(admin.ModelAdmin):
    list_display = ("problem", "language", "time_limit_ms", "memory_limit_mb", "is_active", "updated_at")
    list_filter = ("language", "is_active")
    search_fields = ("problem__title", "runner_path")
