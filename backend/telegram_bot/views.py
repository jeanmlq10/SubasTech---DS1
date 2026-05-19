import json
import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import JsonResponse
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
from audit.models import AuditEvent
from audit.services import log_audit_event
from catalog.models import Service, TechnicianProfile, Zone
from leads.models import ServiceLead
from notifications.models import Notification
from notifications.services import (
    build_telegram_message_payload,
    create_notification,
)
from recommendations.services import RecommendationRequest, recommend_services

from .ai import extract_intent
from .client import TelegramBotClient
from .models import ChatSession, ConversationMessage

logger = logging.getLogger(__name__)

CHATBOT_SOURCE = "telegram_chatbot"
DEFAULT_SLOT_DAYS = 7
DEFAULT_SLOT_COUNT = 5
DEFAULT_CANCELLATION_REASON = "Cancelled from Telegram chat"
DEFAULT_RESCHEDULE_REASON = "Rescheduled from Telegram chat"

CATEGORY_CHOICES = {
    "1": "electricista",
    "2": "plomero",
    "3": "cerrajero",
    "4": "pintor",
}
CATEGORY_KEYWORDS = {
    "electricista": ("electricista", "electricidad", "luz", "corriente"),
    "plomero": ("plomero", "agua", "tuberia", "fuga"),
    "cerrajero": ("cerrajero", "llave", "cerradura", "puerta"),
    "pintor": ("pintor", "pintura", "pintar"),
}
CATEGORY_QUERY_ALIASES = {
    "electricista": "electrician",
    "plomero": "plumber",
    "cerrajero": "locksmith",
    "pintor": "painter",
}
YES_CHOICES = {"si", "sí", "s", "confirmo"}
NO_CHOICES = {"no", "n"}


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


def _update_session(
    session: ChatSession,
    *,
    step: str,
    state_data: dict | None = None,
) -> None:
    session.current_step = step
    if state_data is not None:
        session.state_data = state_data
    session.save(update_fields=["current_step", "state_data", "updated_at"])


def _reset_session(session: ChatSession) -> None:
    _update_session(session, step="initial", state_data={})


def _process_chat_message(
    chat_id: int,
    text: str,
    *,
    user=None,
) -> tuple[ChatSession, dict, str]:
    session = _get_session(chat_id)
    if user is not None and session.user_id != user.id:
        session.user = user
        session.save(update_fields=["user", "updated_at"])

    intent = extract_intent(text)
    _save_inbound(session, text, intent)
    reply = handle_conversation(session, text, intent)
    _save_outbound(session, reply)
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

            session, intent, reply = _process_chat_message(int(chat_id), text)

            if not settings.TELEGRAM_DRY_RUN:
                send_telegram_message(chat_id, reply)
            else:
                logger.info("[DRY RUN] Para %s: %s", chat_id, reply)
            return JsonResponse(
                {"ok": True, "chat_id": chat_id, "intent": intent, "reply": reply}
            )
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

    session, intent, reply = _process_chat_message(
        chat_id,
        text,
        user=request.user,
    )
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
    state = dict(session.state_data or {})
    step = session.current_step
    cleaned_text = (text or "").strip()
    lowered = cleaned_text.lower()
    accion = (intent.get("accion") or "").lower()

    if cleaned_text in CATEGORY_CHOICES and step != "waiting_technician_selection":
        intent = {
            "accion": "agendar",
            "categoria": CATEGORY_CHOICES[cleaned_text],
            "zona": None,
            "urgencia": "media",
        }
        accion = "agendar"

    if accion == "saludo" or lowered in {"/start", "hola", "buenas", "buenos dias"}:
        _reset_session(session)
        return (
            "Hola, soy el asistente de SubasTech.\n\n"
            "Puedo ayudarte a encontrar tecnicos del hogar y agendar una cita.\n\n"
            "¿Que servicio necesitas?\n"
            "1. Electricista\n2. Plomero\n3. Cerrajero\n4. Pintor\n\n"
            "Tambien puedes describirme tu problema."
        )

    if step == "waiting_cancel_confirm":
        return _handle_cancel_confirmation(session, lowered, state)

    if step == "waiting_technician_selection":
        return _handle_technician_selection(session, cleaned_text, state)

    if step == "waiting_slot_selection":
        return _handle_slot_booking(session, cleaned_text, state)

    if step == "waiting_reschedule_slot_selection":
        return _handle_reschedule_slot_selection(session, cleaned_text, state)

    if accion == "cancelar":
        return _start_cancel_flow(session)

    if accion == "reagendar":
        return _start_reschedule_flow(session)

    if accion == "agendar" or step == "waiting_category":
        return _start_booking_flow(session, cleaned_text, intent)

    return (
        "No entendi tu mensaje.\n\n"
        "Puedes decirme cosas como:\n"
        "- Necesito un electricista en Riomar\n"
        "- Quiero cancelar mi cita\n"
        "- Reagendar mi cita"
    )


