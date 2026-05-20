from decimal import Decimal
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from unittest.mock import patch
from django.utils import timezone
from rest_framework.test import APIClient

from appointments.models import Appointment
from catalog.models import Category, Service, TechnicianAvailability, TechnicianProfile, Zone
from leads.models import ServiceLead

from .models import Auction, Bid


class AuctionWorkflowTests(TestCase):
    def setUp(self):
        self.client_api = APIClient()
        user_model = get_user_model()
        self.client_user = user_model.objects.create_user(
            username="auction-client",
            email="client@example.com",
            password="Password123",
            role="client",
            phone_number="3001234567",
        )
        self.other_client = user_model.objects.create_user(username="other-client", password="Password123", role="client")
        self.tech_user = user_model.objects.create_user(username="auction-tech", password="Password123", role="technician")
        self.other_tech_user = user_model.objects.create_user(username="other-tech", password="Password123", role="technician")
        self.unverified_user = user_model.objects.create_user(username="unverified-tech", password="Password123", role="technician")
        self.category = Category.objects.create(name="Electricista", slug="electricista", is_active=True)
        self.zone = Zone.objects.create(name="Villa Santos", slug="barranquilla-villa-santos", city="Barranquilla", is_active=True)
        self.profile = TechnicianProfile.objects.create(user=self.tech_user, is_verified=True, availability_status="available")
        self.other_profile = TechnicianProfile.objects.create(user=self.other_tech_user, is_verified=True, availability_status="available")
        self.unverified_profile = TechnicianProfile.objects.create(user=self.unverified_user, is_verified=False)
        self.service = Service.objects.create(
            technician=self.profile,
            category=self.category,
            title="Revision electrica",
            description="Revision residencial",
            base_price=90000,
        )

    def create_auction(self):
        return Auction.objects.create(
            client=self.client_user,
            category=self.category,
            zone=self.zone,
            title="Necesito electricista",
            description="Breaker principal falla",
            location="Villa Santos",
            budget_max=120000,
        )

    def test_client_can_create_auction(self):
        self.client_api.force_authenticate(self.client_user)

        response = self.client_api.post(
            "/api/auctions/",
            {
                "category": self.category.id,
                "zone": self.zone.id,
                "title": "Instalacion urgente",
                "description": "Necesito cambiar tomacorrientes",
                "location": "Villa Santos",
                "budget_min": "50000",
                "budget_max": "120000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        auction = Auction.objects.get()
        self.assertEqual(auction.client, self.client_user)
        self.assertEqual(auction.status, Auction.Status.OPEN)

    def test_verified_technician_can_bid_on_open_auction(self):
        auction = self.create_auction()
        self.client_api.force_authenticate(self.tech_user)

        response = self.client_api.post(
            "/api/auction-bids/",
            {
                "auction": auction.id,
                "service": self.service.id,
                "amount": "85000",
                "message": "Puedo atender hoy.",
                "estimated_minutes": 90,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        bid = Bid.objects.get()
        self.assertEqual(bid.technician, self.profile)
        self.assertEqual(bid.amount, Decimal("85000.00"))

    def test_telegram_auction_requires_bid_available_from(self):
        auction = self.create_auction()
        auction.source = Auction.Source.TELEGRAM
        auction.metadata = {"chat_id": 123}
        auction.save(update_fields=["source", "metadata", "updated_at"])
        self.client_api.force_authenticate(self.tech_user)

        response = self.client_api.post(
            "/api/auction-bids/",
            {
                "auction": auction.id,
                "service": self.service.id,
                "amount": "85000",
                "message": "Puedo atender hoy.",
                "estimated_minutes": 90,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("available_from", response.json())
        self.assertFalse(Bid.objects.exists())

    @patch("auctions.views.TelegramBotClient.send_message")
    def test_telegram_auction_bid_notifies_client_chat(self, mock_send_message):
        auction = self.create_auction()
        auction.source = Auction.Source.TELEGRAM
        auction.metadata = {"chat_id": 123}
        auction.save(update_fields=["source", "metadata", "updated_at"])
        self.client_api.force_authenticate(self.tech_user)
        start = self._next_available_start()

        response = self.client_api.post(
            "/api/auction-bids/",
            {
                "auction": auction.id,
                "service": self.service.id,
                "amount": "85000",
                "message": "Puedo atender hoy.",
                "estimated_minutes": 90,
                "available_from": start.isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        mock_send_message.assert_called_once()
        payload = mock_send_message.call_args.args[0]
        self.assertEqual(payload["chat_id"], 123)
        self.assertIn("ACEPTO:", payload["text"])
        self.assertIn("auction-tech", payload["text"])

    def test_unverified_technician_cannot_bid(self):
        auction = self.create_auction()
        self.client_api.force_authenticate(self.unverified_user)

        response = self.client_api.post(
            "/api/auction-bids/",
            {"auction": auction.id, "amount": "85000", "message": "Estoy disponible."},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Bid.objects.exists())

    def test_client_awards_bid_and_creates_technician_lead(self):
        auction = self.create_auction()
        winning_bid = Bid.objects.create(auction=auction, technician=self.profile, service=self.service, amount=85000)
        losing_bid = Bid.objects.create(auction=auction, technician=self.other_profile, amount=95000)
        self.client_api.force_authenticate(self.client_user)

        response = self.client_api.post(f"/api/auctions/{auction.id}/award/", {"bid_id": winning_bid.id}, format="json")

        self.assertEqual(response.status_code, 200)
        auction.refresh_from_db()
        winning_bid.refresh_from_db()
        losing_bid.refresh_from_db()
        self.assertEqual(auction.status, Auction.Status.AWARDED)
        self.assertEqual(auction.winning_bid, winning_bid)
        self.assertEqual(winning_bid.status, Bid.Status.ACCEPTED)
        self.assertEqual(losing_bid.status, Bid.Status.REJECTED)
        lead = ServiceLead.objects.get()
        self.assertEqual(lead.technician, self.profile)
        self.assertEqual(lead.client_user, self.client_user)
        self.assertEqual(lead.status, ServiceLead.Status.ACCEPTED)
        self.assertEqual(lead.metadata["auction_id"], auction.id)

    def test_awarding_bid_with_available_from_creates_appointment(self):
        auction = self.create_auction()
        start = self._next_available_start()
        TechnicianAvailability.objects.create(
            technician=self.profile,
            weekday=timezone.localtime(start).isoweekday(),
            start_time=time(9, 0),
            end_time=time(12, 0),
            is_active=True,
        )
        bid = Bid.objects.create(
            auction=auction,
            technician=self.profile,
            service=self.service,
            amount=85000,
            available_from=start,
            estimated_minutes=60,
        )
        self.client_api.force_authenticate(self.client_user)

        response = self.client_api.post(f"/api/auctions/{auction.id}/award/", {"bid_id": bid.id}, format="json")

        self.assertEqual(response.status_code, 200)
        appointment = Appointment.objects.select_related("lead").get()
        self.assertEqual(appointment.client, self.client_user)
        self.assertEqual(appointment.technician, self.profile)
        self.assertEqual(appointment.lead.metadata["auction_id"], auction.id)
        self.assertEqual(appointment.metadata["source"], "auction_award")

    def test_other_client_cannot_award_auction(self):
        auction = self.create_auction()
        bid = Bid.objects.create(auction=auction, technician=self.profile, amount=85000)
        self.client_api.force_authenticate(self.other_client)

        response = self.client_api.post(f"/api/auctions/{auction.id}/award/", {"bid_id": bid.id}, format="json")

        self.assertEqual(response.status_code, 404)
        auction.refresh_from_db()
        self.assertEqual(auction.status, Auction.Status.OPEN)

    def test_technician_only_sees_own_bids(self):
        auction = self.create_auction()
        own_bid = Bid.objects.create(auction=auction, technician=self.profile, amount=85000)
        Bid.objects.create(auction=auction, technician=self.other_profile, amount=95000)
        self.client_api.force_authenticate(self.tech_user)

        response = self.client_api.get("/api/auction-bids/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["id"], own_bid.id)

    def test_open_auction_list_only_embeds_authenticated_technician_bid(self):
        auction = self.create_auction()
        own_bid = Bid.objects.create(auction=auction, technician=self.profile, amount=85000)
        Bid.objects.create(auction=auction, technician=self.other_profile, amount=95000)
        self.client_api.force_authenticate(self.tech_user)

        response = self.client_api.get("/api/auctions/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(len(response.json()[0]["bids"]), 1)
        self.assertEqual(response.json()[0]["bids"][0]["id"], own_bid.id)

    def _next_available_start(self):
        today = timezone.localdate()
        target_date = today + timedelta(days=(1 - today.isoweekday()) % 7 or 7)
        return timezone.make_aware(datetime.combine(target_date, time(9, 0)), timezone.get_current_timezone())
