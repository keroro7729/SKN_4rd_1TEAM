"""공지사항 모델 (지시문 §7, F-11): Notice."""
from django.conf import settings
from django.db import models


class Notice(models.Model):
    title = models.CharField("제목", max_length=200)
    content = models.TextField("내용")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notices",
        verbose_name="작성자",
    )
    is_published = models.BooleanField("게시", default=True)
    created_at = models.DateTimeField("작성일", auto_now_add=True)
    updated_at = models.DateTimeField("수정일", auto_now=True)

    class Meta:
        verbose_name = "공지사항"
        verbose_name_plural = "공지사항"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["is_published", "created_at"])]

    def __str__(self):
        return self.title
