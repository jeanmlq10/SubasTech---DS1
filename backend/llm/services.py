import logging
import re
import unicodedata

from .client import GeminiIntentClient

logger = logging.getLogger(__name__)

CATEGORY_KEYWORDS = {
    "electricista": ["electricista", "luz", "corriente", "breaker", "enchufe", "corto", "electrico", "electrica"],
    "plomero": ["plomero", "tuberia", "agua", "fuga", "bano", "lavaplatos", "grifo", "inodoro"],
    "cerrajero": ["cerrajero", "cerradura", "llave", "puerta"],
    "pintor": ["pintor", "pintura", "pintar", "pared"],
}
URGENCY_KEYWORDS = ["urgente", "ya", "emergencia", "inmediato", "rapido", "hoy", "ahora"]
GREETING_KEYWORDS = ["hola", "buenas", "buenos dias", "/start"]
CANCEL_KEYWORDS = ["cancelar", "cancelacion", "cancelo"]
RESCHEDULE_KEYWORDS = ["reagendar", "reprogramar", "cambiar la cita", "mover la cita"]
LOCATION_PATTERNS = [
    r"\ben\s+([\w\s-]+)",
    r"\bpor\s+([\w\s-]+)",
    r"\bcerca\s+de\s+([\w\s-]+)",
]


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def interpret_message(message: str, *, client: GeminiIntentClient | None = None) -> dict:
    llm_client = client or GeminiIntentClient()
    try:
        payload = llm_client.interpret(message)
        return _normalize_result(payload, provider="gemini")
    except Exception as exc:
        logger.warning("LLM provider failed, using rules fallback: %s", exc)
        return rules_fallback(message)


def rules_fallback(message: str) -> dict:
    text_norm = normalize_text(message)
    category = None
    for slug, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in text_norm for keyword in keywords):
            category = slug
            break

    location = None
    for pattern in LOCATION_PATTERNS:
        match = re.search(pattern, text_norm)
        if match:
            location = match.group(1).split(".", 1)[0].split(",", 1)[0].strip()
            break

    urgency = "alta" if any(keyword in text_norm for keyword in URGENCY_KEYWORDS) else "baja"
    if any(keyword in text_norm for keyword in GREETING_KEYWORDS):
        accion = "saludo"
    elif any(keyword in text_norm for keyword in CANCEL_KEYWORDS):
        accion = "cancelar"
    elif any(keyword in text_norm for keyword in RESCHEDULE_KEYWORDS):
        accion = "reagendar"
    else:
        accion = "agendar" if category else "otro"

    return {
        "accion": accion,
        "categoria": category or None,
        "urgencia": urgency,
        "zona": location or None,
        "confidence": 0.45,
        "provider": "rules",
    }


def _normalize_result(payload: dict, *, provider: str) -> dict:
    return {
        "accion": _coerce_action(payload.get("accion")),
        "categoria": _coerce_category(payload.get("categoria")),
        "urgencia": _coerce_urgency(payload.get("urgencia")),
        "zona": _coerce_optional_text(payload.get("zona")),
        "confidence": _coerce_confidence(payload.get("confidence")),
        "provider": provider,
    }


def _coerce_action(value) -> str:
    allowed = {"agendar", "cancelar", "reagendar", "consultar", "saludo", "otro"}
    normalized = str(value or "").strip().lower()
    return normalized if normalized in allowed else "otro"


def _coerce_category(value):
    normalized = _coerce_optional_text(value)
    return normalized


def _coerce_urgency(value) -> str:
    normalized = str(value or "").strip().lower()
    mapping = {
        "alta": "alta",
        "high": "alta",
        "media": "media",
        "normal": "media",
        "baja": "baja",
        "low": "baja",
    }
    return mapping.get(normalized, "media")


def _coerce_optional_text(value):
    if value in (None, "", "null"):
        return None
    return str(value).strip().lower()


def _coerce_confidence(value) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.75
    return max(0.0, min(confidence, 1.0))
