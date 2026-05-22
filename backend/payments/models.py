from django.conf import settings
from django.db import models


class EscrowPayment(models.Model):
    class Status(models.TextChoices):
        PENDING_DEPOSIT = "pending_deposit", "Pendiente de reserva"
        DEPOSIT_PAID = "deposit_paid", "Reserva pagada"
        SERVICE_COMPLETED = "service_completed", "Servicio completado"
        PENDING_REMAINING = "pending_remaining", "Saldo pendiente"
        REMAINING_PAID = "remaining_paid", "Saldo pagado"
        RELEASED = "released", "Liberado"
        REFUNDED = "refunded", "Reembolsado"
        DISPUTED = "disputed", "En disputa"
        CANCELLED = "cancelled", "Cancelado"

    class Provider(models.TextChoices):
        MOCK = "mock", "Demo / Mock"

    appointment = models.OneToOneField(
        "appointments.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment",
    )
    auction = models.ForeignKey(
        "auctions.Auction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    bid = models.ForeignKey(
        "auctions.Bid",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="escrow_payments",
    )
    technician = models.ForeignKey(
        "catalog.TechnicianProfile",
        on_delete=models.CASCADE,
        related_name="escrow_payments",
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2)
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="COP")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING_DEPOSIT)
    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.MOCK)
    provider_reference = models.CharField(max_length=120, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"EscrowPayment #{self.pk} [{self.status}] ${self.total_amount}"

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            self.Status.RELEASED,
            self.Status.REFUNDED,
            self.Status.CANCELLED,
        }


class PaymentTransaction(models.Model):
    class TransactionType(models.TextChoices):
        DEPOSIT = "deposit", "Depósito inicial (10%)"
        REMAINING = "remaining", "Saldo restante (90%)"
        REFUND = "refund", "Reembolso"
        RELEASE = "release", "Liberación al técnico"
        HOLD = "hold", "Retención por disputa"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        COMPLETED = "completed", "Completado"
        FAILED = "failed", "Fallido"

    payment = models.ForeignKey(EscrowPayment, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    provider_reference = models.CharField(max_length=120, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Tx {self.transaction_type} ${self.amount} [{self.status}]"
