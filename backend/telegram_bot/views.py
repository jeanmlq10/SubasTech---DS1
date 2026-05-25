import json
import logging
import re
import threading
import unicodedata
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import JsonResponse
from django.utils.text import slugify
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from appointments.models import Appointment
from appointments.services import (
    cancel_appointment,
    create_appointment,
    get_available_slots,
    reschedule_appointment,
)
from auctions.models import Auction, Bid
from auctions.services import award_auction_bid
from audit.models import AuditEvent
from audit.services import log_audit_event
from catalog.models import Category, Service, TechnicianProfile, Zone
from leads.models import ServiceLead
from notifications.models import Notification
from notifications.services import build_telegram_message_payload, create_notification
from recommendations.services import RecommendationRequest, recommend_services

from .ai import extract_intent
from .client import TelegramBotClient
from .models import ChatSession, ConversationMessage

logger = logging.getLogger(__name__)
User = get_user_model()

CHATBOT_SOURCE = "telegram_chatbot"
DEFAULT_SLOT_DAYS = 7
DEFAULT_SLOT_COUNT = 5
DEFAULT_CANCELLATION_REASON = "Cancelled from Telegram chat"
DEFAULT_RESCHEDULE_REASON = "Rescheduled from Telegram chat"
CONTACT_FIELD_SEQUENCE = ("full_name", "phone_number", "email", "address")

CATEGORY_CHOICES = {
    "1": "electrician",
    "2": "plumber",
    "3": "locksmith",
    "4": "general-handyman",
}
CATEGORY_DISPLAY_NAMES = {
    "electrician": "Electricista",
    "plumber": "Plomero",
    "locksmith": "Cerrajero",
    "general-handyman": "Mantenimiento general",
}
CATEGORY_KEYWORDS = {
    "electrician": ("electricista", "electricidad", "luz", "corriente"),
    "plumber": ("plomero", "agua", "tuberia", "fuga"),
    "locksmith": ("cerrajero", "llave", "cerradura", "puerta"),
    "general-handyman": ("mantenimiento", "reparacion", "arreglo"),
}
ZONE_DISPLAY_NAMES = {
    "barranquilla-riomar": "Riomar",
    "barranquilla-alto-prado": "Alto Prado",
    "barranquilla-villa-santos": "Villa Santos",
}
ZONE_KEYWORDS = {
    "barranquilla-riomar": ("riomar",),
    "barranquilla-alto-prado": ("alto prado", "prado"),
    "barranquilla-villa-santos": ("villa santos", "villa"),
}
YES_CHOICES = {"si", "s", "confirmo", "yes"}
NO_CHOICES = {"no", "n"}
AUCTION_CHOICES = {"0", "ofertas", "oferta", "subasta", "recibir ofertas", "quiero ofertas"}
RESET_CHOICES = {"inicio", "menu", "menú", "volver", "reiniciar", "empezar", "cancelar flujo"}
RESET_HINT = "Escribe INICIO para volver al principio."
CONTACT_PROMPTS = {
    "full_name": "Antes de confirmar tu cita, necesito algunos datos 📋\n¿Cuál es tu nombre completo?",
    "phone_number": "Gracias. Ahora compárteme tu número de celular.",
    "email": "Perfecto. Ahora digita tu correo electrónico",
    "address": "Por último, escríbeme la dirección donde será el servicio.",
}
CONTACT_STEP_BY_FIELD = {
    "full_name": "waiting_contact_name",
    "phone_number": "waiting_contact_phone",
    "email": "waiting_contact_email",
    "address": "waiting_contact_address",
}


def _get_session(chat_id: int) -> ChatSession:
    session, _created = ChatSession.objects.get_or_create(chat_id=chat_id)
    if session.user_id is None:
        linked_user = User.objects.filter(telegram_chat_id=str(chat_id)).first()
        if linked_user is not None:
            session.user = linked_user
            session.save(update_fields=["user", "updated_at"])
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


def _handle_rating_submission(session: ChatSession, text: str, state: dict) -> str:
    """Process a rating reply in the form `score [comment]` and persist it.

    The session.state_data is expected to contain `awaiting_rating_for` with
    the appointment id.
    """
    cleaned = (text or "").strip()
    match = re.fullmatch(r"([0-5])(?:\s+(.+))?", cleaned)
    if not match:
        return (
            "Por favor responde con un numero entero entre 0 y 5 seguido de un comentario opcional.\n"
            "Por ejemplo: 4 Muy buen servicio."
        )

    score = int(match.group(1))
    comment = (match.group(2) or "").strip()

    appointment_id = state.get("awaiting_rating_for")
    if not appointment_id:
        _reset_session(session)
        return "No encuentro la solicitud asociada a esta calificacion. Intenta de nuevo desde el dashboard o solicita el enlace." 

    if session.user is None:
        return (
            "Para registrar la calificación debes vincular tu cuenta. "
            "Visita el dashboard o envia /link desde la app para asociar tu usuario."
        )

    # Create the rating record
    try:
        from reputation.models import Rating
        from reputation.services import refresh_technician_reputation

        appointment = Appointment.objects.select_related("technician", "service", "lead").filter(pk=appointment_id).first()
        if not appointment:
            _reset_session(session)
            return "No se encontro la cita. Verifica e intenta nuevamente."

        Rating.objects.create(
            author=session.user,
            technician=appointment.technician,
            service=appointment.service,
            lead=appointment.lead,
            target_role=Rating.TargetRole.TECHNICIAN,
            score=score,
            comment=comment,
        )

        # Refresh aggregated reputation metrics for the technician
        try:
            refresh_technician_reputation(appointment.technician)
        except Exception:
            logger.exception("Failed to refresh reputation for technician %s", appointment.technician_id)

        _reset_session(session)
        if comment:
            return f"Gracias. Tu calificación de {score} y tu comentario fueron registrados."
        return f"Gracias. Tu calificación de {score} fue registrada."
    except Exception as exc:
        logger.exception("Error saving rating from telegram: %s", exc)
        return "No pude registrar tu calificacion ahora. Intenta nuevamente mas tarde."


def _build_welcome_message() -> str:
    return (
        "¡Hola! 👋 Soy el asistente de SubasTech.\n\n"
        "Estoy aquí para ayudarte a encontrar técnicos del hogar de confianza "
        "en Barranquilla y agendar tu cita fácilmente.\n\n"
        "¿Qué necesitas hoy?\n"
        "🔌 1. Electricista\n"
        "🚿 2. Plomero\n"
        "🔐 3. Cerrajero\n"
        "🔧 4. Mantenimiento general\n\n"
        "También puedes describirme tu problema directamente."
    )


