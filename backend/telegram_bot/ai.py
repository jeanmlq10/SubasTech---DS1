import re
import unicodedata

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


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def extract_intent(message: str) -> dict:
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
    return {"category": category, "location": location, "urgency": urgency}