def _start_booking_flow(session: ChatSession, text: str, intent: dict) -> str:
    category = _extract_category(intent, text)
    if not category:
        _update_session(session, step="waiting_category", state_data={})
        return (
            "¿Que tipo de tecnico necesitas?\n"
            "Puedes responder: electricista, plomero, cerrajero o pintor."
        )

    location = (intent.get("zona") or "").strip() or None
    urgency = _normalize_urgency(intent.get("urgencia"))
    recommendation_request = RecommendationRequest(
        category=_category_query_value(category),
        location=location,
        urgency=urgency,
        limit=3,
    )
    recommendations = list(recommend_services(recommendation_request))
    if not recommendations:
        _reset_session(session)
        return (
            "Aun no encontre tecnicos disponibles para esa solicitud.\n"
            "Intenta con otra categoria o zona."
        )

    _update_session(
        session,
        step="waiting_technician_selection",
        state_data={
            "request_text": text,
            "categoria": category,
            "zona": location,
            "urgencia": urgency,
            "recommendations": recommendations,
        },
    )
    return _build_recommendation_reply(category, location, recommendations)


def _handle_technician_selection(session: ChatSession, text: str, state: dict) -> str:
    recommendations = state.get("recommendations") or []
    selected_index = _parse_numeric_choice(text, len(recommendations))
    if selected_index is None:
        return f"Responde con un numero entre 1 y {len(recommendations)} para escoger tecnico."

    selected = recommendations[selected_index]
    technician = TechnicianProfile.objects.filter(pk=selected["technician_id"]).first()
    service = Service.objects.filter(pk=selected["service_id"]).first()
    if technician is None or service is None:
        _reset_session(session)
        return "No pude recuperar la informacion del tecnico seleccionado. Intenta de nuevo."
    zone = _find_zone(state.get("zona"))
    slots = get_available_slots(
        technician=technician,
        service=service,
        zone=zone,
        days=DEFAULT_SLOT_DAYS,
    )[:DEFAULT_SLOT_COUNT]
    if not slots:
        return (
            "Ese tecnico no tiene horarios disponibles en los proximos dias.\n"
            "Puedes elegir otro tecnico de la lista."
        )

    serialized_slots = [_serialize_slot(slot) for slot in slots]
    _update_session(
        session,
        step="waiting_slot_selection",
        state_data={
            "request_text": state.get("request_text", ""),
            "categoria": state.get("categoria"),
            "zona": state.get("zona"),
            "urgencia": state.get("urgencia"),
            "selected_service_id": service.id,
            "selected_technician_id": technician.id,
            "selected_technician_name": selected["technician_name"],
            "slots": serialized_slots,
        },
    )
    return _build_slots_reply(selected["technician_name"], serialized_slots)


def _handle_slot_booking(session: ChatSession, text: str, state: dict) -> str:
    slots = state.get("slots") or []
    selected_index = _parse_numeric_choice(text, len(slots))
    if selected_index is None:
        return f"Responde con un numero entre 1 y {len(slots)} para escoger horario."
    if session.user_id is None:
        return (
            "Necesito que vincules tu usuario antes de agendar.\n"
            "Usa el endpoint /api/chatbot/link-user/ y luego vuelve a intentarlo."
        )

    selected_slot = slots[selected_index]
    technician = (
        TechnicianProfile.objects.select_related("user")
        .filter(pk=state["selected_technician_id"])
        .first()
    )
    service = Service.objects.filter(pk=state["selected_service_id"]).first()
    if technician is None or service is None:
        _reset_session(session)
        return "No pude recuperar la informacion del tecnico o del servicio. Intenta de nuevo."
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
            },
            actor=session.user,
        )
    except DjangoValidationError:
        logger.exception("No se pudo crear Appointment desde Telegram chatbot")
        return (
            "No pude reservar ese horario porque acaba de dejar de estar disponible.\n"
            "Responde con otro numero de la lista."
        )

    _reset_session(session)
    return (
        "Cita agendada.\n\n"
        f"Tecnico: {technician.user.get_full_name() or technician.user.username}\n"
        f"Servicio: {service.title}\n"
        f"Horario: {_format_slot_range(selected_slot)}\n\n"
        f"Numero de cita: {appointment.id}"
    )


