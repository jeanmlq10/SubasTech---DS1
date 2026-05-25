import json
import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)


class GeminiIntentClient:
    def __init__(self, api_key: str | None = None):
        self.api_keys = [api_key] if api_key is not None else getattr(settings, "GEMINI_API_KEYS", [])

    @property
    def is_configured(self) -> bool:
        return bool(self.api_keys)

    def interpret(self, message: str) -> dict:
        if not self.is_configured:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        import google.genai as genai

        prompt = f"""Eres el asistente conversacional de SubasTech, una 
plataforma de servicios técnicos del hogar en Barranquilla, Colombia.

Tu tarea es interpretar mensajes de usuarios colombianos en lenguaje 
natural o coloquial y extraer su intención.

Ejemplos de frases coloquiales y su categoría:
- "se me dañó el chorro" → plomero
- "el caño está botando agua" → plomero
- "no prende nada en el cuarto" → electricista
- "se fue la luz del baño" → electricista
- "la llave del agua no cierra" → plomero
- "me robaron y cambiaron la chapa" → cerrajero
- "el wc no jala" → plomero
- "hay un corto en la cocina" → electricista

Si el mensaje es ambiguo o menciona múltiples servicios, elige el 
más probable según el contexto. Si no puedes determinar la categoría 
con seguridad, usa "otro".

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
        # Retry with exponential backoff on transient errors (e.g., 503)
        import time
        max_attempts = 3
        last_exc = None
        response = None

        for key in self.api_keys:
            client = genai.Client(api_key=key)
            delay = 0.5
            key_succeeded = False
            for attempt in range(1, max_attempts + 1):
                try:
                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt,
                    )
                    key_succeeded = True
                    break
                except Exception as exc:
                    last_exc = exc
                    logger.warning("Gemini call attempt %s failed: %s", attempt, exc)
                    if attempt == max_attempts:
                        logger.warning(f"Gemini key ...{key[-4:]} agotada, probando siguiente")
                        break
                    time.sleep(delay)
                    delay *= 2

            if key_succeeded:
                break
        else:
            raise last_exc

        text = (response.text or "").strip()
        if text.startswith("```"):
            text = re.sub(r"```(?:json)?", "", text).strip()
        payload = json.loads(text)
        if "confidence" not in payload:
            payload["confidence"] = 0.85
        return payload
