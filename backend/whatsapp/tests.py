from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from catalog.models import Category, Service, TechnicianProfile, Zone
from reputation.models import Rating
from leads.models import ServiceLead
from .ai import extract_intent
from .views import build_recommendation_reply


class WhatsAppIntentTests(TestCase):
    def test_extracts_category_location_and_urgency(self):
        intent = extract_intent("Necesito un electricista urgente en Riomar")

        self.assertEqual(intent["category"], "electrician")
        self.assertEqual(intent["location"], "riomar")
        self.assertEqual(intent["urgency"], "high")


class WhatsAppWebhookTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        category = Category.objects.create(name="Electrician", slug="electrician")
        zone = Zone.objects.create(name="Riomar", city="Barranquilla")
        tech_user = user_model.objects.create_user(
            username="tech-whatsapp",
            password="Password123",
            role="technician",
            first_name="Carlos",
            last_name="Mendoza",
        )
        client_user = user_model.objects.create_user(username="client-whatsapp", password="Password123", role="client")
        profile = TechnicianProfile.objects.create(
            user=tech_user,
            is_verified=True,
            availability_status=TechnicianProfile.AvailabilityStatus.AVAILABLE,
            response_time_minutes=15,
            completed_services=20,
            service_completion_rate=98,
        )
        profile.zones.add(zone)
        service = Service.objects.create(
            technician=profile,
            category=category,
            title="Instalacion electrica",
            description="Servicio residencial",
            base_price=80000,
        )
        Rating.objects.create(technician=profile, client=client_user, service=service, score=5)

    def test_verifies_webhook_challenge(self):
        response = self.client.get(
            "/api/whatsapp/webhook/",
            {"hub.verify_token": "subastech-dev-token", "hub.challenge": "12345"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "12345")

    @override_settings(ROOT_URLCONF="config.urls")
    def test_replies_with_recommendations_in_dry_run_mode(self):
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "573001112233",
                                        "text": {"body": "Necesito un electricista urgente en Riomar"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        response = self.client.post("/api/whatsapp/webhook/", payload, format="json")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["sender"], "573001112233")
        self.assertEqual(body["intent"]["category"], "electrician")
        self.assertEqual(len(body["recommendations"]), 1)
        self.assertIn("Carlos Mendoza", body["reply_text"])
        self.assertTrue(body["outbound"]["dry_run"])


    def test_numeric_selection_creates_lead(self):
        initial_payload = {"from": "573001112233", "message": "Necesito un electricista urgente en Riomar"}
        initial_response = self.client.post("/api/whatsapp/webhook/", initial_payload, format="json")
        self.assertEqual(initial_response.status_code, 200)

        selection_response = self.client.post("/api/whatsapp/webhook/", {"from": "573001112233", "message": "1"}, format="json")

        self.assertEqual(selection_response.status_code, 200)
        self.assertEqual(ServiceLead.objects.count(), 1)
        lead = ServiceLead.objects.first()
        self.assertEqual(lead.client_phone, "573001112233")
        self.assertEqual(lead.status, ServiceLead.Status.NEW)
        self.assertIn("Enviamos tu solicitud", selection_response.json()["reply_text"])

    def test_builds_fallback_reply_when_no_recommendations_exist(self):
        reply = build_recommendation_reply({"category": "plumber", "location": "Boston"}, [])

        self.assertIn("aun no encontre tecnicos", reply)
