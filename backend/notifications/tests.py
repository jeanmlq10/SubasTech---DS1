from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Notification
from .services import (
    build_telegram_message_payload,
    create_notification,
    render_notification_template,
)


class NotificationAPITests(TestCase):
    def test_user_only_sees_their_own_notifications(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(username="user", password="Password123")
        other = user_model.objects.create_user(username="other", password="Password123")
        Notification.objects.create(user=user, title="Visible", message="For current user")
        Notification.objects.create(user=other, title="Hidden", message="For another user")

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get("/api/notifications/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "Visible")

    def test_regular_user_cannot_create_notification(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(username="regular", password="Password123")

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.post(
            "/api/notifications/",
            {"title": "Unauthorized", "message": "Should not be allowed", "channel": "dashboard"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_notification_for_another_user(self):
        user_model = get_user_model()
        admin = user_model.objects.create_user(username="admin", password="Password123", role="admin")
        user = user_model.objects.create_user(username="target", password="Password123")

        client = APIClient()
        client.force_authenticate(user=admin)
        response = client.post(
            "/api/notifications/",
            {
                "user": user.id,
                "title": "Assigned",
                "message": "Created by admin",
                "channel": "dashboard",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(Notification.objects.filter(user=user, title="Assigned").exists())


class NotificationServiceTests(TestCase):
    def test_can_render_template_and_create_telegram_notification(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(username="template-user", password="Password123")

        rendered = render_notification_template(
            "appointment_reminder",
            {"technician_name": "Carlos", "scheduled_for": "2026-05-20 10:00"},
        )
        notification = create_notification(
            user=user,
            template_name="appointment_reminder",
            context={"technician_name": "Carlos", "scheduled_for": "2026-05-20 10:00"},
            channel=Notification.Channel.TELEGRAM,
        )

        self.assertEqual(rendered["title"], "Recordatorio de cita")
        self.assertIn("Carlos", rendered["message"])
        self.assertEqual(notification.channel, Notification.Channel.TELEGRAM)
        self.assertEqual(notification.title, rendered["title"])

    def test_builds_enriched_telegram_payload(self):
        payload = build_telegram_message_payload(
            chat_id=999,
            text="Revisa tu cita aqui: https://subastech.test/citas/1",
            preview_url=True,
            buttons=[{"text": "Ver cita", "url": "https://subastech.test/citas/1"}],
        )

        self.assertEqual(payload["chat_id"], 999)
        self.assertFalse(payload["disable_web_page_preview"])
        self.assertEqual(payload["reply_markup"]["inline_keyboard"][0][0]["text"], "Ver cita")
