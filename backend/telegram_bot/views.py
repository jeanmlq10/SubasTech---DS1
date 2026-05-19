import json
import logging
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .ai import extract_intent

logger = logging.getLogger(__name__)
conversation_states = {}

@csrf_exempt
def telegram_webhook(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            message = data.get("message", {})
            chat_id = message.get("chat", {}).get("id")
            text = message.get("text", "").strip()
            if not chat_id or not text:
                return JsonResponse({"ok": True})
            intent = extract_intent(text)
            reply = handle_conversation(chat_id, text, intent)
            if not settings.TELEGRAM_DRY_RUN:
                send_telegram_message(chat_id, reply)
            else:
                logger.info(f"[DRY RUN] Para {chat_id}: {reply}")
            return JsonResponse({"ok": True, "chat_id": chat_id, "intent": intent, "reply": reply})
        except Exception as e:
            logger.error(f"Error en webhook: {e}")
            return JsonResponse({"ok": False, "error": str(e)}, status=500)
    return JsonResponse({"status": "SubasTech Telegram Bot activo"})


def handle_conversation(chat_id: int, text: str, intent: dict) -> str:
    state = conversation_states.get(chat_id, {})
    accion = intent.get("accion")

    category_choices = {
        "1": "electricista",
        "2": "plomero",
        "3": "cerrajero",
        "4": "pintor",
    }
    if text in category_choices and state.get("step") != "waiting_selection":
        intent = {"accion": "agendar", "categoria": category_choices[text], "zona": None}
        accion = "agendar"

    if accion == "saludo" or text.lower() in ["/start", "hola", "buenas"]:
        conversation_states[chat_id] = {}
        return (
            "¡Hola! Soy el asistente de SubasTech\n\n"
            "Puedo ayudarte a encontrar técnicos del hogar en Barranquilla.\n\n"
            "¿Qué servicio necesitas?\n"
            "1. Electricista\n2. Plomero\n3. Cerrajero\n4. Pintor\n\n"
            "O simplemente descríbeme tu problema."
        )

    if accion == "agendar" or state.get("step") == "waiting_category":
        categoria = intent.get("categoria")
        if not categoria:
            conversation_states[chat_id] = {"step": "waiting_category"}
            return "¿Qué tipo de técnico necesitas? (electricista, plomero, cerrajero, pintor)"
        from catalog.models import TechnicianProfile
        technicians = list(TechnicianProfile.objects.filter(
            is_verified=True, user__is_active=True
        )[:3])
        if not technicians:
            return "No hay técnicos disponibles ahora. Intenta más tarde."
        conversation_states[chat_id] = {
            "step": "waiting_selection",
            "categoria": categoria,
            "zona": intent.get("zona"),
            "technicians": [t.id for t in technicians]
        }
        reply = f"Técnicos disponibles en {categoria}:\n\n"
        for i, tech in enumerate(technicians, 1):
            reply += f"{i}. {tech.user.get_full_name()} - {getattr(tech, 'rating', 'Nuevo')}\n"
        reply += "\nResponde con el número para agendar."
        return reply

    if state.get("step") == "waiting_selection" and text in ["1", "2", "3"]:
        idx = int(text) - 1
        tech_ids = state.get("technicians", [])
        if idx >= len(tech_ids):
            return "Opción inválida. Responde con 1, 2 o 3."
        conversation_states[chat_id] = {
            "step": "waiting_datetime",
            "selected_tech": tech_ids[idx],
            "categoria": state.get("categoria")
        }
        return "¿Cuándo necesitas el servicio?\nEjemplo: mañana a las 10am o el viernes en la tarde."

    if state.get("step") == "waiting_datetime":
        conversation_states[chat_id] = {}
        return (
            f"Cita registrada\n\n"
            f"Categoría: {state.get('categoria')}\n"
            f"Fecha solicitada: {text}\n\n"
            "El técnico recibirá tu solicitud y te confirmará pronto."
        )

    if accion == "cancelar":
        conversation_states[chat_id] = {"step": "waiting_cancel_confirm"}
        return "¿Confirmas la cancelación de tu cita activa? Responde SI o NO."

    if state.get("step") == "waiting_cancel_confirm":
        conversation_states[chat_id] = {}
        if text.upper() == "SI":
            return "Cita cancelada. El técnico fue notificado."
        return "Cancelación descartada. Tu cita sigue activa."

    return (
        "No entendí tu mensaje.\n\n"
        "Puedes decirme cosas como:\n"
        "- Necesito un electricista en Riomar\n"
        "- Quiero cancelar mi cita\n"
        "- Reagendar para mañana"
    )


def send_telegram_message(chat_id: int, text: str):
    token = settings.TELEGRAM_BOT_TOKEN
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})
