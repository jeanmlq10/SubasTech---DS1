from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from audit.models import AuditEvent
from catalog.models import (
    Category,
    Service,
    TechnicianAvailability,
    TechnicianProfile,
    Zone,
)

from .models import Appointment


class AppointmentWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()

        self.client_user = user_model.objects.create_user(
            username="appointment-client",
            password="Password123",
            role="client",
        )
        self.other_client = user_model.objects.create_user(
            username="appointment-client-2",
            password="Password123",
            role="client",
        )
        self.tech_user = user_model.objects.create_user(
            username="appointment-tech",
            password="Password123",
            role="technician",
            first_name="Laura",
            last_name="Gomez",
        )
        self.other_tech_user = user_model.objects.create_user(
            username="appointment-tech-2",
            password="Password123",
            role="technician",
            first_name="Pedro",
            last_name="Vega",
        )

        self.category = Category.objects.create(
            name="Electricista citas",
            slug="electricista-citas",
        )
        self.other_category = Category.objects.create(
            name="Plomero citas",
            slug="plomero-citas",
        )
        self.zone = Zone.objects.create(name="Riomar", city="Barranquilla")
        self.other_zone = Zone.objects.create(name="Norte Centro", city="Barranquilla")

        self.profile = TechnicianProfile.objects.create(
            user=self.tech_user,
            is_verified=True,
            availability_status=TechnicianProfile.AvailabilityStatus.AVAILABLE,
        )
        self.profile.zones.add(self.zone)
        self.other_profile = TechnicianProfile.objects.create(
            user=self.other_tech_user,
            is_verified=True,
            availability_status=TechnicianProfile.AvailabilityStatus.AVAILABLE,
        )
        self.other_profile.zones.add(self.other_zone)

        self.service = Service.objects.create(
            technician=self.profile,
            category=self.category,
            title="Reparacion electrica",
            description="Diagnostico y reparacion general.",
            base_price=90000,
        )
        self.other_service = Service.objects.create(
            technician=self.other_profile,
            category=self.other_category,
            title="Reparacion hidraulica",
            description="Servicio alterno.",
            base_price=70000,
        )

        self.available_date = self._next_weekday(1)
        TechnicianAvailability.objects.create(
            technician=self.profile,
            weekday=self.available_date.isoweekday(),
            start_time=time(9, 0),
            end_time=time(12, 0),
            is_active=True,
        )
        TechnicianAvailability.objects.create(
            technician=self.other_profile,
            weekday=self.available_date.isoweekday(),
            start_time=time(14, 0),
            end_time=time(17, 0),
            is_active=True,
        )

    def test_client_can_create_appointment(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/appointments/",
            {
                "technician": self.profile.id,
                "service": self.service.id,
                "scheduled_start": self._aware_datetime(self.available_date, 9).isoformat(),
                "scheduled_end": self._aware_datetime(self.available_date, 10).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        appointment = Appointment.objects.get()
        self.assertEqual(appointment.client, self.client_user)
        self.assertEqual(appointment.technician, self.profile)
        self.assertEqual(appointment.status, Appointment.Status.CONFIRMED)
        self.assertTrue(
            AuditEvent.objects.filter(
                event_type="appointment_created",
                entity_id=str(appointment.id),
            ).exists()
        )

    def test_double_booking_is_rejected(self):
        Appointment.objects.create(
            client=self.other_client,
            technician=self.profile,
            service=self.service,
            scheduled_start=self._aware_datetime(self.available_date, 10),
            scheduled_end=self._aware_datetime(self.available_date, 11),
            status=Appointment.Status.CONFIRMED,
        )
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/appointments/",
            {
                "technician": self.profile.id,
                "service": self.service.id,
                "scheduled_start": self._aware_datetime(self.available_date, 10, 30).isoformat(),
                "scheduled_end": self._aware_datetime(self.available_date, 11, 30).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("scheduled_start", response.json())

    def test_client_can_cancel_appointment(self):
        appointment = self._create_appointment(
            client=self.client_user,
            start_hour=9,
            end_hour=10,
        )
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            f"/api/appointments/{appointment.id}/cancel/",
            {"cancellation_reason": "Cambio de planes"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CANCELLED)
        self.assertEqual(appointment.cancellation_reason, "Cambio de planes")
        self.assertEqual(
            appointment.cancellation_timing,
            Appointment.CancellationTiming.EARLY,
        )

    def test_client_can_reschedule_appointment(self):
        appointment = self._create_appointment(
            client=self.client_user,
            start_hour=9,
            end_hour=10,
        )
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            f"/api/appointments/{appointment.id}/reschedule/",
            {
                "scheduled_start": self._aware_datetime(self.available_date, 11).isoformat(),
                "scheduled_end": self._aware_datetime(self.available_date, 12).isoformat(),
                "reschedule_reason": "Me queda mejor mas tarde",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.RESCHEDULED)
        self.assertEqual(appointment.reschedule_reason, "Me queda mejor mas tarde")
        self.assertEqual(appointment.scheduled_start, self._aware_datetime(self.available_date, 11))

    def test_client_can_confirm_appointment_complete(self):
        appointment = self._create_appointment(
            client=self.client_user,
            start_hour=9,
            end_hour=10,
        )
        self.client.force_authenticate(self.client_user)

        response = self.client.post(f"/api/appointments/{appointment.id}/confirm_complete/", {}, format="json")

        self.assertEqual(response.status_code, 200)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.COMPLETED)

    def test_other_client_cannot_confirm_appointment_complete(self):
        appointment = self._create_appointment(
            client=self.client_user,
            start_hour=9,
            end_hour=10,
        )
        self.client.force_authenticate(self.other_client)

        response = self.client.post(f"/api/appointments/{appointment.id}/confirm_complete/", {}, format="json")

        self.assertEqual(response.status_code, 404)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CONFIRMED)

    def test_client_only_sees_own_appointments(self):
        own_appointment = self._create_appointment(
            client=self.client_user,
            start_hour=9,
            end_hour=10,
        )
        self._create_appointment(
            client=self.other_client,
            start_hour=10,
            end_hour=11,
        )
        self.client.force_authenticate(self.client_user)

        response = self.client.get("/api/appointments/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["id"], own_appointment.id)

    def test_technician_only_sees_assigned_appointments(self):
        own_appointment = self._create_appointment(
            client=self.client_user,
            start_hour=9,
            end_hour=10,
        )
        Appointment.objects.create(
            client=self.other_client,
            technician=self.other_profile,
            service=self.other_service,
            scheduled_start=self._aware_datetime(self.available_date, 14),
            scheduled_end=self._aware_datetime(self.available_date, 15),
            status=Appointment.Status.CONFIRMED,
        )
        self.client.force_authenticate(self.tech_user)

        response = self.client.get("/api/appointments/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["id"], own_appointment.id)

    def test_available_slots_endpoint_excludes_conflicts(self):
        self._create_appointment(
            client=self.other_client,
            start_hour=10,
            end_hour=11,
        )
        self.client.force_authenticate(self.client_user)

        response = self.client.get(
            f"/api/technicians/{self.profile.id}/available-slots/",
            {
                "start_date": self.available_date.isoformat(),
                "days": 1,
                "slot_minutes": 60,
                "service_id": self.service.id,
                "category_id": self.category.id,
                "zone_id": self.zone.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["technician"], self.profile.id)
        self.assertEqual(body["slot_minutes"], 60)
        self.assertEqual(len(body["slots"]), 2)
        returned_starts = {
            datetime.fromisoformat(slot["start"].replace("Z", "+00:00"))
            for slot in body["slots"]
        }
        self.assertIn(
            self._aware_datetime(self.available_date, 9),
            returned_starts,
        )
        self.assertIn(
            self._aware_datetime(self.available_date, 11),
            returned_starts,
        )

    def test_available_slots_returns_empty_for_zone_mismatch(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get(
            f"/api/technicians/{self.profile.id}/available-slots/",
            {
                "start_date": self.available_date.isoformat(),
                "days": 1,
                "zone_id": self.other_zone.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["slots"], [])

    def _create_appointment(self, *, client, start_hour: int, end_hour: int):
        return Appointment.objects.create(
            client=client,
            technician=self.profile,
            service=self.service,
            scheduled_start=self._aware_datetime(self.available_date, start_hour),
            scheduled_end=self._aware_datetime(self.available_date, end_hour),
            status=Appointment.Status.CONFIRMED,
        )

    def _aware_datetime(self, target_date, hour: int, minute: int = 0):
        return timezone.make_aware(
            datetime.combine(target_date, time(hour, minute)),
            timezone.get_current_timezone(),
        )

    def _next_weekday(self, weekday: int):
        today = timezone.localdate()
        offset = (weekday - today.isoweekday()) % 7
        if offset == 0:
            offset = 7
        return today + timedelta(days=offset)
