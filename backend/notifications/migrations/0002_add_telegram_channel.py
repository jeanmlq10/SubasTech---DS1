from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="channel",
            field=models.CharField(
                choices=[
                    ("dashboard", "Dashboard"),
                    ("telegram", "Telegram"),
                    ("whatsapp", "WhatsApp"),
                    ("email", "Email"),
                ],
                default="dashboard",
                max_length=20,
            ),
        ),
    ]
