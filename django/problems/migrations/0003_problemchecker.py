from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("problems", "0002_problemfavorite_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProblemChecker",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("language", models.CharField(default="python", max_length=30, verbose_name="실행언어")),
                ("runner_path", models.CharField(blank=True, max_length=255, verbose_name="채점기경로")),
                ("time_limit_ms", models.PositiveIntegerField(default=2000, verbose_name="시간제한(ms)")),
                ("memory_limit_mb", models.PositiveIntegerField(default=128, verbose_name="메모리제한(MB)")),
                ("is_active", models.BooleanField(default=True, verbose_name="활성")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="생성일시")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="수정일시")),
                ("problem", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="checker", to="problems.problem", verbose_name="문제")),
            ],
            options={
                "verbose_name": "문제 채점기",
                "verbose_name_plural": "문제 채점기",
            },
        ),
        migrations.AddIndex(
            model_name="problemchecker",
            index=models.Index(fields=["is_active", "language"], name="problems_pr_is_acti_9da0fb_idx"),
        ),
    ]