def _with_navigation_hint(message: str) -> str:
    if RESET_HINT in message:
        return message
    return f"{message}\n\n{RESET_HINT}"


def _process_chat_message(
    chat_id: int,
    text: str,
    *,
    user=None,
    telegram_message_id: int | None = None,
) -> tuple[ChatSession, dict, str, bool]:
    with transaction.atomic():
        session = _get_session(chat_id)
        session = ChatSession.objects.select_for_update().get(pk=session.pk)

        if user is not None and session.user_id != user.id:
            session.user = user
            session.save(update_fields=["user", "updated_at"])

        if _is_duplicate_telegram_message(session, telegram_message_id):
            return session, {}, "", False

        intent = extract_intent(text)
        _save_inbound(session, text, intent)
        reply = _with_navigation_hint(handle_conversation(session, text, intent))
        _save_outbound(session, reply)
        if telegram_message_id is not None:
            session.last_telegram_message_id = telegram_message_id
            session.save(update_fields=["last_telegram_message_id", "updated_at"])
        log_audit_event(
            event_type=AuditEvent.EventType.MESSAGE_SENT,
            actor=session.user,
            channel="telegram",
            source="telegram_bot.chat",
            entity_type="chat_session",
            entity_id=str(session.chat_id),
            status="success",
            message="Telegram chatbot reply generated",
            metadata={"step": session.current_step, "reply": reply},
        )
        session.refresh_from_db()
        return session, intent, reply, True


def _is_duplicate_telegram_message(session: ChatSession, telegram_message_id: int | None) -> bool:
    if telegram_message_id is None:
        return False
    last_message_id = session.last_telegram_message_id
    return last_message_id is not None and telegram_message_id <= last_message_id


