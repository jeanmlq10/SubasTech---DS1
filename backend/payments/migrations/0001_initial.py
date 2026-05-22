import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("appointments", "0001_initial"),
        ("auctions", "0001_initial"),
        ("catalog", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EscrowPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "appointment",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="payment",
                        to="appointments.appointment",
                    ),
                ),
                (
                    "auction",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="payments",
                        to="auctions.auction",
                    ),
                ),
                (
                    "bid",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="payments",
                        to="auctions.bid",
                    ),
                ),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="escrow_payments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "technician",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="escrow_payments",
                        to="catalog.technicianprofile",
                    ),
                ),
                ("total_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("deposit_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("remaining_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(default="COP", max_length=3)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending_deposit", "Pendiente de reserva"),
                            ("deposit_paid", "Reserva pagada"),
                            ("service_completed", "Servicio completado"),
                            ("pending_remaining", "Saldo pendiente"),
                            ("remaining_paid", "Saldo pagado"),
                            ("released", "Liberado"),
                            ("refunded", "Reembolsado"),
                            ("disputed", "En disputa"),
                            ("cancelled", "Cancelado"),
                        ],
                        default="pending_deposit",
                        max_length=24,
                    ),
                ),
                (
                    "provider",
                    models.CharField(
                        choices=[("mock", "Demo / Mock")],
                        default="mock",
                        max_length=20,
                    ),
                ),
                ("provider_reference", models.CharField(blank=True, max_length=120)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="PaymentTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "payment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="transactions",
                        to="payments.escrowpayment",
                    ),
                ),
                (
                    "transaction_type",
                    models.CharField(
                        choices=[
                            ("deposit", "Depósito inicial (10%)"),
                            ("remaining", "Saldo restante (90%)"),
                            ("refund", "Reembolso"),
                            ("release", "Liberación al técnico"),
                            ("hold", "Retención por disputa"),
                        ],
                        max_length=20,
                    ),
                ),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pendiente"),
                            ("completed", "Completado"),
                            ("failed", "Fallido"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("provider_reference", models.CharField(blank=True, max_length=120)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["created_at"]},
        ),
    ]
