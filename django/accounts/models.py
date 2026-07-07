"""회원 모델 (F-01, F-02).

문서 규칙: Django 기본 User 대신 accounts.CustomUser 사용.
CustomUser는 role, point, is_subscribed, selected_avatar 필드를 포함한다.
"""
from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    # PROFILE_AVATAR_POPUP_V45_MODEL: 동물 프로필 필드/해금 카탈로그
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
    def avatar_catalog(cls):
        """템플릿/뷰에서 공통으로 쓰는 동물 프로필 카탈로그."""
        return [dict(item) for item in cls.AVATAR_CATALOG]

    @property
    def avatar_items(self):
        """현재 사용자의 포인트 기준으로 해금/잠금 상태를 계산한다."""
        items = []
        current_point = self.point or 0
        selected_key = self.selected_avatar or self.Avatar.CAT
        for raw in self.avatar_catalog():
            required = int(raw["required_point"])
            unlocked = current_point >= required
            item = {
                **raw,
                "unlocked": unlocked,
                "selected": str(raw["key"]) == str(selected_key),
                "remaining": max(required - current_point, 0),
            }
            items.append(item)
        return items

    @property
    def avatar_meta(self):
        selected_key = self.selected_avatar or self.Avatar.CAT
        for item in self.avatar_catalog():
            if str(item["key"]) == str(selected_key):
                return item
        return self.avatar_catalog()[0]

    @property
    def avatar_icon(self) -> str:
        return self.avatar_meta["icon"]

    @property
    def avatar_name(self) -> str:
        return self.avatar_meta["name"]

    @property
    def next_locked_avatar(self):
        current_point = self.point or 0
        locked = [item for item in self.avatar_items if not item["unlocked"]]
        if not locked:
            return None
        return locked[0]
