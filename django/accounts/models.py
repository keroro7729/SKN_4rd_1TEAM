"""회원 모델 (F-01, F-02).

문서 규칙: Django 기본 User 대신 accounts.CustomUser 사용.
CustomUser는 role, point, is_subscribed, selected_avatar 필드를 포함한다.
"""
from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    # PROFILE_AVATAR_LEVEL_V49_MODEL: 동물 프로필 + 레벨별 힌트 파트너/테두리
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

    HINT_PARTNER_CATALOG = [
        {
            "level": 1,
            "name": "새싹 코치",
            "icon": "🐣",
            "title": "기초 조건 확인형",
            "message": "입력·출력·예제를 먼저 확인하도록 도와줍니다.",
        },
        {
            "level": 2,
            "name": "강아지 코치",
            "icon": "🐶",
            "title": "흐름 추적형",
            "message": "예제 흐름을 따라가며 실수 지점을 찾도록 도와줍니다.",
        },
        {
            "level": 3,
            "name": "토끼 코치",
            "icon": "🐰",
            "title": "경계값 점검형",
            "message": "인덱스, 기저 조건, 출력 형식을 꼼꼼히 점검합니다.",
        },
        {
            "level": 4,
            "name": "여우 코치",
            "icon": "🦊",
            "title": "전략 설계형",
            "message": "풀이 전략과 알고리즘 선택을 함께 좁혀줍니다.",
        },
        {
            "level": 5,
            "name": "판다 코치",
            "icon": "🐼",
            "title": "복잡도 분석형",
            "message": "시간·메모리 조건을 기준으로 풀이를 점검합니다.",
        },
        {
            "level": 6,
            "name": "호랑이 코치",
            "icon": "🐯",
            "title": "실전 디버깅형",
            "message": "실행 결과와 반례 중심으로 원인을 빠르게 좁힙니다.",
        },
        {
            "level": 7,
            "name": "드래곤 코치",
            "icon": "🐲",
            "title": "마스터 리뷰형",
            "message": "정답 접근, 최적화, 오답 회고까지 종합적으로 안내합니다.",
        },
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


    @classmethod
    def hint_partner_catalog(cls):
        """레벨별 AI 힌트 파트너 카탈로그."""
        return [dict(item) for item in cls.HINT_PARTNER_CATALOG]

    @property
    def level_tier_class(self) -> str:
        return f"level-frame-{self.level_number}"

    @property
    def hint_partner_meta(self):
        current = self.hint_partner_catalog()[0]
        for item in self.hint_partner_catalog():
            if self.level_number >= int(item["level"]):
                current = item
            else:
                break
        return current

    @property
    def hint_partner_icon(self) -> str:
        return self.hint_partner_meta["icon"]

    @property
    def hint_partner_name(self) -> str:
        return self.hint_partner_meta["name"]

    @property
    def hint_partner_title(self) -> str:
        return self.hint_partner_meta["title"]

    @property
    def hint_partner_message(self) -> str:
        return self.hint_partner_meta["message"]

    @property
    def next_level_meta(self):
        current_point = self.point or 0
        for item in self.level_catalog():
            if current_point < int(item["required_point"]):
                result = dict(item)
                result["remaining"] = int(item["required_point"]) - current_point
                return result
        return None
