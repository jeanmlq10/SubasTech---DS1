from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .services import interpret_message


@override_settings(GEMINI_API_KEY="")
class LLMTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="llm-user",
            password="Password123",
            role="admin",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch("llm.client.GeminiIntentClient.interpret")
    def test_interpret_endpoint_uses_llm_when_available(self, mock_interpret):
        mock_interpret.return_value = {
            "accion": "agendar",
            "categoria": "electricista",
            "urgencia": "alta",
            "zona": "riomar",
            "confidence": 0.93,
        }

        response = self.client.post(
            "/api/llm/interpret/",
            {"message": "Necesito un electricista urgente en Riomar"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "gemini")
        self.assertEqual(response.json()["accion"], "agendar")
        self.assertEqual(response.json()["categoria"], "electricista")
        self.assertEqual(response.json()["zona"], "riomar")

    def test_rules_fallback_detects_cancel(self):
        payload = interpret_message("Quiero cancelar mi cita de hoy")

        self.assertEqual(payload["provider"], "rules")
        self.assertEqual(payload["accion"], "cancelar")
        self.assertEqual(payload["urgencia"], "baja")

    @patch("llm.client.GeminiIntentClient.interpret")
    def test_start_command_uses_deterministic_rules_before_llm(self, mock_interpret):
        payload = interpret_message("/START")

        mock_interpret.assert_not_called()
        self.assertEqual(payload["provider"], "rules")
        self.assertEqual(payload["accion"], "saludo")

    @patch("llm.client.GeminiIntentClient.interpret")
    def test_fallback_is_used_when_llm_raises(self, mock_interpret):
        mock_interpret.side_effect = RuntimeError("Provider failed")

        payload = interpret_message("Necesito un plomero en Riomar")

        self.assertEqual(payload["provider"], "rules")
        self.assertEqual(payload["categoria"], "plomero")
