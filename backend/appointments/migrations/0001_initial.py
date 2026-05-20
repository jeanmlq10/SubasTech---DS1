import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("catalog", "0001_initial"),
        ("leads", "0002_servicelead_client_user"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Appointment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scheduled_start", models.DateTimeField()),
                ("scheduled_end", models.DateTimeField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("confirmed", "Confirmed"),
                            ("cancelled", "Cancelled"),
                            ("rescheduled", "Rescheduled"),
                            ("completed", "Completed"),
                            ("no_show", "No show"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("cancellation_reason", models.TextField(blank=True)),
                (
                    "cancellation_timing",
                    models.CharField(
                        blank=True,
                        choices=[("early", "Early"), ("late", "Late")],
                        max_length=10,
                    ),
                ),
                ("reschedule_reason", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="appointments_as_client",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "technician",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="appointments",
                        to="catalog.technicianprofile",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="appointments",
                        to="catalog.service",
                    ),
                ),
                (
                    "lead",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="appointment",
                        to="leads.servicelead",
                    ),
                ),
            ],
            options={
                "verbose_name": "appointment",
                "verbose_name_plural": "appointments",
                "ordering": ["-scheduled_start"],
            },
        ),
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(fields=["technician"], name="appointment_techni_idx"),
        ),
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(fields=["scheduled_start"], name="appointment_start_idx"),
        ),
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(fields=["status"], name="appointment_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="appointment",
            constraint=models.CheckConstraint(
                condition=models.Q(scheduled_end__gt=models.F("scheduled_start")),
                name="appointment_end_after_start",
            ),
        ),
    ]
