import os

from django.http import HttpResponse
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from audit.models import AuditEvent
from audit.services import log_audit_event
from catalog.models import Service
from leads.models import ServiceLead
from recommendations.services import RecommendationRequest, recommend_services
from .ai import extract_intent
from .client import WhatsAppCloudClient
from .models import WhatsAppConversation


class WhatsAppWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "subastech-dev-token")
        if request.query_params.get("hub.verify_token") == verify_token:
            return HttpResponse(request.query_params.get("hub.challenge", ""), status=200)
        return Response({"detail": "Invalid verification token"}, status=status.HTTP_403_FORBIDDEN)

    def post(self, request):
        message = self._extract_message_text(request.data).strip()
        sender = self._extract_sender(request.data)
        log_audit_event(
            event_type=AuditEvent.EventType.WEBHOOK_RECEIVED,
            channel="whatsapp",
            source="whatsapp.webhook",
            entity_type="conversation",
            entity_id=sender or "unknown",
            status="info",
            message="WhatsApp webhook payload received",
            metadata={"sender": sender, "has_message": bool(message)},
        )

        if not message:
            return Response({"detail": "No inbound text message found", "ignored": True}, status=status.HTTP_200_OK)

        if sender and message.isdigit():
            selection_response = self._handle_selection(sender, int(message))
            if selection_response:
                return Response(selection_response)

        intent = extract_intent(message)
        recommendations = list(
            recommend_services(
                RecommendationRequest(
                    category=intent.get("category") or None,
                    location=intent.get("location") or None,
                    urgency=intent.get("urgency", "normal"),
                    limit=3,
                )
            )
        )
        reply_text = build_recommendation_reply(intent, recommendations)
        if sender:
            WhatsAppConversation.objects.update_or_create(
                phone_number=sender,
                defaults={
                    "last_message": message,
                    "last_intent": intent,
                    "last_recommendations": recommendations,
                },
            )
        send_result = WhatsAppCloudClient().send_text(sender, reply_text) if sender else None
        if send_result:
            self._log_send_result(sender=sender, send_result=send_result, context="recommendations")

        return Response(
            {
                "message": message,
                "sender": sender,
                "intent": intent,
                "recommendations": recommendations,
                "reply_text": reply_text,
                "outbound": send_result.__dict__ if send_result else None,
            }
        )

    def _handle_selection(self, sender: str, selection: int) -> dict | None:
        conversation = WhatsAppConversation.objects.filter(phone_number=sender).first()
        if not conversation or not conversation.last_recommendations:
            return None

        index = selection - 1
        if index < 0 or index >= len(conversation.last_recommendations):
            reply_text = "No reconozco esa opcion. Responde con uno de los numeros de la lista enviada."
            send_result = WhatsAppCloudClient().send_text(sender, reply_text)
            self._log_send_result(sender=sender, send_result=send_result, context="invalid_selection")
            return {
                "sender": sender,
                "selection": selection,
                "lead": None,
                "reply_text": reply_text,
                "outbound": send_result.__dict__,
            }

        recommendation = conversation.last_recommendations[index]
        service = Service.objects.select_related("technician", "category").get(pk=recommendation["service_id"])
        client_user = User.objects.filter(phone_number=sender).first() or User.objects.filter(whatsapp_id=sender).first()
        lead = ServiceLead.objects.create(
            technician=service.technician,
            client_user=client_user,
            service=service,
            client_phone=sender,
            message=conversation.last_message,
            category=conversation.last_intent.get("category", ""),
            location=conversation.last_intent.get("location", ""),
            urgency=conversation.last_intent.get("urgency", "normal"),
            metadata={"selected_option": selection, "recommendation": recommendation},
        )
        log_audit_event(
            event_type=AuditEvent.EventType.LEAD_CREATED,
            actor=client_user,
            channel="whatsapp",
            source="whatsapp.selection",
            entity_type="lead",
            entity_id=lead.id,
            status="success",
            message="Lead created from WhatsApp technician selection",
            metadata={"sender": sender, "selection": selection, "technician_id": service.technician_id, "service_id": service.id},
        )
        reply_text = (
            f"Listo. Enviamos tu solicitud a {recommendation['technician_name']} para {recommendation['service_title']}. "
            "El tecnico podra contactarte por WhatsApp."
        )
        send_result = WhatsAppCloudClient().send_text(sender, reply_text)
        self._log_send_result(sender=sender, send_result=send_result, context="lead_created")
        return {
            "sender": sender,
            "selection": selection,
            "lead": {"id": lead.id, "status": lead.status, "technician": recommendation["technician_name"]},
            "reply_text": reply_text,
            "outbound": send_result.__dict__,
        }

    def _extract_message_text(self, payload: dict) -> str:
        if payload.get("message"):
            return str(payload["message"])
        try:
            return payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
        except (KeyError, IndexError, TypeError):
            return ""

    def _extract_sender(self, payload: dict) -> str:
        if payload.get("from"):
            return str(payload["from"])
        try:
            return payload["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
        except (KeyError, IndexError, TypeError):
            return ""

    def _log_send_result(self, *, sender: str, send_result, context: str):
        log_audit_event(
            event_type=AuditEvent.EventType.MESSAGE_SENT if send_result.sent or send_result.dry_run else AuditEvent.EventType.INTEGRATION_ERROR,
            channel="whatsapp",
            source="whatsapp.send_text",
            entity_type="conversation",
            entity_id=sender,
            status="success" if send_result.sent else ("dry_run" if send_result.dry_run else "error"),
            message=f"WhatsApp outbound message processed during {context}",
            metadata={
                "context": context,
                "sent": send_result.sent,
                "dry_run": send_result.dry_run,
                "payload": send_result.payload,
                "response": send_result.response,
                "error": send_result.error,
            },
        )


def build_recommendation_reply(intent: dict, recommendations: list[dict]) -> str:
    category = intent.get("category") or "servicio tecnico"
    location = intent.get("location") or "tu zona"

    if not recommendations:
        return (
            "Hola, soy SubasTech. Entendi que necesitas "
            f"{category} en {location}, pero aun no encontre tecnicos disponibles con esos filtros. "
            "Un asesor puede revisar tu caso o puedes intentar con una zona cercana."
        )

    lines = ["Hola, soy SubasTech. Estas son las mejores opciones que encontre:", ""]
    for index, item in enumerate(recommendations, start=1):
        lines.extend(
            [
                f"{index}. {item['technician_name']} - {item['service_title']}",
                f"   Puntaje: {item['score']}/100 | Respuesta: {item['response_time_minutes']} min",
                f"   Precio base: ${item['base_price']}",
            ]
        )
    lines.extend(["", "Responde con el numero del tecnico que prefieres y crearemos la solicitud."])
    return "\n".join(lines)
