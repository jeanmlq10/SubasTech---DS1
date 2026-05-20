import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("webhook_received", "Webhook received"),
                            ("message_sent", "Message sent"),
                            ("lead_created", "Lead created"),
                            ("lead_status_changed", "Lead status changed"),
                            ("dispute_created", "Dispute created"),
                            ("dispute_claimed", "Dispute claimed"),
                            ("dispute_resolved", "Dispute resolved"),
                            ("admin_action", "Admin action"),
                            ("integration_error", "Integration error"),
                        ],
                        max_length=40,
                    ),
                ),
                ("channel", models.CharField(blank=True, max_length=40)),
                ("source", models.CharField(blank=True, max_length=80)),
                ("entity_type", models.CharField(blank=True, max_length=80)),
                ("entity_id", models.CharField(blank=True, max_length=80)),
                ("status", models.CharField(default="info", max_length=20)),
                ("message", models.CharField(max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
