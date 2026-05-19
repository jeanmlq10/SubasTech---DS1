from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("leads", "0002_servicelead_client_user"),
    ]

    operations = [
        migrations.AlterField(
            model_name="servicelead",
            name="source",
            field=models.CharField(
                choices=[
                    ("whatsapp", "WhatsApp"),
                    ("telegram", "Telegram"),
                    ("dashboard", "Dashboard"),
                ],
                default="whatsapp",
                max_length=20,
            ),
        ),
    ]
