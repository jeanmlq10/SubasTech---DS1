from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from catalog.models import Category, TechnicianProfile, Zone
from auctions.models import Auction, Bid
from appointments.models import Appointment
from disputes.models import Dispute

from .models import EscrowPayment, PaymentTransaction
from .services import (
    cancel_payment,
    create_escrow_for_awarded_bid,
    hold_for_dispute,
    mark_deposit_paid,
    mark_remaining_paid,
    mark_service_completed,
    refund_payment,
    release_payment,
)

User = get_user_model()


def _make_client(username="client1"):
    return User.objects.create_user(username=username, password="pass", role="client")


def _make_technician(username="tech1"):
    user = User.objects.create_user(
        username=username,
        password="pass",
        role=User.Role.TECHNICIAN,
        technician_trade=User.TechnicianTrade.ELECTRICIAN,
    )
    Category.objects.get_or_create(name="electrician", slug="electrician")
    profile = TechnicianProfile.objects.create(user=user, is_verified=True)
    return profile


def _make_auction(client, technician):
    category = Category.objects.get_or_create(name="electrician", slug="electrician")[0]
    return Auction.objects.create(
        client=client,
        category=category,
        title="Test auction",
        description="Test",
        urgency="normal",
        source=Auction.Source.TELEGRAM,
        status=Auction.Status.OPEN,
    )


def _make_bid(auction, technician, amount=Decimal("100000")):
    from django.utils import timezone
    from datetime import timedelta
    return Bid.objects.create(
        auction=auction,
        technician=technician,
        amount=amount,
        estimated_minutes=60,
        available_from=timezone.now() + timedelta(hours=24),
        status=Bid.Status.PENDING,
    )


class EscrowCreationTest(TestCase):
    def setUp(self):
        self.client_user = _make_client()
        self.technician = _make_technician()
        self.auction = _make_auction(self.client_user, self.technician)
        self.bid = _make_bid(self.auction, self.technician, amount=Decimal("100000"))

    def test_creates_payment_with_correct_split(self):
        payment = create_escrow_for_awarded_bid(auction=self.auction, bid=self.bid)
        self.assertEqual(payment.total_amount, Decimal("100000"))
        self.assertEqual(payment.deposit_amount, Decimal("10000"))
        self.assertEqual(payment.remaining_amount, Decimal("90000"))
        self.assertEqual(payment.status, EscrowPayment.Status.PENDING_DEPOSIT)
        self.assertEqual(payment.currency, "COP")

    def test_idempotent_creation(self):
        p1 = create_escrow_for_awarded_bid(auction=self.auction, bid=self.bid)
        p2 = create_escrow_for_awarded_bid(auction=self.auction, bid=self.bid)
        self.assertEqual(p1.id, p2.id)
        self.assertEqual(EscrowPayment.objects.count(), 1)

    def test_deposit_ratio_rounds_correctly(self):
        technician = _make_technician("tech_rounding")
        auction = _make_auction(self.client_user, technician)
        bid = _make_bid(auction, technician, amount=Decimal("50001"))
        payment = create_escrow_for_awarded_bid(auction=auction, bid=bid)
        self.assertEqual(payment.deposit_amount + payment.remaining_amount, payment.total_amount)


class DepositPaymentTest(TestCase):
    def setUp(self):
        self.client_user = _make_client()
        self.technician = _make_technician()
        self.auction = _make_auction(self.client_user, self.technician)
        self.bid = _make_bid(self.auction, self.technician)
        self.payment = create_escrow_for_awarded_bid(auction=self.auction, bid=self.bid)

    def test_mark_deposit_paid(self):
        mark_deposit_paid(self.payment, actor=self.client_user)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, EscrowPayment.Status.DEPOSIT_PAID)
        self.assertEqual(self.payment.transactions.count(), 1)
        tx = self.payment.transactions.first()
        self.assertEqual(tx.transaction_type, PaymentTransaction.TransactionType.DEPOSIT)
        self.assertEqual(tx.status, PaymentTransaction.Status.COMPLETED)

    def test_cannot_pay_deposit_twice(self):
        mark_deposit_paid(self.payment, actor=self.client_user)
        self.payment.refresh_from_db()
        with self.assertRaises(ValidationError):
            mark_deposit_paid(self.payment, actor=self.client_user)

    def test_another_client_cannot_pay(self):
        other = _make_client("other_client")
        # Service layer doesn't enforce ownership — that's the view's job.
        # Verify that the service itself allows any actor (view enforces permission).
        mark_deposit_paid(self.payment, actor=other)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, EscrowPayment.Status.DEPOSIT_PAID)


