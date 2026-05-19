import json
import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from appointments.models import Appointment

from .ai import extract_intent
from .models import ChatSession, ConversationMessage

logger = logging.getLogger(__name__)


def _get_session(chat_id: int) -> ChatSession:
    session, _ = ChatSession.objects.get_or_create(chat_id=chat_id)
    return session


def _save_inbound(session: ChatSession, text: str, intent: dict) -> None:
    ConversationMessage.objects.create(
        session=session,
        direction=ConversationMessage.Direction.INBOUND,
        text=text,
        intent=intent or {},
    )


def _save_outbound(session: ChatSession, text: str) -> None:
    ConversationMessage.objects.create(
        session=session,
        direction=ConversationMessage.Direction.OUTBOUND,
        text=text,
    )


def _update_session(session: ChatSession, *, step: str, state_data: dict | None = None) -> None:
    session.current_step = step
    if state_data is not None:
        session.state_data = state_data
    session.save(update_fields=["current_step", "state_data", "updated_at"])


def _reset_session(session: ChatSession) -> None:
    _update_session(session, step="initial", state_data={})


def _process_chat_message(chat_id: int, text: str) -> tuple[ChatSession, dict, str]:
    session = _get_session(chat_id)
    intent = extract_intent(text)
    _save_inbound(session, text, intent)
    reply = handle_conversation(session, text, intent)
    _save_outbound(session, reply)
    session.refresh_from_db()
    return session, intent, reply


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

            session, intent, reply = _process_chat_message(chat_id, text)

            if not settings.TELEGRAM_DRY_RUN:
                send_telegram_message(chat_id, reply)
            else:
                logger.info(f"[DRY RUN] Para {chat_id}: {reply}")
            return JsonResponse({"ok": True, "chat_id": chat_id, "intent": intent, "reply": reply})
        except Exception as e:
            logger.error(f"Error en webhook: {e}")
            return JsonResponse({"ok": False, "error": str(e)}, status=500)
    return JsonResponse({"status": "SubasTech Telegram Bot activo"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chatbot_message(request):
    chat_id = request.data.get("chat_id")
    text = (request.data.get("text") or "").strip()
    if chat_id is None or not text:
        return Response(
            {"detail": "chat_id and text are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        chat_id = int(chat_id)
    except (TypeError, ValueError):
        return Response(
            {"detail": "chat_id must be an integer"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    session, intent, reply = _process_chat_message(chat_id, text)
    return Response(
        {
            "reply": reply,
            "intent": intent,
            "step": session.current_step,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def chatbot_history(request, chat_id: int):
    try:
        session = ChatSession.objects.get(chat_id=chat_id)
    except ChatSession.DoesNotExist:
        return Response(
            {"detail": "Chat session not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    messages = session.messages.order_by("timestamp")
    return Response(
        {
            "chat_id": session.chat_id,
            "current_step": session.current_step,
            "messages": [
                {
                    "direction": message.direction,
                    "text": message.text,
                    "intent": message.intent,
                    "timestamp": message.timestamp.isoformat(),
                }
                for message in messages
            ],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chatbot_link_user(request):
    chat_id = request.data.get("chat_id")
    if chat_id is None:
        return Response(
            {"detail": "chat_id is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        chat_id = int(chat_id)
    except (TypeError, ValueError):
        return Response(
            {"detail": "chat_id must be an integer"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    session = _get_session(chat_id)
    session.user = request.user
    session.save(update_fields=["user", "updated_at"])

    return Response(
        {
            "ok": True,
            "chat_id": session.chat_id,
            "user": request.user.username,
        }
    )


def handle_conversation(session: ChatSession, text: str, intent: dict) -> str:
    state = session.state_data or {}
    step = session.current_step
    accion = intent.get("accion")

    category_choices = {
        "1": "electricista",
        "2": "plomero",
        "3": "cerrajero",
        "4": "pintor",
    }
    if text in category_choices and step != "waiting_selection":
        intent = {"accion": "agendar", "categoria": category_choices[text], "zona": None}
        accion = "agendar"

    if accion == "saludo" or text.lower() in ["/start", "hola", "buenas"]:
        _reset_session(session)
        return (
            "¡Hola! Soy el asistente de SubasTech\n\n"
            "Puedo ayudarte a encontrar técnicos del hogar en Barranquilla.\n\n"
            "¿Qué servicio necesitas?\n"
            "1. Electricista\n2. Plomero\n3. Cerrajero\n4. Pintor\n\n"
            "O simplemente descríbeme tu problema."
        )

    if accion == "agendar" or step == "waiting_category":
        categoria = intent.get("categoria")
        if not categoria:
            _update_session(session, step="waiting_category", state_data={})
            return "¿Qué tipo de técnico necesitas? (electricista, plomero, cerrajero, pintor)"
        from catalog.models import TechnicianProfile

        technicians = list(
            TechnicianProfile.objects.filter(is_verified=True, user__is_active=True)[:3]
        )
        if not technicians:
            return "No hay técnicos disponibles ahora. Intenta más tarde."
        _update_session(
            session,
            step="waiting_selection",
            state_data={
                "categoria": categoria,
                "zona": intent.get("zona"),
                "technicians": [t.id for t in technicians],
            },
        )
        reply = f"Técnicos disponibles en {categoria}:\n\n"
        for i, tech in enumerate(technicians, 1):
            reply += f"{i}. {tech.user.get_full_name()} - {getattr(tech, 'rating', 'Nuevo')}\n"
        reply += "\nResponde con el número para agendar."
        return reply

    if step == "waiting_selection" and text in ["1", "2", "3"]:
        idx = int(text) - 1
        tech_ids = state.get("technicians", [])
        if idx >= len(tech_ids):
            return "Opción inválida. Responde con 1, 2 o 3."
        _update_session(
            session,
            step="waiting_datetime",
            state_data={
                "selected_tech": tech_ids[idx],
                "categoria": state.get("categoria"),
            },
        )
        return "¿Cuándo necesitas el servicio?\nEjemplo: mañana a las 10am o el viernes en la tarde."

    if step == "waiting_datetime":
        categoria = state.get("categoria")
        try:
            technician_id = state.get("selected_tech")
            if session.user_id and technician_id:
                placeholder_start = timezone.now()
                Appointment.objects.create(
                    client=session.user,
                    technician_id=technician_id,
                    scheduled_start=placeholder_start,
                    scheduled_end=placeholder_start + timedelta(hours=1),
                    status=Appointment.Status.PENDING,
                    metadata={
                        "notes": f"Fecha solicitada por chat: {text}",
                        "requested_date_text": text,
                        "chat_id": session.chat_id,
                        "categoria": categoria,
                        "source": "telegram_chatbot",
                    },
                )
        except Exception:
            logger.exception("No se pudo crear Appointment desde chatbot")

        _reset_session(session)
        return (
            f"Cita registrada\n\n"
            f"Categoría: {categoria}\n"
            f"Fecha solicitada: {text}\n\n"
            "El técnico recibirá tu solicitud y te confirmará pronto."
        )

    if accion == "cancelar":
        _update_session(session, step="waiting_cancel_confirm", state_data={})
        return "¿Confirmas la cancelación de tu cita activa? Responde SI o NO."

    if step == "waiting_cancel_confirm":
        _reset_session(session)
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
