from llm.services import interpret_message


def extract_intent(message: str) -> dict:
    """Backward-compatible adapter around the shared LLM service."""
    interpretation = interpret_message(message)
    return {
        "accion": interpretation["accion"],
        "categoria": interpretation["categoria"],
        "urgencia": interpretation["urgencia"],
        "zona": interpretation["zona"],
        "provider": interpretation.get("provider"),
        "confidence": interpretation.get("confidence"),
    }
