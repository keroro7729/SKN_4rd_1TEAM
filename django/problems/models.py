"""문제 도메인 모델 (지시문 §7): ProblemCategory · ProblemTag · Problem · TestCase.

설계 상세: llm_wiki/6. WOOKS_CODING_데이터모델_문제_제출_Job_오답노트_v0.1.md §1
"""
from django.conf import settings
from django.db import models

from config.choices import DIFFICULTY_CHOICES, TEST_COMPARE_MODE_CHOICES


class ProblemCategory(models.Model):
    name = models.CharField("이름", max_length=50)
    slug = models.SlugField("슬러그", unique=True)
    order = models.PositiveIntegerField("정렬순서", default=0)
    is_active = models.BooleanField("활성", default=True)

    class Meta:
        verbose_name = "문제 카테고리"
        verbose_name_plural = "문제 카테고리"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class ProblemTag(models.Model):
    name = models.CharField("이름", max_length=50)
    slug = models.SlugField("슬러그", unique=True)

    class Meta:
        verbose_name = "문제 태그"
        verbose_name_plural = "문제 태그"

    def __str__(self):
        return self.name


class Problem(models.Model):
    category = models.ForeignKey(
        ProblemCategory,
        on_delete=models.PROTECT,
        related_name="problems",
        verbose_name="카테고리",
    )
    tags = models.ManyToManyField(
        ProblemTag, blank=True, related_name="problems", verbose_name="태그"
    )
    title = models.CharField("제목", max_length=200)
    description = models.TextField("설명")
    difficulty = models.CharField(
        "난이도", max_length=20, choices=DIFFICULTY_CHOICES, default="beginner"
    )
    constraints = models.TextField("제약조건", blank=True)
    is_active = models.BooleanField("활성", default=True)
    created_at = models.DateTimeField("생성일", auto_now_add=True)

    class Meta:
        verbose_name = "문제"
        verbose_name_plural = "문제"
        indexes = [models.Index(fields=["category", "difficulty"])]

    def __str__(self):
        return f"[{self.get_difficulty_display()}] {self.title}"


class ProblemFavorite(models.Model):
    """사용자별 즐겨찾기(북마크). 목록 화면의 ☆ 토글과 '즐겨찾기' 상태 필터가 이 모델을 사용한다."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorite_problems",
        verbose_name="사용자",
    )
    problem = models.ForeignKey(
        Problem,
        on_delete=models.CASCADE,
        related_name="favorited_by",
        verbose_name="문제",
    )
    created_at = models.DateTimeField("등록일", auto_now_add=True)

    class Meta:
        verbose_name = "즐겨찾기"
        verbose_name_plural = "즐겨찾기"
        constraints = [
            models.UniqueConstraint(fields=["user", "problem"], name="unique_user_problem_favorite")
        ]
        indexes = [models.Index(fields=["user", "problem"])]

    def __str__(self):
        return f"{self.user_id} ★ {self.problem_id}"


class TestCase(models.Model):
    problem = models.ForeignKey(
        Problem,
        on_delete=models.CASCADE,
        related_name="test_cases",
        verbose_name="문제",
    )
    input_data = models.TextField("입력", blank=True)
    expected_output = models.TextField("기대출력", blank=True)
    is_sample = models.BooleanField("샘플공개", default=False)
    compare_mode = models.CharField(
        "채점방식", max_length=20, choices=TEST_COMPARE_MODE_CHOICES, default="line_trim"
    )
    float_tolerance = models.FloatField("부동소수허용오차", default=1e-6)

    class Meta:
        verbose_name = "테스트케이스"
        verbose_name_plural = "테스트케이스"
        indexes = [models.Index(fields=["problem"])]

    def __str__(self):
        sample = "샘플" if self.is_sample else "채점"
        return f"TC#{self.pk}({sample}) · problem {self.problem_id}"