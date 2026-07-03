"""회원 모델 (F-01, F-02).

문서 규칙: Django 기본 User 대신 accounts.CustomUser 사용.
CustomUser는 role, point, is_subscribed 필드를 포함한다.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "학습자"
        ADMIN = "admin", "관리자"

    role = models.CharField(
        "권한",
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )
    point = models.PositiveIntegerField("포인트", default=0)
    # 결제/구독은 MVP 제외. 확장 대비 필드로만 유지한다.
    is_subscribed = models.BooleanField("구독 여부", default=False)

    class Meta:
        verbose_name = "회원"
        verbose_name_plural = "회원"

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_service_admin(self) -> bool:
        """서비스 관리자 여부 (role=admin 또는 Django staff)."""
        return self.role == self.Role.ADMIN or self.is_staff