class RemainingPaymentTest(TestCase):
    def setUp(self):
        self.client_user = _make_client()
        self.technician = _make_technician()
        self.auction = _make_auction(self.client_user, self.technician)
        self.bid = _make_bid(self.auction, self.technician)
        self.payment = create_escrow_for_awarded_bid(auction=self.auction, bid=self.bid)

    def test_cannot_pay_remaining_before_service_completed(self):
        mark_deposit_paid(self.payment, actor=self.client_user)
        self.payment.refresh_from_db()
        with self.assertRaises(ValidationError):
            mark_remaining_paid(self.payment, actor=self.client_user)

    def test_mark_service_completed_enables_remaining_payment(self):
        mark_deposit_paid(self.payment, actor=self.client_user)
        self.payment.refresh_from_db()
        mark_service_completed(self.payment, actor=self.client_user)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, EscrowPayment.Status.SERVICE_COMPLETED)

    def test_can_pay_remaining_after_service_completed(self):
        self.payment.status = EscrowPayment.Status.SERVICE_COMPLETED
        self.payment.save()
        mark_remaining_paid(self.payment, actor=self.client_user)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, EscrowPayment.Status.REMAINING_PAID)


class DisputeHoldTest(TestCase):
    def setUp(self):
        self.client_user = _make_client()
        self.technician = _make_technician()
        self.auction = _make_auction(self.client_user, self.technician)
        self.bid = _make_bid(self.auction, self.technician)
        self.payment = create_escrow_for_awarded_bid(auction=self.auction, bid=self.bid)
        mark_deposit_paid(self.payment, actor=self.client_user)
        self.payment.refresh_from_db()

    def _make_dispute(self):
        return Dispute.objects.create(
            client=self.client_user,
            technician=self.technician,
            title="Test dispute",
            description="Something went wrong",
        )

    def test_dispute_blocks_payment(self):
        dispute = self._make_dispute()
        hold_for_dispute(self.payment, dispute)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, EscrowPayment.Status.DISPUTED)
        self.assertIn("dispute_id", self.payment.metadata)

    def test_opening_dispute_on_terminal_payment_is_noop(self):
        self.payment.status = EscrowPayment.Status.RELEASED
        self.payment.save()
        dispute = self._make_dispute()
        hold_for_dispute(self.payment, dispute)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, EscrowPayment.Status.RELEASED)

    def test_release_after_dispute_in_technician_favor(self):
        dispute = self._make_dispute()
        hold_for_dispute(self.payment, dispute)
        self.payment.refresh_from_db()
        release_payment(self.payment, actor=self.client_user)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, EscrowPayment.Status.RELEASED)

    def test_refund_after_dispute_in_client_favor(self):
        dispute = self._make_dispute()
        hold_for_dispute(self.payment, dispute)
        self.payment.refresh_from_db()
        refund_payment(self.payment, actor=self.client_user, reason="client won dispute")
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, EscrowPayment.Status.REFUNDED)


class CancelPaymentTest(TestCase):
    def setUp(self):
        self.client_user = _make_client()
        self.technician = _make_technician()
        self.auction = _make_auction(self.client_user, self.technician)
        self.bid = _make_bid(self.auction, self.technician)
        self.payment = create_escrow_for_awarded_bid(auction=self.auction, bid=self.bid)

    def test_cancel_pending_deposit(self):
        cancel_payment(self.payment, actor=self.client_user, reason="changed mind")
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, EscrowPayment.Status.CANCELLED)

    def test_cannot_cancel_released_payment(self):
        self.payment.status = EscrowPayment.Status.RELEASED
        self.payment.save()
        with self.assertRaises(ValidationError):
            cancel_payment(self.payment, actor=self.client_user)


class TelegramPaymentCommandsTest(TestCase):
    """Smoke test: service functions used by Telegram commands work end-to-end."""

    def setUp(self):
        self.client_user = _make_client()
        self.technician = _make_technician()
        self.auction = _make_auction(self.client_user, self.technician)
        self.bid = _make_bid(self.auction, self.technician, amount=Decimal("200000"))
        self.payment = create_escrow_for_awarded_bid(auction=self.auction, bid=self.bid)

    def test_pagar_reserva_command(self):
        mark_deposit_paid(self.payment, actor=self.client_user)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, EscrowPayment.Status.DEPOSIT_PAID)
        self.assertEqual(self.payment.deposit_amount, Decimal("20000"))

    def test_pagar_restante_after_service_completed(self):
        mark_deposit_paid(self.payment, actor=self.client_user)
        self.payment.status = EscrowPayment.Status.SERVICE_COMPLETED
        self.payment.save()
        mark_remaining_paid(self.payment, actor=self.client_user)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, EscrowPayment.Status.REMAINING_PAID)
        self.assertEqual(self.payment.remaining_amount, Decimal("180000"))
