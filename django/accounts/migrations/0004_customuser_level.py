from django.db import migrations, models


def backfill_user_levels(apps, schema_editor):
    User = apps.get_model("accounts", "CustomUser")
    for user in User.objects.only("id", "point", "level").iterator():
        level = max(1, int(user.point or 0) // 100 + 1)
        if user.level != level:
            user.level = level
            user.save(update_fields=["level"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_rename_accountchangelog_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="level",
            field=models.PositiveIntegerField(default=1, verbose_name="레벨"),
        ),
        migrations.RunPython(backfill_user_levels, migrations.RunPython.noop),
    ]