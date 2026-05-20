"""DRF view layer for the appointments module.

This module keeps views thin: every state mutation delegates to a function
in :mod:`appointments.services`, which is the single source of truth for
business logic (availability/overlap checks, audit, notifications, lead
synchronization and reputation refresh).

The viewset follows the conventions of :class:`disputes.views.DisputeViewSet`
(role-filtered ``get_queryset``, per-action permissions via
``get_permissions``, ``@action(detail=True, methods=["post"])`` for state
transitions) and :class:`leads.views.TechnicianLeadViewSet` (single-word
action calling a service helper and returning the serialized object).
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError as DRFValidationError,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsPlatformAdmin
from catalog.models import TechnicianProfile

from .models import Appointment
from .permissions import IsAppointmentParticipantOrAdmin
from .serializers import (
    AvailableSlotSerializer,
    AvailableSlotsQuerySerializer,
    AppointmentCancelSerializer,
    AppointmentCompleteSerializer,
    AppointmentCreateSerializer,
    AppointmentNoShowSerializer,
    AppointmentRescheduleSerializer,
    AppointmentSerializer,
)
from .services import (
    cancel_appointment,
    complete_appointment,
    create_appointment,
    get_available_slots,
    mark_no_show,
    reschedule_appointment,
)


def _execute_service(fn, **kwargs):
    """Invoke a service function and translate Django's ``ValidationError`` into
    DRF's structured 400 response.

    Service functions raise ``django.core.exceptions.ValidationError`` with a
    dict payload (see :meth:`reputation.models.Rating.clean` for the same
    convention). DRF does not auto-convert those when raised from a view body,
    so the view re-raises them as :class:`rest_framework.exceptions.ValidationError`
    to keep the on-the-wire error shape consistent with the rest of the API.
    """
    try:
        return fn(**kwargs)
    except DjangoValidationError as exc:
        detail = exc.message_dict if hasattr(exc, "error_dict") else exc.messages
        raise DRFValidationError(detail) from exc


class AppointmentViewSet(viewsets.ModelViewSet):
    """CRUD + lifecycle transitions for ``Appointment``.

    Mutations should be performed through the dedicated ``@action`` endpoints
    (``cancel``, ``reschedule``, ``complete``, ``no_show``); the default
    ``update``/``partial_update``/``destroy`` routes are gated to platform
    administrators and exist for moderation only.
    """

    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer

    _ACTION_SERIALIZERS = {
        "create": AppointmentCreateSerializer,
        "cancel": AppointmentCancelSerializer,
        "reschedule": AppointmentRescheduleSerializer,
        "complete": AppointmentCompleteSerializer,
        "no_show": AppointmentNoShowSerializer,
    }

    # ------------------------------------------------------------------ DRF hooks

    def get_serializer_class(self):
        return self._ACTION_SERIALIZERS.get(self.action, AppointmentSerializer)

    def get_permissions(self):
        if self.action in {"update", "partial_update", "destroy"}:
            return [IsPlatformAdmin()]
        if self.action in {
            "retrieve",
            "cancel",
            "reschedule",
            "confirm_complete",
            "complete",
            "no_show",
        }:
            return [IsAuthenticated(), IsAppointmentParticipantOrAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = Appointment.objects.select_related(
            "technician__user",
            "client",
            "service",
            "lead",
        )
        user = self.request.user
        role = getattr(user, "role", "")
        is_admin = (
            user.is_staff
            or user.is_superuser
            or role == User.Role.ADMIN
        )

        if is_admin:
            scoped = queryset
        elif role == User.Role.TECHNICIAN:
            scoped = queryset.filter(technician__user=user)
        elif role == User.Role.CLIENT:
            scoped = queryset.filter(client=user)
        else:
            return Appointment.objects.none()

        return self._apply_query_filters(scoped, is_admin=is_admin)

    # ------------------------------------------------------------------ create

    def create(self, request, *args, **kwargs):
        self._require_client_or_admin(request.user)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        appointment = _execute_service(
            create_appointment,
            client=request.user,
            actor=request.user,
            **serializer.validated_data,
        )
        return Response(
            AppointmentSerializer(
                appointment, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )

    # ------------------------------------------------------------------ transitions

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        appointment = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = _execute_service(
            cancel_appointment,
            appointment=appointment,
            actor=request.user,
            reason=serializer.validated_data["cancellation_reason"],
        )
        return self._render(updated)

    @action(detail=True, methods=["post"])
    def reschedule(self, request, pk=None):
        appointment = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = _execute_service(
            reschedule_appointment,
            appointment=appointment,
            actor=request.user,
            new_start=serializer.validated_data["scheduled_start"],
            new_end=serializer.validated_data["scheduled_end"],
            reason=serializer.validated_data["reschedule_reason"],
        )
        return self._render(updated)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        appointment = self.get_object()
        self._require_technician_actor(request.user, appointment)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = _execute_service(
            complete_appointment,
            appointment=appointment,
            actor=request.user,
        )
        return self._render(updated)

    @action(detail=True, methods=["post"])
    def confirm_complete(self, request, pk=None):
        appointment = self.get_object()
        self._require_client_actor(request.user, appointment)
        serializer = AppointmentCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = _execute_service(
            complete_appointment,
            appointment=appointment,
            actor=request.user,
        )
        return self._render(updated)

    @action(detail=True, methods=["post"])
    def no_show(self, request, pk=None):
        appointment = self.get_object()
        self._require_technician_actor(request.user, appointment)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = _execute_service(
            mark_no_show,
            appointment=appointment,
            actor=request.user,
            reason=serializer.validated_data.get("reason", ""),
        )
        return self._render(updated)

    # ------------------------------------------------------------------ helpers

    def _apply_query_filters(self, queryset, *, is_admin: bool):
        """Lightweight query-param filtering. Keeps the codebase free of
        ``django-filter`` while mirroring how :class:`disputes.views.ArbiterQueueAPIView`
        consumes request params manually.
        """
        params = self.request.query_params

        statuses = [s for s in (params.get("status") or "").split(",") if s]
        if statuses:
            queryset = queryset.filter(status__in=statuses)

        if is_admin and params.get("technician"):
            try:
                queryset = queryset.filter(technician_id=int(params["technician"]))
            except (TypeError, ValueError):
                pass

        if params.get("service"):
            try:
                queryset = queryset.filter(service_id=int(params["service"]))
            except (TypeError, ValueError):
                pass

        if params.get("date_from"):
            parsed = parse_datetime(params["date_from"])
            if parsed is not None:
                queryset = queryset.filter(scheduled_start__gte=parsed)

        if params.get("date_to"):
            parsed = parse_datetime(params["date_to"])
            if parsed is not None:
                queryset = queryset.filter(scheduled_start__lte=parsed)

        return queryset

    def _require_client_or_admin(self, user):
        role = getattr(user, "role", "")
        if user.is_staff or user.is_superuser or role in {
            User.Role.CLIENT,
            User.Role.ADMIN,
        }:
            return
        raise PermissionDenied(
            "Only client users or administrators can create appointments."
        )

    def _require_technician_actor(self, user, appointment):
        if (
            user.is_staff
            or user.is_superuser
            or getattr(user, "role", "") == User.Role.ADMIN
        ):
            return
        if appointment.technician.user_id == user.id:
            return
        raise PermissionDenied(
            "Only the assigned technician or an administrator can perform this action."
        )

    def _require_client_actor(self, user, appointment):
        if (
            user.is_staff
            or user.is_superuser
            or getattr(user, "role", "") == User.Role.ADMIN
        ):
            return
        if appointment.client_id == user.id:
            return
        raise PermissionDenied(
            "Only the appointment client or an administrator can perform this action."
        )

    def _render(self, appointment):
        return Response(
            AppointmentSerializer(
                appointment, context=self.get_serializer_context()
            ).data
        )


class TechnicianAvailableSlotsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        technician = get_object_or_404(
            TechnicianProfile.objects.select_related("user").prefetch_related("zones"),
            pk=pk,
        )
        serializer = AvailableSlotsQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        slots = _execute_service(
            get_available_slots,
            technician=technician,
            **serializer.validated_data,
        )
        effective_start_date = serializer.validated_data.get(
            "start_date",
            timezone.localdate(),
        )
        return Response(
            {
                "technician": technician.id,
                "availability_status": technician.availability_status,
                "start_date": effective_start_date,
                "days": serializer.validated_data["days"],
                "slot_minutes": serializer.validated_data["slot_minutes"],
                "slots": AvailableSlotSerializer(slots, many=True).data,
            }
        )
