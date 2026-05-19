import json
import re

from django.conf import settings


class GeminiIntentClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key if api_key is not None else getattr(settings, "GEMINI_API_KEY", "")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def interpret(self, message: str) -> dict:
        if not self.is_configured:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        import google.genai as genai

        prompt = f"""Extrae la intención del siguiente mensaje de un usuario que solicita servicios técnicos del hogar en Barranquilla, Colombia.
Responde SOLO con JSON válido, sin texto adicional, sin markdown:
{{
  "accion": "agendar|cancelar|reagendar|consultar|saludo|otro",
  "categoria": "electricista|plomero|cerrajero|pintor|otro|null",
  "urgencia": "alta|media|baja",
  "zona": "nombre del barrio o null",
  "confidence": 0.0
}}
Mensaje: {message}
"""
        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = (response.text or "").strip()
        if text.startswith("```"):
            text = re.sub(r"```(?:json)?", "", text).strip()
        payload = json.loads(text)
        if "confidence" not in payload:
            payload["confidence"] = 0.85
        return payload
