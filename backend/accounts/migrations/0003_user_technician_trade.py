from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_address_and_telegram_chat_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="technician_trade",
            field=models.CharField(
                blank=True,
                choices=[
                    ("electrician", "Electrician"),
                    ("plumber", "Plumber"),
                    ("locksmith", "Locksmith"),
                    ("general-handyman", "General Handyman"),
                ],
                max_length=40,
            ),
        ),
    ]
