"""Point and mission reward services."""
from __future__ import annotations

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from config.choices import POINT_REWARD_MAP

from .models import Mission, PointLog, UserMission


def _related_identity(related_obj=None, *, related_model: str = "", related_id=None):
    if related_obj is not None:
        return related_obj._meta.model_name, related_obj.pk
    return related_model, related_id


def award_points(user, action_type: str, related_obj=None, *, related_model: str = "", related_id=None):
    """Award fixed points once for a user/action/related object."""
    point = POINT_REWARD_MAP.get(action_type)
    if point is None:
        raise ValueError(f"unsupported point action: {action_type}")

    model_name, object_id = _related_identity(
        related_obj,
        related_model=related_model,
        related_id=related_id,
    )
    if not model_name or object_id is None:
        raise ValueError("related object identity is required")

    try:
        with transaction.atomic():
            log, created = PointLog.objects.get_or_create(
                user=user,
                action_type=action_type,
                related_model=model_name,
                related_id=object_id,
                defaults={"point": point},
            )
            if created:
                type(user).objects.filter(pk=user.pk).update(point=F("point") + point)
                user.refresh_from_db(fields=["point"])
            return log, created
    except IntegrityError:
        return (
            PointLog.objects.get(
                user=user,
                action_type=action_type,
                related_model=model_name,
                related_id=object_id,
            ),
            False,
        )


def advance_missions(user, action_type: str):
    """Advance active missions whose trigger action matches the event."""
    completed = []
    missions = Mission.objects.filter(is_active=True, trigger_action=action_type)
    for mission in missions:
        user_mission, _ = UserMission.objects.get_or_create(
            user=user,
            mission=mission,
            defaults={"status": "not_started"},
        )
        if user_mission.is_completed:
            continue

        user_mission.progress_count = min(
            user_mission.progress_count + 1,
            mission.target_count,
        )
        if user_mission.progress_count >= mission.target_count:
            user_mission.status = "completed"
            user_mission.is_completed = True
            user_mission.completed_at = timezone.now()
        else:
            user_mission.status = "in_progress"
        user_mission.save(
            update_fields=[
                "progress_count",
                "status",
                "is_completed",
                "completed_at",
            ]
        )

        if user_mission.is_completed:
            award_points(user, "daily_mission_completed", user_mission)
            completed.append(user_mission)
    return completed


def record_user_action(user, action_type: str, related_obj):
    """Award action points and update missions for a completed user action."""
    point_log, created = award_points(user, action_type, related_obj)
    completed_missions = []
    if created:
        completed_missions = advance_missions(user, action_type)
    return {
        "point_log": point_log,
        "point_created": created,
        "completed_missions": completed_missions,
    }
