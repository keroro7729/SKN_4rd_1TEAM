from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("submissions", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="submission",
            name="submission_type",
            field=models.CharField(
                choices=[("run", "실행"), ("submit", "최종제출")],
                db_index=True,
                default="submit",
                max_length=20,
                verbose_name="제출유형",
            ),
        ),
        migrations.AddIndex(
            model_name="submission",
            index=models.Index(
                fields=["user", "submission_type", "created_at"],
                name="submissions_user_id_ee78f2_idx",
            ),
        ),
    ]
