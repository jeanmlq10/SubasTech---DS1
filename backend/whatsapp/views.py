import os

from django.http import HttpResponse
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

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
            return {
                "sender": sender,
                "selection": selection,
                "lead": None,
                "reply_text": reply_text,
                "outbound": send_result.__dict__,
            }

        recommendation = conversation.last_recommendations[index]
        service = Service.objects.select_related("technician", "category").get(pk=recommendation["service_id"])
        lead = ServiceLead.objects.create(
            technician=service.technician,
            service=service,
            client_phone=sender,
            message=conversation.last_message,
            category=conversation.last_intent.get("category", ""),
            location=conversation.last_intent.get("location", ""),
            urgency=conversation.last_intent.get("urgency", "normal"),
            metadata={"selected_option": selection, "recommendation": recommendation},
        )
        reply_text = (
            f"Listo. Enviamos tu solicitud a {recommendation['technician_name']} para {recommendation['service_title']}. "
            "El tecnico podra contactarte por WhatsApp."
        )
        send_result = WhatsAppCloudClient().send_text(sender, reply_text)
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
