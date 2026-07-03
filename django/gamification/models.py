"""게이미피케이션 모델 (지시문 §7/§8): Mission · UserMission · PointLog.

포인트 지급 수치는 config.choices.POINT_REWARD_MAP 로 고정(§8). 실제 지급 로직은 STEP-08.
PointLog 의 (user, action_type, related_model, related_id) unique 로 중복 지급을 차단한다.
"""
from django.conf import settings
from django.db import models

from config.choices import MISSION_STATUS_CHOICES, POINT_ACTION_TYPE_CHOICES


class Mission(models.Model):
    title = models.CharField("미션명", max_length=200)
    target_count = models.PositiveIntegerField("목표횟수", default=1)
    reward_point = models.PositiveIntegerField("보상포인트", default=0)
    is_active = models.BooleanField("활성", default=True)

    class Meta:
        verbose_name = "미션"
        verbose_name_plural = "미션"
        indexes = [models.Index(fields=["is_active"])]

    def __str__(self):
        return self.title


class UserMission(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_missions",
        verbose_name="회원",
    )
    mission = models.ForeignKey(
        Mission,
        on_delete=models.CASCADE,
        related_name="user_missions",
        verbose_name="미션",
    )
    status = models.CharField(
        "상태", max_length=20, choices=MISSION_STATUS_CHOICES, default="not_started"
    )
    progress_count = models.PositiveIntegerField("진행횟수", default=0)
    is_completed = models.BooleanField("완료", default=False)
    completed_at = models.DateTimeField("완료일", null=True, blank=True)

    class Meta:
        verbose_name = "회원 미션"
        verbose_name_plural = "회원 미션"
        constraints = [
            models.UniqueConstraint(fields=["user", "mission"], name="uniq_user_mission")
        ]

    def __str__(self):
        return f"u{self.user_id}-m{self.mission_id} · {self.status}"


class PointLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="point_logs",
        verbose_name="회원",
    )
    action_type = models.CharField(
        "행동유형", max_length=30, choices=POINT_ACTION_TYPE_CHOICES
    )
    point = models.IntegerField("포인트")  # admin_adjustment 는 음수 가능
    related_model = models.CharField("관련모델", max_length=50, blank=True)
    related_id = models.PositiveIntegerField("관련ID", null=True, blank=True)
    created_at = models.DateTimeField("지급일", auto_now_add=True)

    class Meta:
        verbose_name = "포인트 로그"
        verbose_name_plural = "포인트 로그"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "action_type", "related_model", "related_id"],
                name="uniq_point_award",
            )
        ]
        indexes = [models.Index(fields=["user", "action_type"])]

    def __str__(self):
        return f"u{self.user_id} · {self.action_type} · {self.point:+d}"
