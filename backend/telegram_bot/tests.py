from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from appointments.models import Appointment
from audit.models import AuditEvent
from catalog.models import Category, Service, TechnicianAvailability, TechnicianProfile, Zone
from leads.models import ServiceLead
from notifications.models import Notification

from .ai import extract_intent
from .models import ChatSession, ConversationMessage


@override_settings(GEMINI_API_KEY="")
class TelegramBotTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.webhook_client = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="telegram-client",
            password="Password123",
            role="client",
            first_name="Sara",
            last_name="Lopez",
            phone_number="573001112233",
            email="sara@example.com",
            address="Cra 10 # 20-30, Barranquilla",
        )
        self.client.force_authenticate(self.user)

        self.category = Category.objects.create(name="Electrician", slug="electrician")
        self.zone = Zone.objects.create(name="Riomar", city="Barranquilla")
        self.boston_zone = Zone.objects.create(name="Boston", city="Barranquilla")
        self.technician_user = user_model.objects.create_user(
            username="telegram-tech",
            password="Password123",
            role="technician",
            first_name="Carlos",
            last_name="Mendoza",
        )
        self.profile = TechnicianProfile.objects.create(
            user=self.technician_user,
            is_verified=True,
            availability_status=TechnicianProfile.AvailabilityStatus.AVAILABLE,
            response_time_minutes=15,
        )
        self.profile.zones.add(self.zone)
        self.profile.zones.add(self.boston_zone)
        self.service = Service.objects.create(
            technician=self.profile,
            category=self.category,
            title="Instalacion electrica",
            description="Servicio residencial",
            base_price=80000,
        )

        self.available_date = self._next_weekday(1)
        TechnicianAvailability.objects.create(
            technician=self.profile,
            weekday=self.available_date.isoweekday(),
            start_time=time(9, 0),
            end_time=time(12, 0),
            is_active=True,
        )

    def test_extract_intent_fallback_detects_cancel_and_reschedule(self):
        cancel_intent = extract_intent("Quiero cancelar mi cita")
        reschedule_intent = extract_intent("Necesito reagendar mi cita")

        self.assertEqual(cancel_intent["accion"], "cancelar")
        self.assertEqual(reschedule_intent["accion"], "reagendar")

    def test_initial_message_returns_recommendations(self):
        response = self._send_message("Necesito un electricista urgente en Riomar")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["step"], "waiting_technician_selection")
        self.assertIn("Tecnicos disponibles", body["reply"])
        self.assertIn("Carlos Mendoza", body["reply"])
        self.assertIn("Escribe INICIO para volver al principio.", body["reply"])

    def test_missing_zone_asks_for_free_text_neighborhood(self):
        response = self._send_message("Necesito un electricista")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["step"], "waiting_zone")
        self.assertIn("Escribeme el barrio", body["reply"])
        self.assertNotIn("1. Riomar", body["reply"])

    def test_free_text_neighborhood_continues_booking_flow(self):
        first_response = self._send_message("Necesito un electricista")
        self.assertEqual(first_response.json()["step"], "waiting_zone")

        zone_response = self._send_message("Boston")

        self.assertEqual(zone_response.status_code, 200)
        self.assertEqual(zone_response.json()["step"], "waiting_technician_selection")
        self.assertIn("Tecnicos disponibles", zone_response.json()["reply"])

    def test_numeric_text_is_not_accepted_as_neighborhood(self):
        first_response = self._send_message("Necesito un electricista")
        self.assertEqual(first_response.json()["step"], "waiting_zone")

        zone_response = self._send_message("2")

        self.assertEqual(zone_response.status_code, 200)
        self.assertEqual(zone_response.json()["step"], "waiting_zone")
        self.assertIn("No encontre ese barrio", zone_response.json()["reply"])
        self.assertNotIn("Alto Prado", zone_response.json()["reply"])

    def test_reset_command_returns_to_start_from_any_step(self):
        first_response = self._send_message("Necesito un electricista")
        self.assertEqual(first_response.json()["step"], "waiting_zone")

        reset_response = self._send_message("inicio")

        self.assertEqual(reset_response.status_code, 200)
        self.assertEqual(reset_response.json()["step"], "initial")
        self.assertIn("Hola, soy el asistente de SubasTech.", reset_response.json()["reply"])
        self.assertIn("Escribe INICIO para volver al principio.", reset_response.json()["reply"])

    def test_history_persists_full_conversation(self):
        self._send_message("hola")
        self._send_message("Necesito un electricista en Riomar")

        history = self.client.get("/api/chatbot/history/101/")

        self.assertEqual(history.status_code, 200)
        payload = history.json()
        self.assertEqual(payload["chat_id"], 101)
        self.assertEqual(len(payload["messages"]), 4)
        self.assertEqual(payload["messages"][0]["direction"], ConversationMessage.Direction.INBOUND)
        self.assertEqual(payload["messages"][1]["direction"], ConversationMessage.Direction.OUTBOUND)
        self.assertEqual(payload["current_step"], "waiting_technician_selection")

    def test_selecting_slot_creates_appointment_and_lead(self):
        first_response = self._send_message("Necesito un electricista en Riomar")
        self.assertEqual(first_response.json()["step"], "waiting_technician_selection")

        selection_response = self._send_message("1")
        self.assertEqual(selection_response.status_code, 200)
        self.assertEqual(selection_response.json()["step"], "waiting_slot_selection")
        self.assertIn("Horarios disponibles", selection_response.json()["reply"])
        self.assertNotIn("En que zona", selection_response.json()["reply"])

        booking_response = self._send_message("1")

        self.assertEqual(booking_response.status_code, 200)
        self.assertEqual(booking_response.json()["step"], "initial")
        self.assertIn("Cita agendada", booking_response.json()["reply"])
        self.assertEqual(Appointment.objects.count(), 1)
        self.assertEqual(ServiceLead.objects.count(), 1)
        appointment = Appointment.objects.select_related("lead").get()
        self.assertEqual(appointment.client, self.user)
        self.assertEqual(appointment.technician, self.profile)
        self.assertEqual(appointment.status, Appointment.Status.CONFIRMED)
        self.assertEqual(appointment.metadata["source"], "telegram_chatbot")
        self.assertEqual(appointment.lead.metadata["source"], "telegram_chatbot")
        self.assertEqual(appointment.lead.source, ServiceLead.Source.TELEGRAM)
        self.assertTrue(
            Notification.objects.filter(
                user=self.technician_user,
                title="Nueva solicitud",
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                event_type=AuditEvent.EventType.LEAD_CREATED,
                entity_id=str(appointment.lead_id),
            ).exists()
        )

    def test_webhook_collects_client_data_and_auto_creates_booking(self):
        first_response = self._send_webhook_message("Necesito un electricista en Riomar", chat_id=202)
        self.assertTrue(first_response.json()["ok"])
        self.assertIn("Tecnicos disponibles", first_response.json()["reply"])

        second_response = self._send_webhook_message("1", chat_id=202)
        self.assertIn("Horarios disponibles", second_response.json()["reply"])

        third_response = self._send_webhook_message("1", chat_id=202)
        self.assertIn("nombre completo", third_response.json()["reply"].lower())
        session = ChatSession.objects.get(chat_id=202)
        self.assertEqual(session.current_step, "waiting_contact_name")

        self._send_webhook_message("Laura Diaz", chat_id=202)
        session.refresh_from_db()
        self.assertEqual(session.current_step, "waiting_contact_phone")

        self._send_webhook_message("3001234567", chat_id=202)
        session.refresh_from_db()
        self.assertEqual(session.current_step, "waiting_contact_email")

        self._send_webhook_message("laura@example.com", chat_id=202)
        session.refresh_from_db()
        self.assertEqual(session.current_step, "waiting_contact_address")

        final_response = self._send_webhook_message("Calle 84 # 50-10, Barranquilla", chat_id=202)

        self.assertIn("Cita agendada", final_response.json()["reply"])
        session.refresh_from_db()
        self.assertEqual(session.current_step, "initial")
        self.assertIsNotNone(session.user)
        self.assertEqual(session.user.telegram_chat_id, "202")
        self.assertEqual(session.user.email, "laura@example.com")
        self.assertEqual(session.user.address, "Calle 84 # 50-10, Barranquilla")
        self.assertEqual(Appointment.objects.count(), 1)
        self.assertEqual(ServiceLead.objects.count(), 1)

    def test_webhook_ignores_duplicate_telegram_message_id(self):
        first_response = self._send_webhook_message("Necesito un electricista en Riomar", chat_id=303, message_id=11)
        duplicate_response = self._send_webhook_message("Necesito un electricista en Riomar", chat_id=303, message_id=11)

        self.assertTrue(first_response.json()["ok"])
        self.assertTrue(duplicate_response.json()["ok"])
        self.assertEqual(duplicate_response.json()["ignored"], "duplicate_message")
        session = ChatSession.objects.get(chat_id=303)
        inbound_count = session.messages.filter(direction=ConversationMessage.Direction.INBOUND).count()
        outbound_count = session.messages.filter(direction=ConversationMessage.Direction.OUTBOUND).count()
        self.assertEqual(inbound_count, 1)
        self.assertEqual(outbound_count, 1)

    def test_cancel_from_chat_cancels_upcoming_appointment(self):
        appointment = self._create_appointment(9, 10)

        start_response = self._send_message("Quiero cancelar mi cita")
        self.assertEqual(start_response.status_code, 200)
        self.assertEqual(start_response.json()["step"], "waiting_cancel_confirm")
        self.assertIn("Confirmas la cancelacion?", start_response.json()["reply"])

        confirm_response = self._send_message("SI")

        self.assertEqual(confirm_response.status_code, 200)
        self.assertEqual(confirm_response.json()["step"], "initial")
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CANCELLED)
        self.assertIn("Cita cancelada", confirm_response.json()["reply"])

    def test_reschedule_from_chat_uses_real_slots(self):
        appointment = self._create_appointment(9, 10)

        start_response = self._send_message("Necesito reagendar mi cita")
        self.assertEqual(start_response.status_code, 200)
        self.assertEqual(start_response.json()["step"], "waiting_reschedule_slot_selection")
        self.assertIn("horarios disponibles", start_response.json()["reply"].lower())

        confirm_response = self._send_message("1")

        self.assertEqual(confirm_response.status_code, 200)
        self.assertEqual(confirm_response.json()["step"], "initial")
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.RESCHEDULED)
        self.assertEqual(
            timezone.localtime(appointment.scheduled_start).hour,
            10,
        )
        self.assertIn("Cita reagendada", confirm_response.json()["reply"])

    def _send_message(self, text: str, chat_id: int = 101):
        return self.client.post(
            "/api/chatbot/message/",
            {"chat_id": chat_id, "text": text},
            format="json",
        )

    def _send_webhook_message(self, text: str, chat_id: int = 101, message_id: int | None = None):
        message = {"chat": {"id": chat_id}, "text": text}
        if message_id is not None:
            message["message_id"] = message_id
        return self.webhook_client.post(
            "/api/telegram/webhook/",
            {"message": message},
            format="json",
        )

    def _create_appointment(self, start_hour: int, end_hour: int):
        return Appointment.objects.create(
            client=self.user,
            technician=self.profile,
            service=self.service,
            scheduled_start=self._aware_datetime(self.available_date, start_hour),
            scheduled_end=self._aware_datetime(self.available_date, end_hour),
            status=Appointment.Status.CONFIRMED,
        )

    def _aware_datetime(self, target_date, hour: int):
        return timezone.make_aware(
            datetime.combine(target_date, time(hour, 0)),
            timezone.get_current_timezone(),
        )

    def _next_weekday(self, weekday: int):
        today = timezone.localdate()
        offset = (weekday - today.isoweekday()) % 7
        if offset == 0:
            offset = 7
        return today + timedelta(days=offset)
