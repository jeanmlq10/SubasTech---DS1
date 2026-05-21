from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_alter_user_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="dispute_strikes",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="user",
            name="auction_blocked",
            field=models.BooleanField(default=False),
        ),
    ]