@csrf_exempt
def telegram_webhook(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            message = data.get("message", {})
            chat_id = message.get("chat", {}).get("id")
            message_id = message.get("message_id")
            text = (message.get("text") or "").strip()
            if not chat_id or not text:
                return JsonResponse({"ok": True})

            session = _get_session(int(chat_id))
            log_audit_event(
                event_type=AuditEvent.EventType.WEBHOOK_RECEIVED,
                actor=session.user,
                channel="telegram",
                source="telegram_bot.webhook",
                entity_type="chat_session",
                entity_id=str(chat_id),
                status="success",
                message="Telegram webhook received",
                metadata={"text": text},
            )
            session, intent, reply, processed = _process_chat_message(
                int(chat_id),
                text,
                telegram_message_id=message_id,
            )
            if not processed:
                return JsonResponse({"ok": True, "chat_id": chat_id, "ignored": "duplicate_message"})

            if not settings.TELEGRAM_DRY_RUN:
                send_telegram_message(chat_id, reply)
            else:
                logger.info("[DRY RUN] Para %s: %s", chat_id, reply)
            return JsonResponse({"ok": True, "chat_id": chat_id, "intent": intent, "reply": reply})
        except Exception as exc:
            logger.error("Error en webhook: %s", exc)
            log_audit_event(
                event_type=AuditEvent.EventType.INTEGRATION_ERROR,
                channel="telegram",
                source="telegram_bot.webhook",
                entity_type="chat_session",
                status="error",
                message="Telegram webhook processing failed",
                metadata={"error": str(exc)},
            )
            return JsonResponse({"ok": False, "error": str(exc)}, status=500)
    return JsonResponse({"status": "SubasTech Telegram Bot activo"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chatbot_message(request):
    chat_id = request.data.get("chat_id")
    text = (request.data.get("text") or "").strip()
    if chat_id is None or not text:
        return Response({"detail": "chat_id and text are required"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        chat_id = int(chat_id)
    except (TypeError, ValueError):
        return Response({"detail": "chat_id must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

    session, intent, reply, _processed = _process_chat_message(chat_id, text, user=request.user)
    return Response({"reply": reply, "intent": intent, "step": session.current_step})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def chatbot_history(request, chat_id: int):
    try:
        session = ChatSession.objects.get(chat_id=chat_id)
    except ChatSession.DoesNotExist:
        return Response({"detail": "Chat session not found"}, status=status.HTTP_404_NOT_FOUND)

    _ensure_session_access(request.user, session)
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
        return Response({"detail": "chat_id is required"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        chat_id = int(chat_id)
    except (TypeError, ValueError):
        return Response({"detail": "chat_id must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

    session = _get_session(chat_id)
    previous_user = session.user
    if previous_user is not None and previous_user.id != request.user.id:
        Auction.objects.filter(client=previous_user).update(client=request.user)
        Appointment.objects.filter(client=previous_user).update(client=request.user)
        ServiceLead.objects.filter(client_user=previous_user).update(client_user=request.user)
        if previous_user.telegram_chat_id == str(chat_id):
            previous_user.telegram_chat_id = None
            previous_user.save(update_fields=["telegram_chat_id"])

    User.objects.filter(telegram_chat_id=str(chat_id)).exclude(pk=request.user.pk).update(telegram_chat_id=None)
    request.user.telegram_chat_id = str(chat_id)
    request.user.save(update_fields=["telegram_chat_id"])
    session.user = request.user
    session.save(update_fields=["user", "updated_at"])
    return Response({"ok": True, "chat_id": session.chat_id, "user": request.user.username})


def handle_conversation(session: ChatSession, text: str, intent: dict) -> str:
    state = dict(session.state_data or {})
    step = session.current_step
    cleaned_text = (text or "").strip()
    lowered = cleaned_text.lower()
    accion = (intent.get("accion") or "").lower()

    if cleaned_text in CATEGORY_CHOICES and step in {"initial", "waiting_category"}:
        intent = {"accion": "agendar", "categoria": CATEGORY_CHOICES[cleaned_text], "zona": None}
        accion = "agendar"

    if lowered in RESET_CHOICES:
        _reset_session(session)
        return _build_welcome_message()

    if step == "waiting_rating":
        return _handle_rating_submission(session, cleaned_text, state)

    if _is_bid_acceptance(cleaned_text):
        return _handle_bid_acceptance(session, cleaned_text)

    if accion == "saludo" or lowered in {"/start", "hola", "buenas", "buenos dias"}:
        _reset_session(session)
        return _build_welcome_message()

    if accion == "cancelar" and step not in {"waiting_cancel_confirm", "waiting_cancel_target"}:
        return _start_cancel_flow(session)

    if step == "waiting_zone":
        return _handle_zone_selection(session, cleaned_text, state)
    if step == "waiting_technician_selection":
        return _handle_technician_selection(session, cleaned_text, state)
    if step == "waiting_auction_name":
        return _handle_auction_name(session, cleaned_text, state)
    if step == "waiting_auction_phone":
        return _handle_auction_phone(session, cleaned_text, state)
    if step == "waiting_auction_address":
        return _handle_auction_address(session, cleaned_text, state)
    if step == "waiting_slot_selection":
        return _handle_slot_booking(session, cleaned_text, state)
    if step in {
        "waiting_contact_name",
        "waiting_contact_phone",
        "waiting_contact_email",
        "waiting_contact_address",
    }:
        return _handle_contact_collection(session, cleaned_text, state, step)
    if step == "waiting_cancel_target":
        return _handle_cancel_target(session, cleaned_text, state)
    if step == "waiting_cancel_confirm":
        return _handle_cancel_confirmation(session, lowered, state)
    if step == "waiting_reschedule_slot_selection":
        return _handle_reschedule_slot_selection(session, cleaned_text, state)

    if accion == "reagendar":
        return _start_reschedule_flow(session)
    if accion == "agendar" or step == "waiting_category":
        return _start_booking_flow(session, cleaned_text, intent)

    return (
        "No entendí bien lo que necesitas 🤔\n"
        "Puedes decirme por ejemplo:\n"
        "- Necesito un electricista en Riomar\n"
        "- Quiero cancelar mi cita\n"
        "- Cancelar mi subasta\n"
        "- Reagendar mi cita"
    )


def _start_booking_flow(session: ChatSession, text: str, intent: dict) -> str:
    category = _extract_category(intent, text)
    if not category:
        _update_session(session, step="waiting_category", state_data={})
        return (
            "Que tipo de tecnico necesitas?\n"
            "Puedes responder: electricista, plomero, cerrajero o mantenimiento."
        )

    location = _extract_zone(intent, text)
    if not location:
        _update_session(
            session,
            step="waiting_zone",
            state_data={"request_text": text, "categoria": category},
        )
        return (
            f"En que zona necesitas el servicio de {CATEGORY_DISPLAY_NAMES.get(category, category)}?\n"
            "Escribeme el barrio, por ejemplo: Riomar, Boston, El Prado, Villa Santos o La Pradera."
        )

    recommendations = _recommend_technicians(category, location)
    if not recommendations:
        _reset_session(session)
        return "Aun no encontre tecnicos disponibles para esa solicitud. Intenta con otra categoria o zona."

    _update_session(
        session,
        step="waiting_technician_selection",
        state_data={
            "request_text": _meaningful_request_text(text, category, location),
            "categoria": category,
            "zona": location,
            "recommendations": recommendations,
        },
    )
    return _build_recommendation_reply(category, location, recommendations)


def _handle_zone_selection(session: ChatSession, text: str, state: dict) -> str:
    selected_zone = _resolve_zone_text(text)

    if not selected_zone:
        return (
            "No encontre ese barrio en nuestra cobertura.\n"
            "Escribelo de nuevo sin direccion completa, por ejemplo: Riomar, Boston, El Prado, Villa Santos o La Pradera."
        )

    category = state.get("categoria")
    recommendations = _recommend_technicians(category, selected_zone)
    if not recommendations:
        _reset_session(session)
        zone_name = ZONE_DISPLAY_NAMES.get(selected_zone, selected_zone)
        service_name = CATEGORY_DISPLAY_NAMES.get(category, category)
        return f"No hay tecnicos disponibles en {zone_name} para {service_name}. Intenta con otra zona o categoria."

    _update_session(
        session,
        step="waiting_technician_selection",
        state_data={
            "request_text": _meaningful_request_text(state.get("request_text", ""), category, selected_zone),
            "categoria": category,
            "zona": selected_zone,
            "recommendations": recommendations,
        },
    )
    return _build_recommendation_reply(category, selected_zone, recommendations)


def _handle_technician_selection(session: ChatSession, text: str, state: dict) -> str:
    recommendations = state.get("recommendations") or []
    if text.strip().lower() in AUCTION_CHOICES:
        return _start_auction_flow(session, state)

    selected_index = _parse_numeric_choice(text, len(recommendations))
    if selected_index is None:
        return f"Responde con un numero entre 1 y {len(recommendations)} para escoger tecnico, o 0 para recibir ofertas."

    selected = recommendations[selected_index]
    technician = TechnicianProfile.objects.filter(pk=selected["technician_id"]).first()

    service = Service.objects.filter(pk=selected["service_id"]).first()
    if technician is None or service is None:
        _reset_session(session)
        return "No pude recuperar la informacion del tecnico seleccionado. Intenta de nuevo."

    slots = get_available_slots(
        technician=technician,
        service=service,
        zone=_find_zone(state.get("zona")),
        days=DEFAULT_SLOT_DAYS,
    )[:DEFAULT_SLOT_COUNT]
    if not slots:
        return "Ese tecnico no tiene horarios disponibles en los proximos dias. Puedes elegir otro tecnico de la lista."

    _update_session(
        session,
        step="waiting_slot_selection",
        state_data={
            "request_text": state.get("request_text", ""),
            "categoria": state.get("categoria"),
            "zona": state.get("zona"),
            "selected_service_id": service.id,
            "selected_technician_id": technician.id,
            "selected_technician_name": selected["technician_name"],
            "slots": [_serialize_slot(slot) for slot in slots],
        },
    )
    return _build_slots_reply(selected["technician_name"], [_serialize_slot(slot) for slot in slots])


def _handle_slot_booking(session: ChatSession, text: str, state: dict) -> str:
    slots = state.get("slots") or []
    selected_index = _parse_numeric_choice(text, len(slots))
    if selected_index is None:
        return f"Responde con un numero entre 1 y {len(slots)} para escoger horario."

    booking_state = dict(state)
    booking_state["selected_slot"] = slots[selected_index]
    next_field = _next_missing_contact_field(session.user, booking_state)
    if next_field is not None:
        _update_session(
            session,
            step=CONTACT_STEP_BY_FIELD[next_field],
            state_data=booking_state,
        )
        return CONTACT_PROMPTS[next_field]

    return _finalize_booking(session, booking_state)


def _handle_contact_collection(session: ChatSession, text: str, state: dict, step: str) -> str:
    field_name = {
        "waiting_contact_name": "full_name",
        "waiting_contact_phone": "phone_number",
        "waiting_contact_email": "email",
        "waiting_contact_address": "address",
    }[step]
    try:
        cleaned_value = _validate_contact_field(field_name, text)
    except ValueError as exc:
        return str(exc)

    updated_state = dict(state)
    client_draft = dict(updated_state.get("client_draft") or {})
    client_draft[field_name] = cleaned_value
    updated_state["client_draft"] = client_draft

    next_field = _next_missing_contact_field(session.user, updated_state)
    if next_field is not None:
        _update_session(session, step=CONTACT_STEP_BY_FIELD[next_field], state_data=updated_state)
        return CONTACT_PROMPTS[next_field]

    return _finalize_booking(session, updated_state)


def _start_auction_flow(session: ChatSession, state: dict) -> str:
    user = session.user
    user_name = (getattr(user, "first_name", "") or "").strip() if user else ""
    if not user_name:
        _update_session(session, step="waiting_auction_name", state_data=state)
        return "Antes de crear la subasta, necesito tu nombre completo."
    user_phone = (getattr(user, "phone_number", "") or "").strip() if user else ""
    if not user_phone:
        _update_session(session, step="waiting_auction_phone", state_data=state)
        return "Cual es tu numero de celular?"
    user_address = (getattr(user, "address", "") or "").strip() if user else ""
    if not user_address:
        _update_session(session, step="waiting_auction_address", state_data=state)
        return (
            "Para que el tecnico pueda llegar, necesito la direccion del servicio.\n"
            "Escribeme la calle, barrio o una referencia clara, por ejemplo: Cra 50 #80-45 Riomar."
        )
    updated_state = dict(state)
    updated_state["auction_address"] = user_address
    return _create_auction_from_chat(session, updated_state)


def _handle_auction_name(session: ChatSession, text: str, state: dict) -> str:
    if len(text.strip().split()) < 2:
        return "Necesito tu nombre y apellido para continuar."
    if session.user:
        first_name, last_name = text.strip().split(" ", 1)
        session.user.first_name = first_name
        session.user.last_name = last_name
        session.user.save(update_fields=["first_name", "last_name"])
    user_phone = (getattr(session.user, "phone_number", "") or "").strip() if session.user else ""
    if not user_phone:
        _update_session(session, step="waiting_auction_phone", state_data=state)
        return "Cual es tu numero de celular?"
    user_address = (getattr(session.user, "address", "") or "").strip() if session.user else ""
    if not user_address:
        _update_session(session, step="waiting_auction_address", state_data=state)
        return (
            "Para que el tecnico pueda llegar, necesito la direccion del servicio.\n"
            "Escribeme la calle, barrio o una referencia clara, por ejemplo: Cra 50 #80-45 Riomar."
        )
    updated_state = dict(state)
    updated_state["auction_address"] = user_address
    return _create_auction_from_chat(session, updated_state)


def _handle_auction_phone(session: ChatSession, text: str, state: dict) -> str:
    digits = re.sub(r"\D", "", text.strip())
    if len(digits) < 10 or len(digits) > 15:
        return "Comparte un numero de celular valido, por ejemplo 3001234567 o 573001234567."
    if session.user:
        session.user.phone_number = digits
        session.user.save(update_fields=["phone_number"])
    user_address = (getattr(session.user, "address", "") or "").strip() if session.user else ""
    if not user_address:
        _update_session(session, step="waiting_auction_address", state_data=state)
        return (
            "Para que el tecnico pueda llegar, necesito la direccion del servicio.\n"
            "Escribeme la calle, barrio o una referencia clara, por ejemplo: Cra 50 #80-45 Riomar."
        )
    updated_state = dict(state)
    updated_state["auction_address"] = user_address
    return _create_auction_from_chat(session, updated_state)


def _handle_auction_address(session: ChatSession, text: str, state: dict) -> str:
    if len(text.strip()) < 8:
        return "Comparte una direccion mas completa, por ejemplo: Cra 50 #80-45 Riomar o Calle 84 frente al parque."
    updated_state = dict(state)
    updated_state["auction_address"] = text.strip()
    if session.user:
        session.user.address = text.strip()
        session.user.save(update_fields=["address"])
    return _create_auction_from_chat(session, updated_state)


def _expire_telegram_auction_after_timeout(auction_id: int, chat_id: int) -> None:
    try:
        auction = Auction.objects.get(pk=auction_id)
    except Auction.DoesNotExist:
        return
    if auction.status != Auction.Status.OPEN:
        return
    had_bids = auction.bids.exists()
    auction.status = Auction.Status.EXPIRED
    auction.save(update_fields=["status", "updated_at"])
    if not had_bids:
        send_telegram_message(
            chat_id,
            (
                f"⏰ Tu subasta #{auction_id} cerró sin ofertas esta vez.\n"
                "Escribe INICIO si quieres intentarlo de nuevo."
            ),
        )


def _create_auction_from_chat(session: ChatSession, state: dict) -> str:
    from django.utils.timezone import now

    if session.user_id is None:
        _ensure_client_user(session, state)

    if getattr(session.user, "auction_blocked", False):
        _reset_session(session)
        return "Tu cuenta tiene restringida la creación de subastas por disputas perdidas. Contacta con soporte para resolverlo."

    category = _resolve_auction_category(state)
    if category is None:
        _reset_session(session)
        return "No pude crear la subasta porque no identifique la categoria. Intenta de nuevo desde el inicio."

    zone = _find_zone(state.get("zona"))
    expires_at = now() + timedelta(minutes=settings.AUCTION_DURATION_MINUTES)
    with transaction.atomic():
        previous_auctions = Auction.objects.filter(
            source=Auction.Source.TELEGRAM,
            status=Auction.Status.OPEN,
            metadata__chat_id=session.chat_id,
        )
        Bid.objects.filter(auction__in=previous_auctions, status=Bid.Status.PENDING).update(status=Bid.Status.REJECTED)
        previous_auctions.update(status=Auction.Status.CANCELLED)
        auction = Auction.objects.create(
            client=session.user,
            category=category,
            zone=zone,
            title=f"Solicitud de {CATEGORY_DISPLAY_NAMES.get(state.get('categoria'), category.name)}",
            description=state.get("request_text") or f"Solicitud desde Telegram para {category.name}",
            location=ZONE_DISPLAY_NAMES.get(state.get("zona"), state.get("zona") or ""),
            urgency="normal",
            source=Auction.Source.TELEGRAM,
            expires_at=expires_at,
            metadata={
                "source": CHATBOT_SOURCE,
                "chat_id": session.chat_id,
                "category": state.get("categoria"),
                "zone": state.get("zona"),
                "client_address": state.get("auction_address") or (getattr(session.user, "address", "") if session.user else ""),
            },
        )
    threading.Timer(
        settings.AUCTION_DURATION_MINUTES * 60,
        _expire_telegram_auction_after_timeout,
        args=[auction.id, session.chat_id],
    ).start()
    log_audit_event(
        event_type=AuditEvent.EventType.LEAD_CREATED,
        actor=session.user,
        channel="telegram",
        source="telegram_bot.auction",
        entity_type="auction",
        entity_id=str(auction.id),
        status="success",
        message="Auction created from Telegram chatbot",
        metadata={"category_id": category.id, "zone_id": zone.id if zone else None},
    )
    _reset_session(session)
    duration_minutes = settings.AUCTION_DURATION_MINUTES
    return (
        "¡Tu subasta está activa! 🔨\n"
        "Ya notifiqué a los técnicos disponibles para que te envíen sus ofertas.\n\n"
        f"Solicitud: {auction.title}\n"
        f"Zona: {auction.location or 'Sin zona'}\n"
        f"Numero de subasta: {auction.id}\n\n"
        f"⏱ Tu subasta estará activa por {duration_minutes} minutos.\n"
        "Te notificaré cada oferta que llegue por aquí.\n\n"
        "Para aceptar, responde ACEPTO: Nombre Tecnico cuando recibas la oferta."
    )


def _is_bid_acceptance(text: str) -> bool:
    return bool(re.match(r"^\s*acepto\s*:\s*.+", text or "", flags=re.IGNORECASE))


def _handle_bid_acceptance(session: ChatSession, text: str) -> str:
    match = re.match(r"^\s*acepto\s*:\s*(?P<name>.+?)\s*$", text, flags=re.IGNORECASE)
    technician_text = match.group("name") if match else ""
    auction = (
        Auction.objects.select_related("client", "category", "zone")
        .filter(
            source=Auction.Source.TELEGRAM,
            status=Auction.Status.OPEN,
            metadata__chat_id=session.chat_id,
        )
        .order_by("-created_at")
        .first()
    )
    if auction is None:
        _reset_session(session)
        return "No encontre una subasta abierta para aceptar. Crea una nueva solicitud si aun necesitas el servicio."

    pending_bids = list(
        Bid.objects.select_related("technician__user", "service", "auction")
        .filter(auction=auction, status=Bid.Status.PENDING)
        .order_by("created_at")
    )
    matching_bids = [bid for bid in pending_bids if _technician_name_matches(bid, technician_text)]
    if not matching_bids:
        available_names = ", ".join(_bid_technician_name(bid) for bid in pending_bids) or "sin ofertas pendientes"
        return (
            f"No encontre una oferta pendiente de '{technician_text}' para la subasta #{auction.id}.\n"
            f"Ofertas disponibles: {available_names}.\n\n"
            "Responde con el formato ACEPTO: Nombre Tecnico."
        )
    if len(matching_bids) > 1:
        return "Encontre mas de un tecnico con ese nombre. Responde ACEPTO: Nombre y Apellido como aparece en la oferta."

    bid = matching_bids[0]
    if bid.available_from is None:
        return "Esa oferta no tiene horario propuesto. Pidele al tecnico enviar una oferta con fecha y hora."

    try:
        _lead, appointment = award_auction_bid(
            auction=auction,
            bid=bid,
            actor=auction.client,
            source="telegram.auction_acceptance",
        )
    except DjangoValidationError as exc:
        logger.warning("Telegram auction acceptance failed: %s", exc)
        return "No pude aceptar esa oferta porque el horario ya no esta disponible. Espera otra oferta o crea una nueva subasta."

    _reset_session(session)
    return (
        "¡Perfecto, oferta aceptada! 🎉\n"
        "Tu cita quedó confirmada con estos datos:\n\n"
        f"Tecnico: {_bid_technician_name(bid)}\n"
        f"Servicio: {bid.service.title if bid.service else 'Servicio tecnico'}\n"
        f"Horario: {_format_local_datetime(appointment.scheduled_start)} - {_format_local_time(appointment.scheduled_end)}\n"
        f"Direccion/zona: {auction.location or (auction.zone.name if auction.zone else 'Sin zona')}\n"
        f"Numero de cita: {appointment.id}"
    )


def _technician_name_matches(bid: Bid, raw_name: str) -> bool:
    requested = _normalize_match_text(raw_name)
    full_name = _normalize_match_text(_bid_technician_name(bid))
    username = _normalize_match_text(bid.technician.user.username)
    return requested in {full_name, username} or requested in full_name


def _bid_technician_name(bid: Bid) -> str:
    return bid.technician.user.get_full_name() or bid.technician.user.username


def _meaningful_request_text(text: str, category: str | None, zone: str | None) -> str:
    """Return a human-readable request description.

    When the user selected via number or typed only a short keyword, the raw
    text carries no useful context. In that case we build a description from
    the resolved category and zone instead.
    """
    cleaned = (text or "").strip()
    is_trivial = not cleaned or cleaned.isdigit() or (len(cleaned.split()) == 1 and len(cleaned) <= 20)
    if is_trivial:
        category_name = CATEGORY_DISPLAY_NAMES.get(category or "", category or "Servicio tecnico")
        zone_name = ZONE_DISPLAY_NAMES.get(zone or "", zone or "")
        return f"Solicitud de {category_name}" + (f" en {zone_name}" if zone_name else "")
    return cleaned


def _normalize_match_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").lower())
    return " ".join("".join(ch for ch in normalized if not unicodedata.combining(ch)).split())


def _format_local_datetime(value: datetime) -> str:
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")


def _format_local_time(value: datetime) -> str:
    return timezone.localtime(value).strftime("%H:%M")


def _get_open_auction_for_session(session: ChatSession) -> "Auction | None":
    return (
        Auction.objects.filter(
            source=Auction.Source.TELEGRAM,
            status=Auction.Status.OPEN,
            metadata__chat_id=session.chat_id,
        )
        .order_by("-created_at")
        .first()
    )


def _start_cancel_flow(session: ChatSession) -> str:
    appointment = _get_upcoming_client_appointment(session)
    auction = _get_open_auction_for_session(session)

    if appointment and auction:
        _update_session(
            session,
            step="waiting_cancel_target",
            state_data={"appointment_id": appointment.id, "auction_id": auction.id},
        )
        return (
            "Tienes dos cosas activas. Que quieres cancelar?\n\n"
            f"1. Cita: {_format_appointment_summary(appointment)}\n"
            f"2. Subasta #{auction.id}: {auction.title}\n\n"
            "Responde 1 para la cita o 2 para la subasta."
        )
    if appointment:
        _update_session(
            session,
            step="waiting_cancel_confirm",
            state_data={"appointment_id": appointment.id, "cancel_target": "appointment"},
        )
        return f"Encontre esta cita activa:\n{_format_appointment_summary(appointment)}\n\nConfirmas la cancelacion? Responde SI o NO."
    if auction:
        _update_session(
            session,
            step="waiting_cancel_confirm",
            state_data={"auction_id": auction.id, "cancel_target": "auction"},
        )
        return f"Encontre esta subasta abierta:\nSubasta #{auction.id}: {auction.title}\n\nConfirmas la cancelacion? Responde SI o NO."
    if session.current_step != "initial":
        _reset_session(session)
        return "Proceso cancelado."
    return "No tienes citas ni subastas activas para cancelar."


def _handle_cancel_target(session: ChatSession, text: str, state: dict) -> str:
    if text.strip() == "1":
        appointment_id = state.get("appointment_id")
        appointment = _get_owned_appointment(session, appointment_id)
        if appointment is None:
            _reset_session(session)
            return "No encontre esa cita activa."
        _update_session(
            session,
            step="waiting_cancel_confirm",
            state_data={"appointment_id": appointment_id, "cancel_target": "appointment"},
        )
        return f"Confirmas la cancelacion de esta cita?\n{_format_appointment_summary(appointment)}\n\nResponde SI o NO."
    if text.strip() == "2":
        auction_id = state.get("auction_id")
        auction = Auction.objects.filter(pk=auction_id, status=Auction.Status.OPEN).first()
        if auction is None:
            _reset_session(session)
            return "No encontre esa subasta abierta."
        _update_session(
            session,
            step="waiting_cancel_confirm",
            state_data={"auction_id": auction_id, "cancel_target": "auction"},
        )
        return f"Confirmas la cancelacion de la subasta #{auction.id}: {auction.title}?\n\nResponde SI o NO."
    return "Responde 1 para cancelar la cita o 2 para cancelar la subasta."


def _handle_cancel_confirmation(session: ChatSession, lowered_text: str, state: dict) -> str:
    if lowered_text in NO_CHOICES:
        _reset_session(session)
        return "Listo, dejamos la cancelacion quieta."
    if lowered_text not in YES_CHOICES:
        return "Para estar seguros, responde SI para confirmar la cancelacion o NO para descartarla."

    cancel_target = state.get("cancel_target", "appointment")

    if cancel_target == "auction":
        auction = Auction.objects.filter(pk=state.get("auction_id"), status=Auction.Status.OPEN).first()
        if auction is None:
            _reset_session(session)
            return "Ya no encontré esa subasta abierta para cancelar."
        with transaction.atomic():
            Bid.objects.filter(auction=auction, status=Bid.Status.PENDING).update(status=Bid.Status.REJECTED)
            auction.status = Auction.Status.CANCELLED
            auction.save(update_fields=["status", "updated_at"])
        _reset_session(session)
        return f"Listo, cancelé la subasta #{auction.id}. ❌\nLas ofertas pendientes fueron rechazadas."

    appointment = _get_owned_appointment(session, state.get("appointment_id"))
    if appointment is None:
        _reset_session(session)
        return "Ya no encontré esa cita activa para cancelar."
    cancel_appointment(appointment, actor=session.user, reason=DEFAULT_CANCELLATION_REASON)
    _reset_session(session)
    return f"Listo, cancelé tu cita. ❌\n\n{_format_appointment_summary(appointment)}"


def _start_reschedule_flow(session: ChatSession) -> str:
    appointment = _get_upcoming_client_appointment(session)
    if appointment is None:
        _reset_session(session)
        return "No encontré una cita activa para reagendar."

    slots = get_available_slots(
        technician=appointment.technician,
        service=appointment.service,
        days=DEFAULT_SLOT_DAYS,
        exclude_appointment_id=appointment.id,
    )
    slots = [
        slot
        for slot in slots
        if slot["start"] != appointment.scheduled_start or slot["end"] != appointment.scheduled_end
    ][:DEFAULT_SLOT_COUNT]
    if not slots:
        _reset_session(session)
        return "Hmm, no encontré horarios disponibles para reagendar 😕\nPodemos intentarlo más tarde o revisar otra opción."

    serialized_slots = [_serialize_slot(slot) for slot in slots]
    _update_session(
        session,
        step="waiting_reschedule_slot_selection",
        state_data={"appointment_id": appointment.id, "slots": serialized_slots},
    )
    return (
        f"Esta es tu cita actual:\n{_format_appointment_summary(appointment)}\n\n"
        "Encontré estos horarios disponibles para reagendar 📅\n"
        f"{_format_slots_list(serialized_slots)}\n\n"
        "Responde con el número del nuevo horario."
    )


def _handle_reschedule_slot_selection(session: ChatSession, text: str, state: dict) -> str:
    slots = state.get("slots") or []
    selected_index = _parse_numeric_choice(text, len(slots))
    if selected_index is None:
        return f"Responde con un número entre 1 y {len(slots)} para elegir el nuevo horario."

    appointment = _get_owned_appointment(session, state.get("appointment_id"))
    if appointment is None:
        _reset_session(session)
        return "Ya no encontré esa cita activa para reagendar."

    selected_slot = slots[selected_index]
    try:
        reschedule_appointment(
            appointment,
            actor=session.user,
            new_start=_parse_slot_datetime(selected_slot["start"]),
            new_end=_parse_slot_datetime(selected_slot["end"]),
            reason=DEFAULT_RESCHEDULE_REASON,
        )
    except DjangoValidationError:
        logger.exception("No se pudo reagendar Appointment desde Telegram chatbot")
        return "Ese horario ya no está disponible 😕\nResponde con otro número de la lista para intentarlo de nuevo."

    appointment.refresh_from_db()
    _reset_session(session)
    return (
        "¡Tu cita fue reagendada con éxito! 📅\n\n"
        f"Nuevo horario: {_format_slot_range(selected_slot)}\n"
        f"Cita: {_format_appointment_summary(appointment)}"
    )


def _finalize_booking(session: ChatSession, state: dict) -> str:
    if session.user_id is None:
        _ensure_client_user(session, state)

    technician = (
        TechnicianProfile.objects.select_related("user")
        .filter(pk=state["selected_technician_id"])
        .first()
    )
    service = Service.objects.filter(pk=state["selected_service_id"]).first()
    selected_slot = state.get("selected_slot")
    if technician is None or service is None or not selected_slot:
        _reset_session(session)
        return "No pude recuperar la informacion del tecnico, servicio u horario. Intenta de nuevo."

    lead = _create_chat_lead(session, state, technician, service)
    try:
        appointment = create_appointment(
            client=session.user,
            technician=technician,
            service=service,
            lead=lead,
            scheduled_start=_parse_slot_datetime(selected_slot["start"]),
            scheduled_end=_parse_slot_datetime(selected_slot["end"]),
            status=Appointment.Status.CONFIRMED,
            metadata={
                "source": CHATBOT_SOURCE,
                "chat_id": session.chat_id,
                "category": state.get("categoria"),
                "location": state.get("zona"),
                "request_text": state.get("request_text"),
                "client_address": session.user.address,
            },
            actor=session.user,
        )
    except DjangoValidationError:
        logger.exception("No se pudo crear Appointment desde Telegram chatbot")
        return "No pude reservar ese horario porque acaba de dejar de estar disponible. Responde con otro numero de la lista."

    _reset_session(session)
    return (
        "¡Listo, tu cita quedó agendada! 🎉\n\n"
        f"Cliente: {_display_client_name(session.user)}\n"
        f"Servicio: {service.title}\n"
        f"Tecnico: {technician.user.get_full_name() or technician.user.username}\n"
        f"Horario: {_format_slot_range(selected_slot)}\n"
        f"Direccion: {session.user.address}\n\n"
        f"Numero de cita: {appointment.id}"
    )


def _ensure_client_user(session: ChatSession, state: dict) -> None:
    draft = dict(state.get("client_draft") or {})
    user = session.user or User.objects.filter(telegram_chat_id=str(session.chat_id)).first()
    if user is None:
        user = User.objects.create(
            username=_build_telegram_username(session.chat_id),
            role=User.Role.CLIENT,
            telegram_chat_id=str(session.chat_id),
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])

    if draft.get("full_name"):
        first_name, last_name = _split_full_name(draft["full_name"])
        user.first_name = first_name
        user.last_name = last_name
    if draft.get("phone_number"):
        user.phone_number = draft["phone_number"]
    if draft.get("email"):
        user.email = draft["email"]
    if draft.get("address"):
        user.address = draft["address"]
    if not user.telegram_chat_id:
        user.telegram_chat_id = str(session.chat_id)
    user.role = User.Role.CLIENT
    user.save()

    session.user = user
    session.save(update_fields=["user", "updated_at"])


def _next_missing_contact_field(user, state: dict) -> str | None:
    draft = dict(state.get("client_draft") or {})
    for field_name in CONTACT_FIELD_SEQUENCE:
        if field_name == "full_name":
            if draft.get("full_name"):
                continue
            if user and (user.first_name or "").strip():
                continue
        elif field_name == "phone_number":
            if draft.get("phone_number"):
                continue
            if user and (user.phone_number or "").strip():
                continue
        elif field_name == "email":
            if draft.get("email"):
                continue
            if user and (user.email or "").strip():
                continue
        elif field_name == "address":
            if draft.get("address"):
                continue
            if user and (getattr(user, "address", "") or "").strip():
                continue
        return field_name
    return None


def _validate_contact_field(field_name: str, value: str) -> str:
    cleaned = value.strip()
    if field_name == "full_name":
        if len(cleaned.split()) < 2:
            raise ValueError("Necesito tu nombre y apellido para continuar.")
        return cleaned
    if field_name == "phone_number":
        digits = re.sub(r"\D", "", cleaned)
        if len(digits) < 10 or len(digits) > 15:
            raise ValueError("Comparte un numero de celular valido, por ejemplo 3001234567 o 573001234567.")
        return digits
    if field_name == "email":
        try:
            validate_email(cleaned)
        except Exception as exc:
            raise ValueError("Comparte un correo valido, por ejemplo nombre@correo.com.") from exc
        return cleaned.lower()
    if field_name == "address":
        if len(cleaned) < 8:
            raise ValueError("Comparte una direccion mas completa para poder registrar la cita.")
        return cleaned
    return cleaned


def _recommend_technicians(category: str, zone: str) -> list[dict]:
    request_payload = RecommendationRequest(
        category=category,
        location=zone,
        urgency="normal",
        limit=3,
    )
    return list(recommend_services(request_payload))


def _resolve_auction_category(state: dict) -> Category | None:
    recommendations = state.get("recommendations") or []
    if recommendations:
        service = Service.objects.select_related("category").filter(pk=recommendations[0].get("service_id")).first()
        if service is not None:
            return service.category

    category_key = state.get("categoria")
    display_name = CATEGORY_DISPLAY_NAMES.get(category_key, category_key)
    return (
        Category.objects.filter(slug=category_key).first()
        or Category.objects.filter(name__iexact=display_name).first()
        or Category.objects.filter(name__icontains=display_name or "").first()
    )


def _ensure_session_access(user, session: ChatSession) -> None:
    if user.is_staff or user.is_superuser:
        return
    if session.user_id == user.id:
        return
    raise PermissionDenied("You do not have permission to access this chat history.")


def _get_upcoming_client_appointment(session: ChatSession) -> Appointment | None:
    if session.user_id is None:
        return None
    return (
        Appointment.objects.select_related("technician__user", "service")
        .filter(client=session.user, status__in=Appointment.ACTIVE_STATUSES, scheduled_end__gte=timezone.now())
        .order_by("scheduled_start")
        .first()
    )


def _get_owned_appointment(session: ChatSession, appointment_id) -> Appointment | None:
    if session.user_id is None or not appointment_id:
        return None
    return (
        Appointment.objects.select_related("technician__user", "service")
        .filter(pk=appointment_id, client=session.user, status__in=Appointment.ACTIVE_STATUSES)
        .first()
    )


def _create_chat_lead(session: ChatSession, state: dict, technician: TechnicianProfile, service: Service) -> ServiceLead:
    lead = ServiceLead.objects.create(
        technician=technician,
        client_user=session.user,
        service=service,
        client_name=_display_client_name(session.user),
        client_phone=session.user.phone_number or f"telegram:{session.chat_id}",
        message=state.get("request_text") or f"Solicitud desde Telegram para {service.title}",
        category=state.get("categoria") or "",
        location=ZONE_DISPLAY_NAMES.get(state.get("zona"), state.get("zona") or ""),
        urgency="normal",
        source=ServiceLead.Source.TELEGRAM,
        metadata={
            "source": CHATBOT_SOURCE,
            "chat_id": session.chat_id,
            "client_email": session.user.email,
            "client_address": session.user.address,
        },
    )
    create_notification(
        user=technician.user,
        template_name="lead_received",
        context={
            "client_name": _display_client_name(session.user),
            "category": state.get("categoria") or service.title,
        },
        channel=Notification.Channel.DASHBOARD,
        metadata={"lead_id": lead.id, "source": CHATBOT_SOURCE},
    )
    log_audit_event(
        event_type=AuditEvent.EventType.LEAD_CREATED,
        actor=session.user,
        channel="telegram",
        source="telegram_bot.chat",
        entity_type="service_lead",
        entity_id=str(lead.id),
        status="success",
        message="Lead created from Telegram chatbot",
        metadata={"technician_id": technician.id, "service_id": service.id},
    )
    return lead


def _build_recommendation_reply(category: str, location: str | None, recommendations: list[dict]) -> str:
    intro = "¡Encontré estos técnicos disponibles! ⚡\n"
    if location:
        intro += f"Aquí tienes las mejores opciones en {ZONE_DISPLAY_NAMES.get(location, location)}:"
    else:
        intro += f"Aquí tienes las mejores opciones para {CATEGORY_DISPLAY_NAMES.get(category, category)}:"
    intro += "\n\n"
    lines = [intro]
    for index, item in enumerate(recommendations, start=1):
        lines.append(
            f"{index}. {item['technician_name']} ⭐ {item['score']} pts — responde en ~{item['response_time_minutes']} min"
        )
    lines.append("\nResponde con el numero del tecnico para ver horarios disponibles.")
    lines.append("Tambien puedes responder 0 para crear una subasta y recibir ofertas.")
    return "\n".join(lines)


def _build_slots_reply(technician_name: str, slots: list[dict]) -> str:
    return (
        f"Estos son los horarios disponibles con {technician_name} 📅\n"
        f"{_format_slots_list(slots)}\n\n"
        "Responde con el numero del horario que quieres reservar."
    )


def _format_slots_list(slots: list[dict]) -> str:
    return "\n".join(f"{index}. {_format_slot_range(slot)}" for index, slot in enumerate(slots, start=1))


def _format_slot_range(slot: dict) -> str:
    start = _parse_slot_datetime(slot["start"])
    end = _parse_slot_datetime(slot["end"])
    return f"{timezone.localtime(start):%Y-%m-%d %H:%M} - {timezone.localtime(end):%H:%M}"


def _format_appointment_summary(appointment: Appointment) -> str:
    service_name = appointment.service.title if appointment.service_id else "Sin servicio"
    technician_name = appointment.technician.user.get_full_name() or appointment.technician.user.username
    return f"Cita #{appointment.id} | {service_name} | {technician_name} | {timezone.localtime(appointment.scheduled_start):%Y-%m-%d %H:%M}"


def _extract_category(intent: dict, text: str) -> str | None:
    category = intent.get("categoria")
    if category:
        normalized = str(category).strip().lower()
        for slug, keywords in CATEGORY_KEYWORDS.items():
            if normalized in keywords or normalized == slug:
                return slug
        return normalized

    lowered = (text or "").strip().lower()
    for slug, keywords in CATEGORY_KEYWORDS.items():
        if lowered == slug or any(keyword in lowered for keyword in keywords):
            return slug
    return None


def _extract_zone(intent: dict, text: str) -> str | None:
    zone = intent.get("zona")
    if zone:
        resolved_zone = _resolve_zone_text(str(zone))
        return resolved_zone or str(zone).strip().lower()

    return _resolve_zone_text(text)


def _resolve_zone_text(value: str | None) -> str | None:
    if not value:
        return None

    cleaned = str(value).strip()
    if not cleaned:
        return None

    lowered = cleaned.lower()
    for zone_slug, keywords in ZONE_KEYWORDS.items():
        if lowered == zone_slug or any(keyword == lowered or keyword in lowered for keyword in keywords):
            return zone_slug

    normalized_slug = slugify(f"Barranquilla-{cleaned}")
    zone = Zone.objects.filter(slug__iexact=normalized_slug, is_active=True).first()
    if zone is not None:
        return zone.slug

    zone = Zone.objects.filter(slug__iexact=cleaned, is_active=True).first()
    if zone is not None:
        return zone.slug

    zone = Zone.objects.filter(name__iexact=cleaned, is_active=True).first()
    if zone is not None:
        return zone.slug

    zone = Zone.objects.filter(name__icontains=cleaned, is_active=True).first()
    if zone is not None:
        return zone.slug

    return None


def _parse_numeric_choice(text: str, total_options: int) -> int | None:
    if total_options < 1 or not text.isdigit():
        return None
    selected_index = int(text) - 1
    if 0 <= selected_index < total_options:
        return selected_index
    return None


def _serialize_slot(slot: dict) -> dict:
    return {"start": slot["start"].isoformat(), "end": slot["end"].isoformat()}


def _parse_slot_datetime(value: str):
    parsed = datetime.fromisoformat(value)
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _find_zone(location: str | None) -> Zone | None:
    if not location:
        return None
    zone = Zone.objects.filter(slug__iexact=location, is_active=True).first()
    if zone is not None:
        return zone
    return Zone.objects.filter(name__icontains=location, is_active=True).first()


def _build_telegram_username(chat_id: int) -> str:
    return f"telegram_{chat_id}"


def _build_frontend_link(path: str, **params) -> str:
    query = "&".join(f"{key}={value}" for key, value in params.items() if value is not None)
    suffix = f"?{query}" if query else ""
    return f"{settings.FRONTEND_URL}{path}{suffix}"


def _split_full_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _display_client_name(user) -> str:
    full_name = user.get_full_name().strip()
    return full_name or user.username


def send_telegram_message(chat_id: int, text: str):
    payload = build_telegram_message_payload(chat_id=chat_id, text=text, preview_url=False)
    result = TelegramBotClient().send_message(payload)
    if result.error:
        logger.error("Error sending Telegram message: %s", result.error)
        log_audit_event(
            event_type=AuditEvent.EventType.INTEGRATION_ERROR,
            channel="telegram",
            source="telegram_bot.send_message",
            entity_type="chat_session",
            entity_id=str(chat_id),
            status="error",
            message="Telegram outbound message failed",
            metadata={"error": result.error},
        )
    return result
