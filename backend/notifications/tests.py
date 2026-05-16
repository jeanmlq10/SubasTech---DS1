from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Notification


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
