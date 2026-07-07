import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('problems', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProblemFavorite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='등록일')),
                ('problem', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorited_by', to='problems.problem', verbose_name='문제')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorite_problems', to=settings.AUTH_USER_MODEL, verbose_name='사용자')),
            ],
            options={
                'verbose_name': '즐겨찾기',
                'verbose_name_plural': '즐겨찾기',
                'indexes': [models.Index(fields=['user', 'problem'], name='problems_pr_user_id_8c7ecb_idx')],
            },
        ),
        migrations.AddConstraint(
            model_name='problemfavorite',
            constraint=models.UniqueConstraint(fields=('user', 'problem'), name='unique_user_problem_favorite'),
        ),
    ]