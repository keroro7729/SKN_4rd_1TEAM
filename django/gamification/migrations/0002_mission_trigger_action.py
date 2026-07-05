from django.db import migrations, models

import config.choices


def assign_trigger_actions(apps, schema_editor):
    Mission = apps.get_model("gamification", "Mission")
    for mission in Mission.objects.all():
        title = mission.title or ""
        if "오답" in title:
            trigger_action = "wrongnote_completed"
        elif "복습" in title:
            trigger_action = "review_completed"
        else:
            trigger_action = "submission_created"
        Mission.objects.filter(pk=mission.pk).update(trigger_action=trigger_action)


class Migration(migrations.Migration):
    dependencies = [
        ("gamification", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="mission",
            name="trigger_action",
            field=models.CharField(
                choices=config.choices.POINT_ACTION_TYPE_CHOICES,
                default="submission_created",
                max_length=30,
                verbose_name="진행조건",
            ),
        ),
        migrations.AddIndex(
            model_name="mission",
            index=models.Index(
                fields=["is_active", "trigger_action"],
                name="gamificatio_is_acti_3d7a40_idx",
            ),
        ),
        migrations.RunPython(assign_trigger_actions, migrations.RunPython.noop),
    ]