def _start_cancel_flow(session: ChatSession) -> str:
    appointment = _get_upcoming_client_appointment(session)
    if appointment is None:
        _reset_session(session)
        return "No encontre una cita activa para cancelar."

    _update_session(
        session,
        step="waiting_cancel_confirm",
        state_data={"appointment_id": appointment.id},
    )
    return (
        "Encontre esta cita activa:\n"
        f"{_format_appointment_summary(appointment)}\n\n"
        "¿Confirmas la cancelacion? Responde SI o NO."
    )


def _handle_cancel_confirmation(session: ChatSession, lowered_text: str, state: dict) -> str:
    if lowered_text in NO_CHOICES:
        _reset_session(session)
        return "Cancelacion descartada. Tu cita sigue activa."
    if lowered_text not in YES_CHOICES:
        return "Responde SI para cancelar la cita o NO para conservarla."

    appointment = _get_owned_appointment(session, state.get("appointment_id"))
    if appointment is None:
        _reset_session(session)
        return "Ya no encontre esa cita activa para cancelar."

    cancel_appointment(
        appointment,
        actor=session.user,
        reason=DEFAULT_CANCELLATION_REASON,
    )
    _reset_session(session)
    return f"Cita cancelada correctamente.\n\n{_format_appointment_summary(appointment)}"


def _start_reschedule_flow(session: ChatSession) -> str:
    appointment = _get_upcoming_client_appointment(session)
    if appointment is None:
        _reset_session(session)
        return "No encontre una cita activa para reagendar."

    slots = get_available_slots(
        technician=appointment.technician,
        service=appointment.service,
        days=DEFAULT_SLOT_DAYS,
        exclude_appointment_id=appointment.id,
    )
    slots = [
        slot
        for slot in slots
        if (
            slot["start"] != appointment.scheduled_start
            or slot["end"] != appointment.scheduled_end
        )
    ][:DEFAULT_SLOT_COUNT]
    if not slots:
        _reset_session(session)
        return "No encontre horarios alternos disponibles para reagendar esa cita."

    serialized_slots = [_serialize_slot(slot) for slot in slots]
    _update_session(
        session,
        step="waiting_reschedule_slot_selection",
        state_data={
            "appointment_id": appointment.id,
            "slots": serialized_slots,
        },
    )
    return (
        f"Esta es tu cita actual:\n{_format_appointment_summary(appointment)}\n\n"
        "Estos son los horarios disponibles para reagendar:\n"
        f"{_format_slots_list(serialized_slots)}\n\n"
        "Responde con el numero del nuevo horario."
    )


def _handle_reschedule_slot_selection(session: ChatSession, text: str, state: dict) -> str:
    slots = state.get("slots") or []
    selected_index = _parse_numeric_choice(text, len(slots))
    if selected_index is None:
        return f"Responde con un numero entre 1 y {len(slots)} para reagendar."

    appointment = _get_owned_appointment(session, state.get("appointment_id"))
    if appointment is None:
        _reset_session(session)
        return "Ya no encontre esa cita activa para reagendar."

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
        return (
            "No pude reagendar a ese horario porque ya no esta disponible.\n"
            "Responde con otro numero de la lista."
        )

    appointment.refresh_from_db()
    _reset_session(session)
    return (
        "Cita reagendada correctamente.\n\n"
        f"Nuevo horario: {_format_slot_range(selected_slot)}\n"
        f"Cita: {_format_appointment_summary(appointment)}"
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
        .filter(
            client=session.user,
            status__in=Appointment.ACTIVE_STATUSES,
            scheduled_end__gte=timezone.now(),
        )
        .order_by("scheduled_start")
        .first()
    )


def _get_owned_appointment(session: ChatSession, appointment_id) -> Appointment | None:
    if session.user_id is None or not appointment_id:
        return None
    return (
        Appointment.objects.select_related("technician__user", "service")
        .filter(
            pk=appointment_id,
            client=session.user,
            status__in=Appointment.ACTIVE_STATUSES,
        )
        .first()
    )


