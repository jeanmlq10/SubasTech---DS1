from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from audit.models import AuditEvent
from catalog.models import Category, Service, TechnicianProfile, Zone
from disputes.models import Dispute
from leads.models import ServiceLead
from reputation.models import Rating


class AdminSummaryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(username="admin", password="Password123", role="admin")
        self.client_user = user_model.objects.create_user(username="client", password="Password123", role="client")
        self.tech_user = user_model.objects.create_user(
            username="tech",
            password="Password123",
            role="technician",
            first_name="Carlos",
            last_name="Mendoza",
        )
        category = Category.objects.create(name="Electrician", slug="electrician")
        zone = Zone.objects.create(name="Riomar", city="Barranquilla")
        profile = TechnicianProfile.objects.create(
            user=self.tech_user,
            is_verified=False,
            availability_status=TechnicianProfile.AvailabilityStatus.AVAILABLE,
            response_time_minutes=20,
            service_completion_rate=90,
        )
        profile.zones.add(zone)
        service = Service.objects.create(
            technician=profile,
            category=category,
            title="Instalacion electrica",
            description="Servicio residencial",
            base_price=80000,
        )
        ServiceLead.objects.create(
            technician=profile,
            client_user=self.client_user,
            service=service,
            client_phone="573001112233",
            message="Necesito una visita",
            status=ServiceLead.Status.NEW,
        )
        ServiceLead.objects.create(
            technician=profile,
            client_user=self.client_user,
            service=service,
            client_phone="573001112233",
            message="Ya me contactaron",
            status=ServiceLead.Status.CONTACTED,
        )
        ServiceLead.objects.create(
            technician=profile,
            client_user=self.client_user,
            service=service,
            client_phone="573001112233",
            message="Trabajo cerrado",
            status=ServiceLead.Status.CLOSED,
        )
        Rating.objects.create(
            author=self.client_user,
            technician=profile,
            service=service,
            target_role=Rating.TargetRole.TECHNICIAN,
            score=5,
        )
        Dispute.objects.create(
            client=self.client_user,
            technician=profile,
            service=service,
            title="Trabajo incompleto",
            description="El servicio no quedo terminado.",
            priority="high",
        )
        AuditEvent.objects.create(
            event_type=AuditEvent.EventType.INTEGRATION_ERROR,
            source="whatsapp.send_text",
            status="error",
            entity_type="conversation",
            entity_id="573001112233",
            message="Meta API timeout",
        )

    def test_admin_role_can_read_summary(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get("/api/admin/summary/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["metrics"]["total_technicians"], 1)
        self.assertEqual(body["metrics"]["pending_verification"], 1)
        self.assertEqual(body["metrics"]["open_disputes"], 1)
        self.assertEqual(body["metrics"]["total_leads"], 3)
        self.assertEqual(body["metrics"]["new_leads"], 1)
        self.assertEqual(body["metrics"]["contacted_leads"], 1)
        self.assertEqual(body["metrics"]["closed_leads"], 1)
        self.assertEqual(body["metrics"]["recent_integration_errors"], 1)
        self.assertEqual(body["lead_status_breakdown"]["new"], 1)
        self.assertEqual(body["recent_errors"][0]["source"], "whatsapp.send_text")
        self.assertEqual(body["recent_technicians"][0]["name"], "Carlos Mendoza")
        self.assertTrue(body["alerts"])

    def test_non_admin_cannot_read_summary(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get("/api/admin/summary/")

        self.assertEqual(response.status_code, 403)

    def test_summary_counts_suspended_technicians(self):
        self.tech_user.is_active = False
        self.tech_user.save(update_fields=["is_active"])
        self.client.force_authenticate(self.admin)

        response = self.client.get("/api/admin/summary/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["metrics"]["suspended_technicians"], 1)


class AdminTechnicianActionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(username="action-admin", password="Password123", role="admin")
        self.client_user = user_model.objects.create_user(username="action-client", password="Password123", role="client")
        self.tech_user = user_model.objects.create_user(username="action-tech", password="Password123", role="technician")
        self.profile = TechnicianProfile.objects.create(user=self.tech_user, is_verified=False)

    def test_admin_can_moderate_technician(self):
        self.client.force_authenticate(self.admin)

        verify_response = self.client.post(f"/api/admin/technicians/{self.profile.id}/verify/")
        self.assertEqual(verify_response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_verified)

        suspend_response = self.client.post(f"/api/admin/technicians/{self.profile.id}/suspend/")
        self.assertEqual(suspend_response.status_code, 200)
        self.tech_user.refresh_from_db()
        self.assertFalse(self.tech_user.is_active)

        activate_response = self.client.post(f"/api/admin/technicians/{self.profile.id}/activate/")
        self.assertEqual(activate_response.status_code, 200)
        self.tech_user.refresh_from_db()
        self.assertTrue(self.tech_user.is_active)
        self.assertEqual(AuditEvent.objects.filter(event_type=AuditEvent.EventType.ADMIN_ACTION).count(), 3)

    def test_non_admin_cannot_moderate_technician(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(f"/api/admin/technicians/{self.profile.id}/verify/")

        self.assertEqual(response.status_code, 403)


class HealthEndpointTests(TestCase):
    def test_health_endpoint_is_public(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertIn("counts", response.json())
