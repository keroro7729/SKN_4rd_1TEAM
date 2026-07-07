"""Account models."""
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


def calculate_user_level(point: int) -> int:
    return max(1, int(point or 0) // 100 + 1)

class CustomUser(AbstractUser):
    """Service user model."""

    class Role(models.TextChoices):
        STUDENT = "student", "학습자"
        ADMIN = "admin", "관리자"

    role = models.CharField("권한", max_length=20, choices=Role.choices, default=Role.STUDENT)
    point = models.PositiveIntegerField("포인트", default=0)
    level = models.PositiveIntegerField('레벨', default=1)
    is_subscribed = models.BooleanField("구독 여부", default=False)

    class Meta:
        verbose_name = "회원"
        verbose_name_plural = "회원"

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


    def sync_level(self) -> None:
        self.level = calculate_user_level(self.point)

    def save(self, *args, **kwargs):
        self.sync_level()
        super().save(*args, **kwargs)
    @property
    def is_service_admin(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_staff


class AccountChangeLog(models.Model):
    """Audit log for user-visible account changes."""

    class ChangeType(models.TextChoices):
        EMAIL = "email", "이메일"
        PASSWORD = "password", "비밀번호"
        SECURITY = "security", "보안"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="account_change_logs",
        verbose_name="회원",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="account_changes_made",
        verbose_name="변경자",
    )
    change_type = models.CharField("변경유형", max_length=20, choices=ChangeType.choices)
    field_name = models.CharField("항목", max_length=50)
    old_value = models.CharField("이전값", max_length=255, blank=True)
    new_value = models.CharField("변경값", max_length=255, blank=True)
    created_at = models.DateTimeField("변경일시", auto_now_add=True)

    class Meta:
        verbose_name = "계정 수정 이력"
        verbose_name_plural = "계정 수정 이력"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        return f"{self.user_id} · {self.get_change_type_display()} · {self.field_name}"