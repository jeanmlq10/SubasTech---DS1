import json
import logging
import re
import unicodedata

import google.generativeai as genai
from django.conf import settings

logger = logging.getLogger(__name__)

CATEGORY_KEYWORDS = {
    "electrician": ["electricista", "luz", "corriente", "breaker", "enchufe", "corto", "electrico", "electrica"],
    "plumber": ["plomero", "tuberia", "agua", "fuga", "bano", "lavaplatos", "grifo", "inodoro"],
    "appliance-repair": ["nevera", "lavadora", "aire", "estufa", "electrodomestico", "refrigerador"],
    "locksmith": ["cerrajero", "cerradura", "llave", "puerta"],
    "hvac-technician": ["aire acondicionado", "ac", "minisplit", "hvac", "climatizacion"],
    "general-handyman": ["arreglo", "mantenimiento", "instalar", "montar", "reparacion general"],
}
URGENCY_KEYWORDS = ["urgente", "ya", "emergencia", "inmediato", "rapido", "hoy", "ahora"]
LOCATION_PATTERNS = [
    r"\ben\s+([\w\s-]+)",
    r"\bpor\s+([\w\s-]+)",
    r"\bcerca\s+de\s+([\w\s-]+)",
]


genai.configure(api_key=settings.GEMINI_API_KEY)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _clean_response_text(text: str) -> str:
    if not isinstance(text, str):
        return str(text)
    return text.strip()


def extract_intent(message: str) -> dict:
    prompt = f"""Extrae la intención del siguiente mensaje de un usuario que solicita servicios técnicos del hogar en Barranquilla, Colombia.
Responde SOLO con JSON válido, sin texto adicional:
{{
  "accion": "agendar|cancelar|reagendar|consultar|saludo|otro",
  "categoria": "electricista|plomero|cerrajero|pintor|otro|null",
  "urgencia": "alta|media|baja",
  "zona": "nombre del barrio o null"
}}
Mensaje: {message}
"""
    try:
        response = genai.generate_text(
            model="gemini-1.5-flash",
            prompt=prompt,
            max_output_tokens=300,
            temperature=0.2,
        )
        text = getattr(response, "text", None)
        if text is None:
            text = getattr(response, "content", None)
        text = _clean_response_text(text)
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing Gemini response JSON: {e}")
    except Exception as e:
        logger.error(f"Error extracting intent with Gemini: {e}")

    # Fallback a parsing por reglas si la respuesta no es válida
    text = normalize_text(message)
    category = ""
    for slug, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            category = slug
            break

    location = ""
    for pattern in LOCATION_PATTERNS:
        match = re.search(pattern, text)
        if match:
            location = match.group(1).split(".", 1)[0].split(",", 1)[0].strip()
            break

    urgency = "high" if any(keyword in text for keyword in URGENCY_KEYWORDS) else "normal"
    return {"accion": "otro", "categoria": category or None, "urgencia": urgency, "zona": location or None}
