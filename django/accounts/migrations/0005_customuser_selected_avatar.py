# Generated for restoring level-based animal profile after main merge.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_customuser_level"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="selected_avatar",
            field=models.CharField(
                choices=[
                    ("cat", "고양이"),
                    ("dog", "강아지"),
                    ("rabbit", "토끼"),
                    ("fox", "여우"),
                    ("panda", "판다"),
                    ("tiger", "호랑이"),
                    ("dragon", "드래곤"),
                ],
                default="cat",
                max_length=20,
                verbose_name="프로필 동물",
            ),
        ),
    ]
