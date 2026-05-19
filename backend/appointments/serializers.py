"""DRF serializers for the appointments module.

These serializers intentionally stay thin: they only validate payload shape
and basic field-level integrity (e.g. ``scheduled_end > scheduled_start``,
FK ownership, non-empty reasons). All business logic — availability checks,
double-booking detection, lead synchronization, audit, notifications and
reputation updates — lives in :mod:`appointments.services` and is invoked
from the view layer by passing ``serializer.validated_data`` into the
appropriate service function.

The style mirrors the existing modules:

* the read serializer (``AppointmentSerializer``) is a ``ModelSerializer``
  with denormalized ``*_name`` / ``*_username`` / ``*_title`` display fields,
  matching :class:`leads.serializers.ServiceLeadSerializer` and
  :class:`disputes.serializers.ArbiterDisputeSerializer`;
* every lifecycle transition has its own dedicated ``Serializer`` subclass
  (analogous to :class:`leads.serializers.TechnicianLeadStatusSerializer`
  and :class:`disputes.serializers.ArbiterDecisionSerializer`).
"""
from django.utils import timezone
from rest_framework import serializers

from catalog.models import (
    Category,
    Service,
    TechnicianProfile,
    Zone,
)
from leads.models import ServiceLead

from .models import Appointment


# ---------------------------------------------------------------------------
# Read serializer
# ---------------------------------------------------------------------------

class AppointmentSerializer(serializers.ModelSerializer):
    """Read-only serializer used for list/retrieve responses.

    All fields are read-only on purpose: every mutation goes through a
    dedicated action serializer + the matching ``appointments.services``
    entry point, so the main serializer never needs to accept writes.
    """

    technician_name = serializers.SerializerMethodField()
    client_username = serializers.CharField(source="client.username", read_only=True)
    service_title = serializers.CharField(source="service.title", read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "client",
            "client_username",
            "technician",
            "technician_name",
            "service",
            "service_title",
            "lead",
            "scheduled_start",
            "scheduled_end",
            "status",
            "cancellation_reason",
            "cancellation_timing",
            "reschedule_reason",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_technician_name(self, obj):
        return obj.technician.user.get_full_name() or obj.technician.user.username


# ---------------------------------------------------------------------------
# Action serializers (one per lifecycle transition)
# ---------------------------------------------------------------------------

class AppointmentCreateSerializer(serializers.Serializer):
    """Payload schema for :func:`appointments.services.create_appointment`.

    The ``client`` is always the request user and is therefore set by the
    view, not accepted from the payload (mirrors how
    :class:`disputes.serializers.DisputeSerializer` keeps ``client`` read-only).
    """

    technician = serializers.PrimaryKeyRelatedField(
        queryset=TechnicianProfile.objects.all()
    )
    service = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all(),
        required=False,
        allow_null=True,
        default=None,
    )
    lead = serializers.PrimaryKeyRelatedField(
        queryset=ServiceLead.objects.all(),
        required=False,
        allow_null=True,
        default=None,
    )
    scheduled_start = serializers.DateTimeField()
    scheduled_end = serializers.DateTimeField()
    status = serializers.ChoiceField(
        choices=Appointment.Status.choices,
        required=False,
        default=Appointment.Status.CONFIRMED,
    )
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_scheduled_start(self, value):
        if timezone.is_naive(value):
            raise serializers.ValidationError(
                "scheduled_start must be timezone-aware."
            )
        return value

    def validate_scheduled_end(self, value):
        if timezone.is_naive(value):
            raise serializers.ValidationError(
                "scheduled_end must be timezone-aware."
            )
        return value

    def validate(self, attrs):
        if attrs["scheduled_end"] <= attrs["scheduled_start"]:
            raise serializers.ValidationError(
                {"scheduled_end": "scheduled_end must be greater than scheduled_start."}
            )

        technician = attrs["technician"]
        service = attrs.get("service")
        lead = attrs.get("lead")

        if service is not None and service.technician_id != technician.pk:
            raise serializers.ValidationError(
                {"service": "The service does not belong to the selected technician."}
            )
        if lead is not None and lead.technician_id != technician.pk:
            raise serializers.ValidationError(
                {"lead": "The lead does not belong to the selected technician."}
            )
        return attrs


class AppointmentCancelSerializer(serializers.Serializer):
    """Payload schema for :func:`appointments.services.cancel_appointment`."""

    cancellation_reason = serializers.CharField()

    def validate_cancellation_reason(self, value):
        cleaned = value.strip() if isinstance(value, str) else value
        if not cleaned:
            raise serializers.ValidationError(
                "cancellation_reason cannot be empty."
            )
        return cleaned


class AppointmentRescheduleSerializer(serializers.Serializer):
    """Payload schema for :func:`appointments.services.reschedule_appointment`.

    The view is responsible for translating the validated fields into the
    service kwargs (``new_start``, ``new_end``, ``reason``).
    """

    scheduled_start = serializers.DateTimeField()
    scheduled_end = serializers.DateTimeField()
    reschedule_reason = serializers.CharField()

    def validate_scheduled_start(self, value):
        if timezone.is_naive(value):
            raise serializers.ValidationError(
                "scheduled_start must be timezone-aware."
            )
        return value

    def validate_scheduled_end(self, value):
        if timezone.is_naive(value):
            raise serializers.ValidationError(
                "scheduled_end must be timezone-aware."
            )
        return value

    def validate_reschedule_reason(self, value):
        cleaned = value.strip() if isinstance(value, str) else value
        if not cleaned:
            raise serializers.ValidationError(
                "reschedule_reason cannot be empty."
            )
        return cleaned

    def validate(self, attrs):
        if attrs["scheduled_end"] <= attrs["scheduled_start"]:
            raise serializers.ValidationError(
                {"scheduled_end": "scheduled_end must be greater than scheduled_start."}
            )
        return attrs


class AppointmentCompleteSerializer(serializers.Serializer):
    """Payload schema for :func:`appointments.services.complete_appointment`.

    The service function takes no additional input beyond the actor and the
    appointment instance, so this serializer accepts an empty body. It
    exists to give the view layer a uniform pattern across lifecycle
    transitions and a forward-compatible hook for future fields
    (e.g. completion notes).
    """

    pass


class AppointmentNoShowSerializer(serializers.Serializer):
    """Payload schema for :func:`appointments.services.mark_no_show`.

    Mirrors the optional ``reason`` kwarg the service function already
    supports (stored as ``appointment.metadata['no_show_reason']`` when
    non-empty).
    """

    reason = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_reason(self, value):
        return value.strip() if isinstance(value, str) else value


class AvailableSlotsQuerySerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    days = serializers.IntegerField(required=False, min_value=1, max_value=14, default=7)
    slot_minutes = serializers.IntegerField(required=False, min_value=15, max_value=240, default=60)
    service_id = serializers.PrimaryKeyRelatedField(
        source="service",
        queryset=Service.objects.all(),
        required=False,
        allow_null=True,
        default=None,
    )
    category_id = serializers.PrimaryKeyRelatedField(
        source="category",
        queryset=Category.objects.filter(is_active=True),
        required=False,
        allow_null=True,
        default=None,
    )
    zone_id = serializers.PrimaryKeyRelatedField(
        source="zone",
        queryset=Zone.objects.filter(is_active=True),
        required=False,
        allow_null=True,
        default=None,
    )


class AvailableSlotSerializer(serializers.Serializer):
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
