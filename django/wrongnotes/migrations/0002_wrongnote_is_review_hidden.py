# Generated for review board hide feature

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wrongnotes", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="wrongnote",
            name="is_review_hidden",
            field=models.BooleanField(default=False, verbose_name="복습보드숨김"),
        ),
    ]
