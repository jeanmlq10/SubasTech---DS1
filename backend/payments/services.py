"""Escrow payment service layer.

All write operations run inside transaction.atomic() where atomicity matters.
The mock provider simulates the full payment lifecycle without any real gateway.
Design: replace EscrowPayment.Provider.MOCK with a real provider and swap out
the _mock_* helpers — all business logic stays identical.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from audit.services import log_audit_event

from .models import EscrowPayment, PaymentTransaction

DEPOSIT_RATIO = Decimal("0.10")

# Audit event type constants (additive — audit.EventType is a hint, not a DB constraint)
AUDIT_PAYMENT_CREATED = "payment_created"
AUDIT_PAYMENT_DEPOSIT_PAID = "payment_deposit_paid"
AUDIT_PAYMENT_SERVICE_COMPLETED = "payment_service_completed"
AUDIT_PAYMENT_REMAINING_PAID = "payment_remaining_paid"
AUDIT_PAYMENT_RELEASED = "payment_released"
AUDIT_PAYMENT_REFUNDED = "payment_refunded"
AUDIT_PAYMENT_DISPUTED = "payment_disputed"
AUDIT_PAYMENT_CANCELLED = "payment_cancelled"


def create_escrow_for_awarded_bid(*, auction, bid, appointment=None) -> EscrowPayment:
    """Create escrow for an awarded bid. Idempotent: returns existing if already created."""
    if appointment is not None:
        existing = EscrowPayment.objects.filter(appointment=appointment).first()
        if existing:
            return existing
    existing = EscrowPayment.objects.filter(auction=auction, bid=bid).first()
    if existing:
        if appointment is not None and existing.appointment_id is None:
            existing.appointment = appointment
            existing.save(update_fields=["appointment", "updated_at"])
        return existing

    total = Decimal(str(bid.amount))
    deposit = (total * DEPOSIT_RATIO).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    remaining = total - deposit

    payment = EscrowPayment.objects.create(
        appointment=appointment,
        auction=auction,
        bid=bid,
        client=auction.client,
        technician=bid.technician,
        total_amount=total,
        deposit_amount=deposit,
        remaining_amount=remaining,
        currency="COP",
        status=EscrowPayment.Status.PENDING_DEPOSIT,
        provider=EscrowPayment.Provider.MOCK,
        metadata={"source": "auction_award", "auction_id": auction.id, "bid_id": bid.id},
    )
    log_audit_event(
        event_type=AUDIT_PAYMENT_CREATED,
        actor=auction.client,
        source="payments.create_escrow",
        entity_type="payment",
        entity_id=payment.id,
        status="success",
        message="Escrow de pago creado al adjudicar subasta",
        metadata={"total": str(total), "deposit": str(deposit), "remaining": str(remaining)},
    )
    return payment


def mark_deposit_paid(payment: EscrowPayment, actor) -> EscrowPayment:
    """Simulate payment of the 10% deposit (mock provider)."""
    if payment.status != EscrowPayment.Status.PENDING_DEPOSIT:
        raise ValidationError({"status": "La reserva solo se puede pagar cuando está pendiente de pago inicial."})

    with transaction.atomic():
        payment.status = EscrowPayment.Status.DEPOSIT_PAID
        payment.provider_reference = f"MOCK-DEP-{payment.id}"
        payment.save(update_fields=["status", "provider_reference", "updated_at"])
        PaymentTransaction.objects.create(
            payment=payment,
            transaction_type=PaymentTransaction.TransactionType.DEPOSIT,
            amount=payment.deposit_amount,
            status=PaymentTransaction.Status.COMPLETED,
            provider_reference=payment.provider_reference,
        )

    log_audit_event(
        event_type=AUDIT_PAYMENT_DEPOSIT_PAID,
        actor=actor,
        source="payments.deposit",
        entity_type="payment",
        entity_id=payment.id,
        status="success",
        message="Reserva del 10% pagada (mock)",
        metadata={"deposit_amount": str(payment.deposit_amount)},
    )
    return payment


def mark_service_completed(payment: EscrowPayment, actor) -> EscrowPayment:
    """Enable the remaining 90% once the linked appointment is completed."""
    if payment.status == EscrowPayment.Status.SERVICE_COMPLETED:
        return payment
    if payment.status != EscrowPayment.Status.DEPOSIT_PAID:
        return payment

    with transaction.atomic():
        locked = EscrowPayment.objects.select_for_update().get(pk=payment.pk)
        if locked.status != EscrowPayment.Status.DEPOSIT_PAID:
            return locked
        locked.status = EscrowPayment.Status.SERVICE_COMPLETED
        locked.save(update_fields=["status", "updated_at"])

    log_audit_event(
        event_type=AUDIT_PAYMENT_SERVICE_COMPLETED,
        actor=actor,
        source="payments.service_completed",
        entity_type="payment",
        entity_id=payment.id,
        status="success",
        message="Servicio completado; saldo restante habilitado",
        metadata={"remaining_amount": str(payment.remaining_amount)},
    )
    payment.refresh_from_db()
    return payment


def mark_remaining_paid(payment: EscrowPayment, actor) -> EscrowPayment:
    """Simulate payment of the 90% remaining amount (mock provider)."""
    allowed = {EscrowPayment.Status.SERVICE_COMPLETED, EscrowPayment.Status.PENDING_REMAINING}
    if payment.status not in allowed:
        raise ValidationError({"status": "El saldo restante solo se puede pagar después de completar el servicio."})

    with transaction.atomic():
        payment.status = EscrowPayment.Status.REMAINING_PAID
        payment.provider_reference = f"MOCK-REM-{payment.id}"
        payment.save(update_fields=["status", "provider_reference", "updated_at"])
        PaymentTransaction.objects.create(
            payment=payment,
            transaction_type=PaymentTransaction.TransactionType.REMAINING,
            amount=payment.remaining_amount,
            status=PaymentTransaction.Status.COMPLETED,
            provider_reference=payment.provider_reference,
        )

    log_audit_event(
        event_type=AUDIT_PAYMENT_REMAINING_PAID,
        actor=actor,
        source="payments.remaining",
        entity_type="payment",
        entity_id=payment.id,
        status="success",
        message="Saldo restante del 90% pagado (mock)",
        metadata={"remaining_amount": str(payment.remaining_amount)},
    )
    return payment


def release_payment(payment: EscrowPayment, actor) -> EscrowPayment:
    """Release total payment to technician (admin/arbiter action or auto after remaining paid)."""
    releasable = {
        EscrowPayment.Status.DEPOSIT_PAID,
        EscrowPayment.Status.SERVICE_COMPLETED,
        EscrowPayment.Status.PENDING_REMAINING,
        EscrowPayment.Status.REMAINING_PAID,
        EscrowPayment.Status.DISPUTED,
    }
    if payment.status not in releasable:
        raise ValidationError({"status": "Este pago no puede ser liberado en su estado actual."})

    with transaction.atomic():
        payment.status = EscrowPayment.Status.RELEASED
        payment.save(update_fields=["status", "updated_at"])
        PaymentTransaction.objects.create(
            payment=payment,
            transaction_type=PaymentTransaction.TransactionType.RELEASE,
            amount=payment.total_amount,
            status=PaymentTransaction.Status.COMPLETED,
            provider_reference=f"MOCK-REL-{payment.id}",
        )

    log_audit_event(
        event_type=AUDIT_PAYMENT_RELEASED,
        actor=actor,
        source="payments.release",
        entity_type="payment",
        entity_id=payment.id,
        status="success",
        message="Pago liberado al técnico",
        metadata={"total_amount": str(payment.total_amount)},
    )
    return payment


def hold_for_dispute(payment: EscrowPayment, dispute) -> EscrowPayment:
    """Hold escrow payment when a dispute is opened. No-op if already terminal."""
    if payment.is_terminal:
        return payment

    prev_status = payment.status
    with transaction.atomic():
        payment.status = EscrowPayment.Status.DISPUTED
        payment.metadata = {**payment.metadata, "dispute_id": dispute.id, "held_from_status": prev_status}
        payment.save(update_fields=["status", "metadata", "updated_at"])
        PaymentTransaction.objects.create(
            payment=payment,
            transaction_type=PaymentTransaction.TransactionType.HOLD,
            amount=payment.total_amount,
            status=PaymentTransaction.Status.COMPLETED,
            metadata={"dispute_id": dispute.id, "held_from_status": prev_status},
        )

    log_audit_event(
        event_type=AUDIT_PAYMENT_DISPUTED,
        actor=None,
        source="payments.hold_for_dispute",
        entity_type="payment",
        entity_id=payment.id,
        status="info",
        message="Pago bloqueado por disputa abierta",
        metadata={"dispute_id": dispute.id, "previous_status": prev_status},
    )
    return payment


def refund_payment(payment: EscrowPayment, actor, reason: str = "") -> EscrowPayment:
    """Refund full escrow to client."""
    refundable = {
        EscrowPayment.Status.PENDING_DEPOSIT,
        EscrowPayment.Status.DEPOSIT_PAID,
        EscrowPayment.Status.SERVICE_COMPLETED,
        EscrowPayment.Status.PENDING_REMAINING,
        EscrowPayment.Status.DISPUTED,
    }
    if payment.status not in refundable:
        raise ValidationError({"status": "Este pago no puede ser reembolsado en su estado actual."})

    with transaction.atomic():
        payment.status = EscrowPayment.Status.REFUNDED
        payment.save(update_fields=["status", "updated_at"])
        PaymentTransaction.objects.create(
            payment=payment,
            transaction_type=PaymentTransaction.TransactionType.REFUND,
            amount=payment.total_amount,
            status=PaymentTransaction.Status.COMPLETED,
            provider_reference=f"MOCK-REF-{payment.id}",
            metadata={"reason": reason},
        )

    log_audit_event(
        event_type=AUDIT_PAYMENT_REFUNDED,
        actor=actor,
        source="payments.refund",
        entity_type="payment",
        entity_id=payment.id,
        status="success",
        message="Pago reembolsado al cliente",
        metadata={"total_amount": str(payment.total_amount), "reason": reason},
    )
    return payment


def cancel_payment(payment: EscrowPayment, actor, reason: str = "") -> EscrowPayment:
    """Cancel escrow (only when no real money has moved)."""
    cancellable = {EscrowPayment.Status.PENDING_DEPOSIT, EscrowPayment.Status.DEPOSIT_PAID}
    if payment.status not in cancellable:
        raise ValidationError({"status": "Solo se puede cancelar si la reserva aún no fue completada."})

    with transaction.atomic():
        payment.status = EscrowPayment.Status.CANCELLED
        payment.save(update_fields=["status", "updated_at"])

    log_audit_event(
        event_type=AUDIT_PAYMENT_CANCELLED,
        actor=actor,
        source="payments.cancel",
        entity_type="payment",
        entity_id=payment.id,
        status="success",
        message="Pago cancelado",
        metadata={"reason": reason},
    )
    return payment


def get_active_payment_for_client(client) -> EscrowPayment | None:
    """Return the most recent non-terminal payment for a client."""
    return (
        EscrowPayment.objects.filter(client=client)
        .exclude(status__in=[EscrowPayment.Status.RELEASED, EscrowPayment.Status.REFUNDED, EscrowPayment.Status.CANCELLED])
        .order_by("-created_at")
        .first()
    )
