from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Category, Service, TechnicianProfile
from .models import ServiceLead


class TechnicianLeadTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.tech_user = user_model.objects.create_user(username="lead-tech", password="Password123", role="technician")
        other_user = user_model.objects.create_user(username="other-tech", password="Password123", role="technician")
        category = Category.objects.create(name="Electrician", slug="electrician")
        self.profile = TechnicianProfile.objects.create(user=self.tech_user, is_verified=True)
        other_profile = TechnicianProfile.objects.create(user=other_user, is_verified=True)
        service = Service.objects.create(technician=self.profile, category=category, title="Servicio propio", description="A", base_price=1)
        other_service = Service.objects.create(technician=other_profile, category=category, title="Servicio otro", description="B", base_price=1)
        self.lead = ServiceLead.objects.create(
            technician=self.profile,
            service=service,
            client_phone="573001112233",
            message="Necesito luz",
            category="electrician",
            location="Riomar",
        )
        ServiceLead.objects.create(
            technician=other_profile,
            service=other_service,
            client_phone="573004445566",
            message="Otro lead",
        )

    def test_technician_only_reads_own_leads(self):
        self.client.force_authenticate(self.tech_user)

        response = self.client.get("/api/technician/leads/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["client_phone"], "573001112233")

    def test_technician_can_update_lead_status(self):
        self.client.force_authenticate(self.tech_user)

        response = self.client.post(f"/api/technician/leads/{self.lead.id}/status/", {"status": "contacted"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, ServiceLead.Status.CONTACTED)
