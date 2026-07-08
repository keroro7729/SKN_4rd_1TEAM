"""회원 모델 (F-01, F-02).

기존 CustomUser 구조(role, point, is_subscribed, is_service_admin)를 유지하면서
동물 프로필과 회원 계정 수정 이력(AccountChangeLog)을 추가한다.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    # PROFILE_DESIGN_RESTORE_V55_MODEL: selected_avatar + level + AccountChangeLog 호환
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

    LEVEL_CATALOG = [
        {"level": 1, "name": "새싹", "required_point": 0},
        {"level": 2, "name": "입문자", "required_point": 50},
        {"level": 3, "name": "연습생", "required_point": 100},
        {"level": 4, "name": "탐험가", "required_point": 200},
        {"level": 5, "name": "분석가", "required_point": 350},
        {"level": 6, "name": "해결사", "required_point": 500},
        {"level": 7, "name": "마스터", "required_point": 800},
    ]

    AVATAR_CATALOG = [
        {"key": Avatar.CAT, "name": "고양이", "icon": "🐱", "required_point": 0, "tag": "Lv.1 · 기본 지급"},
        {"key": Avatar.DOG, "name": "강아지", "icon": "🐶", "required_point": 50, "tag": "Lv.2 · 50P"},
        {"key": Avatar.RABBIT, "name": "토끼", "icon": "🐰", "required_point": 100, "tag": "Lv.3 · 100P"},
        {"key": Avatar.FOX, "name": "여우", "icon": "🦊", "required_point": 200, "tag": "Lv.4 · 200P"},
        {"key": Avatar.PANDA, "name": "판다", "icon": "🐼", "required_point": 350, "tag": "Lv.5 · 350P"},
        {"key": Avatar.TIGER, "name": "호랑이", "icon": "🐯", "required_point": 500, "tag": "Lv.6 · 500P"},
        {"key": Avatar.DRAGON, "name": "드래곤", "icon": "🐲", "required_point": 800, "tag": "Lv.7 · 800P"},
    ]

    role = models.CharField(
        "권한",
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )
    point = models.PositiveIntegerField("포인트", default=0)
    level = models.PositiveSmallIntegerField("레벨", default=1)
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
        locked = [item for item in self.avatar_items if not item["unlocked"]]
        return locked[0] if locked else None

    @classmethod
    def level_catalog(cls):
        """포인트 구간별 플레이어 레벨 표."""
        return [dict(item) for item in cls.LEVEL_CATALOG]

    @property
    def level_meta(self):
        current_point = self.point or 0
        current = self.level_catalog()[0]
        for item in self.level_catalog():
            if current_point >= int(item["required_point"]):
                current = item
            else:
                break
        return current

    @property
    def level_number(self) -> int:
        return int(self.level_meta["level"])

    @property
    def level_name(self) -> str:
        return self.level_meta["name"]

    @property
    def next_level_meta(self):
        current_point = self.point or 0
        for item in self.level_catalog():
            if current_point < int(item["required_point"]):
                result = dict(item)
                result["remaining"] = int(item["required_point"]) - current_point
                return result
        return None


class AccountChangeLog(models.Model):
    """사용자 계정정보 변경 이력."""

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


def calculate_user_level(point_or_user=0) -> int:
    """포인트 기준 사용자 레벨 계산 함수.

    gamification.services에서 import해서 사용하는 기존 호환 함수다.
    accounts.models에서 이 함수가 빠지면 Django 시작 단계에서 ImportError가 발생한다.
    """
    if hasattr(point_or_user, "point"):
        point = getattr(point_or_user, "point", 0) or 0
    else:
        point = point_or_user or 0

    try:
        point = int(point)
    except (TypeError, ValueError):
        point = 0

    current_level = 1
    catalog = getattr(
        CustomUser,
        "LEVEL_CATALOG",
        [
            {"level": 1, "required_point": 0},
            {"level": 2, "required_point": 50},
            {"level": 3, "required_point": 100},
            {"level": 4, "required_point": 200},
            {"level": 5, "required_point": 350},
            {"level": 6, "required_point": 500},
            {"level": 7, "required_point": 800},
        ],
    )

    for item in catalog:
        if point >= int(item["required_point"]):
            current_level = int(item["level"])
        else:
            break

    return current_level

