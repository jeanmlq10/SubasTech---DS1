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
        self.assertEqual(self.user_model.objects.get(username="public-client").email, "client@example.com")

    def test_public_registration_rejects_client_without_email(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "client-no-email",
                "password": "Password123",
                "role": "client",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json())

    def test_public_registration_rejects_duplicate_email_case_insensitive(self):
        self.user_model.objects.create_user(
            username="existing-client",
            email="client@example.com",
            password="Password123",
            role="client",
        )

        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "duplicate-client",
                "email": "CLIENT@example.com",
                "password": "Password123",
                "role": "client",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json())

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

    def test_public_registration_allows_technician_without_email(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "public-tech",
                "password": "Password123",
                "role": "technician",
                "technician_trade": "electrician",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(self.user_model.objects.filter(username="public-tech", role="technician").exists())
        self.assertEqual(self.user_model.objects.get(username="public-tech").technician_trade, "electrician")

    def test_public_registration_rejects_technician_without_profession(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "public-tech-no-trade",
                "password": "Password123",
                "role": "technician",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("technician_trade", response.json())


class AuthSessionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username="session-user",
            password="Password123",
            role="technician",
            email="session@example.com",
            technician_trade="electrician",
        )

    def test_token_obtain_pair_returns_jwt_for_valid_credentials(self):
        response = self.client.post(
            "/api/auth/token/",
            {
                "username": "session-user",
                "password": "Password123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
        self.assertIn("refresh", response.json())

    def test_token_obtain_pair_accepts_email_credentials(self):
        response = self.client.post(
            "/api/auth/token/",
            {
                "email": "SESSION@example.com",
                "password": "Password123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
        self.assertIn("refresh", response.json())

    def test_token_obtain_pair_rejects_invalid_email_credentials(self):
        response = self.client.post(
            "/api/auth/token/",
            {
                "email": "session@example.com",
                "password": "WrongPassword123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_me_returns_authenticated_user_with_jwt(self):
        token_response = self.client.post(
            "/api/auth/token/",
            {
                "username": "session-user",
                "password": "Password123",
            },
            format="json",
        )
        access = token_response.json()["access"]

        response = self.client.get(
            "/api/auth/me/",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "session-user")
        self.assertEqual(response.json()["role"], "technician")
        self.assertEqual(response.json()["technician_trade"], "electrician")
