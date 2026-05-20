import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def migrate_existing_ratings(apps, schema_editor):
    Rating = apps.get_model("reputation", "Rating")
    for rating in Rating.objects.all().iterator():
        rating.author_id = rating.client_id
        rating.target_role = "technician"
        rating.save(update_fields=["author", "target_role"])


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
        ("leads", "0002_servicelead_client_user"),
        ("reputation", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="rating",
            name="author",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="ratings_given",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="rating",
            name="lead",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ratings",
                to="leads.servicelead",
            ),
        ),
        migrations.AddField(
            model_name="rating",
            name="target_role",
            field=models.CharField(
                choices=[("technician", "Technician"), ("client", "Client")],
                default="technician",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="rating",
            name="updated_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="penalty",
            name="code",
            field=models.CharField(
                choices=[
                    ("manual", "Manual"),
                    ("no_show", "No show"),
                    ("late_cancellation", "Late cancellation"),
                    ("low_reputation", "Low reputation"),
                    ("lost_dispute", "Lost dispute"),
                ],
                default="manual",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="penalty",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="penalty",
            name="updated_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="rating",
            name="client",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="ratings_received",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="rating",
            name="technician",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="ratings",
                to="catalog.technicianprofile",
            ),
        ),
        migrations.RunPython(migrate_existing_ratings, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="rating",
            name="author",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="ratings_given",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="rating",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("target_role", "technician"), ("technician__isnull", False), ("client__isnull", True))
                    | models.Q(("target_role", "client"), ("technician__isnull", True), ("client__isnull", False))
                ),
                name="rating_target_matches_role",
            ),
        ),
        migrations.AddConstraint(
            model_name="rating",
            constraint=models.UniqueConstraint(
                condition=models.Q(("lead__isnull", True), ("target_role", "technician")),
                fields=("author", "technician", "service", "target_role"),
                name="unique_technician_rating_per_service",
            ),
        ),
        migrations.AddConstraint(
            model_name="rating",
            constraint=models.UniqueConstraint(
                condition=models.Q(("lead__isnull", False), ("target_role", "technician")),
                fields=("author", "technician", "lead", "target_role"),
                name="unique_technician_rating_per_lead",
            ),
        ),
        migrations.AddConstraint(
            model_name="rating",
            constraint=models.UniqueConstraint(
                condition=models.Q(("target_role", "client")),
                fields=("author", "client", "lead", "target_role"),
                name="unique_client_rating_per_lead",
            ),
        ),
    ]
