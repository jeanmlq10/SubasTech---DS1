from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient


class RegisterAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_model = get_user_model()

    def test_public_registration_allows_client_role(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "public-client",
                "email": "client@example.com",
                "password": "Password123",
                "role": "client",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(self.user_model.objects.filter(username="public-client", role="client").exists())

    def test_public_registration_rejects_admin_role(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "public-admin",
                "email": "admin@example.com",
                "password": "Password123",
                "role": "admin",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.json())
