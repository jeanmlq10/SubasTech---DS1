from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from appointments.models import Appointment
from audit.models import AuditEvent
from catalog.models import Category, Service, TechnicianProfile
from .models import ServiceLead


class TechnicianLeadTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.tech_user = user_model.objects.create_user(username="lead-tech", password="Password123", role="technician")
        self.client_user = user_model.objects.create_user(
            username="lead-client",
            password="Password123",
            role="client",
            address="Calle 18 #20-30",
        )
        other_user = user_model.objects.create_user(username="other-tech", password="Password123", role="technician")
        category = Category.objects.create(name="Electrician", slug="electrician")
        self.profile = TechnicianProfile.objects.create(user=self.tech_user, is_verified=True)
        other_profile = TechnicianProfile.objects.create(user=other_user, is_verified=True)
        self.service = Service.objects.create(technician=self.profile, category=category, title="Servicio propio", description="A", base_price=1)
        other_service = Service.objects.create(technician=other_profile, category=category, title="Servicio otro", description="B", base_price=1)
        self.lead = ServiceLead.objects.create(
            technician=self.profile,
            service=self.service,
            client_user=self.client_user,
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

    def test_lead_includes_linked_appointment_details(self):
        start = timezone.make_aware(datetime(2026, 5, 25, 9, 0))
        appointment = Appointment.objects.create(
            client=self.client_user,
            technician=self.profile,
            service=self.service,
            lead=self.lead,
            scheduled_start=start,
            scheduled_end=start + timedelta(hours=1),
            status=Appointment.Status.CONFIRMED,
            metadata={"client_address": "Carrera 18 #20-30", "request_text": "Urgencia electrica residencial"},
        )
        self.client.force_authenticate(self.tech_user)

        response = self.client.get("/api/technician/leads/")

        self.assertEqual(response.status_code, 200)
        body = response.json()[0]
        self.assertEqual(body["appointment"]["id"], appointment.id)
        self.assertEqual(body["appointment"]["status"], Appointment.Status.CONFIRMED)
        self.assertEqual(body["appointment"]["client_address"], "Carrera 18 #20-30")
        self.assertEqual(body["appointment"]["request_text"], "Urgencia electrica residencial")

    def test_technician_can_update_lead_status(self):
        self.client.force_authenticate(self.tech_user)

        response = self.client.post(f"/api/technician/leads/{self.lead.id}/status/", {"status": "contacted"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, ServiceLead.Status.CONTACTED)
        event = AuditEvent.objects.get(event_type=AuditEvent.EventType.LEAD_STATUS_CHANGED)
        self.assertEqual(event.entity_id, str(self.lead.id))
        self.assertEqual(event.metadata["new_status"], ServiceLead.Status.CONTACTED)