def _create_chat_lead(
    session: ChatSession,
    state: dict,
    technician: TechnicianProfile,
    service: Service,
) -> ServiceLead:
    lead = ServiceLead.objects.create(
        technician=technician,
        client_user=session.user,
        service=service,
        client_name=session.user.get_full_name(),
        client_phone=session.user.phone_number or f"telegram:{session.chat_id}",
        message=state.get("request_text") or f"Solicitud desde Telegram para {service.title}",
        category=state.get("categoria") or "",
        location=state.get("zona") or "",
        urgency=state.get("urgencia") or "normal",
        source=ServiceLead.Source.TELEGRAM,
        metadata={
            "source": CHATBOT_SOURCE,
            "chat_id": session.chat_id,
        },
    )
    create_notification(
        user=technician.user,
        template_name="lead_received",
        context={
            "client_name": session.user.get_full_name() or session.user.username,
            "category": state.get("categoria") or service.title,
        },
        channel=Notification.Channel.DASHBOARD,
        metadata={
            "lead_id": lead.id,
            "source": CHATBOT_SOURCE,
        },
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
    intro = f"Tecnicos disponibles para {category}"
    if location:
        intro += f" en {location}"
    intro += ":\n\n"

    lines = [intro]
    for index, item in enumerate(recommendations, start=1):
        lines.append(
            (
                f"{index}. {item['technician_name']} | {item['service_title']} | "
                f"score {item['score']} | respuesta aprox. {item['response_time_minutes']} min"
            )
        )
    lines.append("\nResponde con el numero del tecnico para ver horarios disponibles.")
    return "\n".join(lines)


def _build_slots_reply(technician_name: str, slots: list[dict]) -> str:
    return (
        f"Horarios disponibles con {technician_name}:\n"
        f"{_format_slots_list(slots)}\n\n"
        "Responde con el numero del horario que quieres reservar."
    )


def _format_slots_list(slots: list[dict]) -> str:
    return "\n".join(
        f"{index}. {_format_slot_range(slot)}"
        for index, slot in enumerate(slots, start=1)
    )


def _format_slot_range(slot: dict) -> str:
    start = _parse_slot_datetime(slot["start"])
    end = _parse_slot_datetime(slot["end"])
    return (
        f"{timezone.localtime(start):%Y-%m-%d %H:%M}"
        f" - {timezone.localtime(end):%H:%M}"
    )


def _format_appointment_summary(appointment: Appointment) -> str:
    service_name = appointment.service.title if appointment.service_id else "Sin servicio"
    technician_name = (
        appointment.technician.user.get_full_name()
        or appointment.technician.user.username
    )
    return (
        f"Cita #{appointment.id} | {service_name} | {technician_name} | "
        f"{timezone.localtime(appointment.scheduled_start):%Y-%m-%d %H:%M}"
    )


def _extract_category(intent: dict, text: str) -> str | None:
    category = intent.get("categoria")
    if category:
        return str(category).strip().lower()

    lowered = (text or "").strip().lower()
    for normalized, keywords in CATEGORY_KEYWORDS.items():
        if lowered == normalized or any(keyword in lowered for keyword in keywords):
            return normalized
    return None


def _normalize_urgency(raw_value) -> str:
    mapping = {
        "alta": "high",
        "high": "high",
        "urgente": "high",
        "media": "normal",
        "normal": "normal",
        "baja": "low",
        "low": "low",
    }
    return mapping.get(str(raw_value or "").strip().lower(), "normal")


def _category_query_value(category: str | None) -> str | None:
    if not category:
        return None
    return CATEGORY_QUERY_ALIASES.get(category, category)


def _parse_numeric_choice(text: str, total_options: int) -> int | None:
    if total_options < 1 or not text.isdigit():
        return None
    selected_index = int(text) - 1
    if 0 <= selected_index < total_options:
        return selected_index
    return None


def _serialize_slot(slot: dict) -> dict:
    return {
        "start": slot["start"].isoformat(),
        "end": slot["end"].isoformat(),
    }


def _parse_slot_datetime(value: str):
    parsed = datetime.fromisoformat(value)
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _find_zone(location: str | None) -> Zone | None:
    if not location:
        return None
    return Zone.objects.filter(name__icontains=location, is_active=True).first()


def send_telegram_message(chat_id: int, text: str):
    payload = build_telegram_message_payload(
        chat_id=chat_id,
        text=text,
        preview_url=False,
    )
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
