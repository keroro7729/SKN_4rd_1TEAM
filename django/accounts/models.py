"""회원 모델 (F-01, F-02).

문서 규칙: Django 기본 User 대신 accounts.CustomUser 사용.
CustomUser는 role, point, is_subscribed, selected_avatar 필드를 포함한다.
"""
from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "학습자"
        ADMIN = "admin", "관리자"

    class Avatar(models.TextChoices):
        CAT = "cat", "고양이"
        DOG = "dog", "강아지"
        RABBIT = "rabbit", "토끼"
        FOX = "fox", "여우"
        PANDA = "panda", "판다"
        TIGER = "tiger", "호랑이"
        DRAGON = "dragon", "드래곤"

    AVATAR_CATALOG = [
        {"key": Avatar.CAT, "name": "고양이", "icon": "🐱", "required_point": 0, "tag": "기본 지급"},
        {"key": Avatar.DOG, "name": "강아지", "icon": "🐶", "required_point": 50, "tag": "50P 달성"},
        {"key": Avatar.RABBIT, "name": "토끼", "icon": "🐰", "required_point": 100, "tag": "100P 달성"},
        {"key": Avatar.FOX, "name": "여우", "icon": "🦊", "required_point": 200, "tag": "200P 달성"},
        {"key": Avatar.PANDA, "name": "판다", "icon": "🐼", "required_point": 350, "tag": "350P 달성"},
        {"key": Avatar.TIGER, "name": "호랑이", "icon": "🐯", "required_point": 500, "tag": "500P 달성"},
        {"key": Avatar.DRAGON, "name": "드래곤", "icon": "🐲", "required_point": 800, "tag": "800P 달성"},
    ]

    role = models.CharField(
        "권한",
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )
    point = models.PositiveIntegerField("포인트", default=0)
    selected_avatar = models.CharField(
        "프로필 동물",
        max_length=20,
        choices=Avatar.choices,
        default=Avatar.CAT,
    )
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

    @classmethod
    def get_avatar_catalog(cls) -> list[dict]:
        """포인트로 해금되는 동물 프로필 목록."""
        return list(cls.AVATAR_CATALOG)

    @classmethod
    def get_avatar_config(cls, key: str) -> dict | None:
        for item in cls.AVATAR_CATALOG:
            if item["key"] == key:
                return item
        return None

    def can_use_avatar(self, key: str) -> bool:
        item = self.get_avatar_config(key)
        if not item:
            return False
        return self.point >= int(item["required_point"])

    @property
    def avatar_icon(self) -> str:
        item = self.get_avatar_config(self.selected_avatar)
        return item["icon"] if item else "🐱"

    @property
    def avatar_name(self) -> str:
        item = self.get_avatar_config(self.selected_avatar)
        return item["name"] if item else "고양이"

    @property
    def avatar_items(self) -> list[dict]:
        """템플릿에서 바로 사용할 수 있는 프로필 카드 데이터."""
        items = []
        for item in self.AVATAR_CATALOG:
            unlocked = self.point >= int(item["required_point"])
            remaining = max(int(item["required_point"]) - int(self.point), 0)
            items.append(
                {
                    **item,
                    "unlocked": unlocked,
                    "selected": self.selected_avatar == item["key"],
                    "remaining": remaining,
                }
            )
        return items

    @property
    def next_locked_avatar(self) -> dict | None:
        for item in self.avatar_items:
            if not item["unlocked"]:
                return item
        return None
