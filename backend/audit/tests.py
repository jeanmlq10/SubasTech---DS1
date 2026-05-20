from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import AuditEvent
from .services import log_audit_event


class AuditServiceTests(TestCase):
    def test_log_audit_event_persists_metadata(self):
        user_model = get_user_model()
        actor = user_model.objects.create_user(username="auditor", password="Password123", role="admin")

        event = log_audit_event(
            event_type=AuditEvent.EventType.ADMIN_ACTION,
            actor=actor,
            source="adminpanel",
            entity_type="technician",
            entity_id=12,
            status="success",
            message="Technician verified",
            metadata={"action": "verify"},
        )

        self.assertEqual(event.actor, actor)
        self.assertEqual(event.entity_id, "12")
        self.assertEqual(event.metadata["action"], "verify")


class AuditAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(username="audit-admin", password="Password123", role="admin")
        self.client_user = user_model.objects.create_user(username="audit-client", password="Password123", role="client")
        AuditEvent.objects.create(
            event_type=AuditEvent.EventType.WEBHOOK_RECEIVED,
            actor=self.admin,
            source="whatsapp",
            status="info",
            message="Webhook received",
        )

    def test_admin_can_list_audit_events(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get("/api/audit/events/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_non_admin_cannot_list_audit_events(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get("/api/audit/events/")

        self.assertEqual(response.status_code, 403)
