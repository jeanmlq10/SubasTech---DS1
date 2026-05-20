# Generated manually on 2026-05-19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("telegram_bot", "0003_add_chat_session_and_messages"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatsession",
            name="last_telegram_message_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
