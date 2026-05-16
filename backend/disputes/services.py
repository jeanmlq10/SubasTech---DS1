QUALITY_KEYWORDS = ["incompleto", "mal", "defecto", "danado", "dañado", "fallo", "garantia"]
BEHAVIOR_KEYWORDS = ["grosero", "irrespeto", "amenaza", "tarde", "no llego", "no llegó"]
PAYMENT_KEYWORDS = ["cobro", "precio", "pago", "caro", "dinero", "factura"]


def classify_dispute(description: str) -> str:
    text = description.lower()
    if any(keyword in text for keyword in BEHAVIOR_KEYWORDS):
        return "technician_behavior"
    if any(keyword in text for keyword in PAYMENT_KEYWORDS):
        return "pricing_or_payment"
    if any(keyword in text for keyword in QUALITY_KEYWORDS):
        return "service_quality"
    return "general_review"


def suggest_priority(description: str, current_priority: str) -> str:
    text = description.lower()
    if current_priority == "high" or any(keyword in text for keyword in ["urgente", "amenaza", "peligro", "daño", "dano"]):
        return "high"
    if current_priority == "low":
        return "low"
    return "normal"


def summarize_dispute(description: str) -> str:
    clean = " ".join(description.split())
    if len(clean) <= 280:
        return clean
    return clean[:277] + "..."


def build_dispute_assistant_payload(dispute) -> dict:
    description = dispute.description or ""
    return {
        "summary": dispute.ai_summary or summarize_dispute(description),
        "classification": classify_dispute(description),
        "suggested_priority": suggest_priority(description, dispute.priority),
        "recommended_review_steps": [
            "Review client description and uploaded evidence.",
            "Compare technician service scope against the complaint.",
            "Record a human decision and concise rationale.",
        ],
    }
