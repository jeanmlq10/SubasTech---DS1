from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Category, Service, TechnicianProfile
from .models import Dispute
from .services import build_dispute_assistant_payload, classify_dispute


class ArbiterWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.arbiter = user_model.objects.create_user(username="arbiter", password="Password123", role="arbiter")
        self.client_user = user_model.objects.create_user(username="client", password="Password123", role="client")
        self.tech_user = user_model.objects.create_user(
            username="tech",
            password="Password123",
            role="technician",
            first_name="Laura",
            last_name="Perez",
        )
        category = Category.objects.create(name="Appliance Repair", slug="appliance-repair")
        profile = TechnicianProfile.objects.create(user=self.tech_user, is_verified=True)
        service = Service.objects.create(
            technician=profile,
            category=category,
            title="Reparacion de lavadora",
            description="Diagnostico y reparacion de electrodomesticos.",
            base_price=90000,
        )
        self.dispute = Dispute.objects.create(
            client=self.client_user,
            technician=profile,
            service=service,
            title="Trabajo incompleto",
            description="La lavadora quedo con el mismo fallo y el tecnico no llego a corregirlo.",
            ai_summary="La lavadora quedo con el mismo fallo.",
            priority="high",
        )

    def test_arbiter_can_read_queue_with_assistant_payload(self):
        self.client.force_authenticate(self.arbiter)

        response = self.client.get("/api/arbiter/queue/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["metrics"]["open"], 1)
        self.assertEqual(body["disputes"][0]["assistant"]["classification"], "technician_behavior")
        self.assertEqual(body["disputes"][0]["technician_name"], "Laura Perez")

    def test_client_cannot_read_arbiter_queue(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get("/api/arbiter/queue/")

        self.assertEqual(response.status_code, 403)

    def test_arbiter_can_claim_and_resolve_dispute(self):
        self.client.force_authenticate(self.arbiter)

        claim_response = self.client.post(f"/api/arbiter/disputes/{self.dispute.id}/claim/")
        self.assertEqual(claim_response.status_code, 200)
        self.dispute.refresh_from_db()
        self.assertEqual(self.dispute.status, Dispute.Status.IN_REVIEW)
        self.assertEqual(self.dispute.arbiter, self.arbiter)

        decision_response = self.client.post(
            f"/api/arbiter/disputes/{self.dispute.id}/decision/",
            {"decision": Dispute.Decision.FAVOR_CLIENT, "notes": "Evidence supports the client."},
            format="json",
        )

        self.assertEqual(decision_response.status_code, 200)
        self.dispute.refresh_from_db()
        self.assertEqual(self.dispute.status, Dispute.Status.RESOLVED)
        self.assertEqual(self.dispute.decision, Dispute.Decision.FAVOR_CLIENT)
        self.assertEqual(self.dispute.arbiter_notes, "Evidence supports the client.")

    def test_invalid_pending_decision_is_rejected(self):
        self.client.force_authenticate(self.arbiter)

        response = self.client.post(
            f"/api/arbiter/disputes/{self.dispute.id}/decision/",
            {"decision": Dispute.Decision.PENDING},
            format="json",
        )

        self.assertEqual(response.status_code, 400)


class DisputeAssistantTests(TestCase):
    def test_classifies_service_quality(self):
        self.assertEqual(classify_dispute("El trabajo quedo incompleto y con defecto"), "service_quality")

    def test_builds_assistant_payload(self):
        dispute = type(
            "DisputeStub",
            (),
            {
                "description": "Hubo un cobro mayor al acordado.",
                "ai_summary": "",
                "priority": "normal",
            },
        )()

        payload = build_dispute_assistant_payload(dispute)

        self.assertEqual(payload["classification"], "pricing_or_payment")
        self.assertEqual(payload["suggested_priority"], "normal")
        self.assertTrue(payload["recommended_review_steps"])
