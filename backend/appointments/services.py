"""Service layer for appointment scheduling and lifecycle management.

Conventions
-----------
* All write operations run inside ``transaction.atomic()``.
* Concurrency safety relies on a ``SELECT FOR UPDATE`` lock on the relevant
  ``catalog.TechnicianProfile`` row, then on the ``Appointment`` row. Callers
  do not have to acquire these locks manually; the service functions do it
  on their behalf. SQLite silently ignores ``select_for_update``; on
  PostgreSQL it serializes concurrent booking attempts against the same
  technician (so the conflict check + INSERT/UPDATE happen as one logical
  step). The lock order is always: technician -> appointment.
* Validation errors are raised as :class:`django.core.exceptions.ValidationError`
  with a structured ``{"<field>": "<message>"}`` payload, mirroring the
  convention used in :meth:`reputation.models.Rating.clean` and
  :meth:`appointments.models.Appointment.clean`.
* Audit events, dashboard notifications, lead synchronization and reputation
  refresh are emitted from this module and never from views, so every entry
  point (REST viewset, management command, WhatsApp pipeline) gets the same
  side effects.
* This module never imports DRF; raised exceptions are framework-agnostic
  Django core ``ValidationError`` instances.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from appointments.models import Appointment
from audit.services import log_audit_event
from catalog.models import Service, TechnicianAvailability, TechnicianProfile
from leads.models import ServiceLead
from notifications.models import Notification
from reputation.services import (
    evaluate_automatic_penalties,
    refresh_technician_reputation,
)

# Cancellations strictly before this many hours from scheduled_start are
# considered "early" and do not trigger an automatic penalty; on or after the
# threshold they are "late" and feed the existing reputation engine.
LATE_CANCELLATION_THRESHOLD_HOURS = 24

# Audit event types. AuditEvent.event_type is a CharField(max_length=40) whose
# choices act as form-level hints (not DB constraints), so adding appointment
# event values here is safe and additive. Promoting them to AuditEvent.EventType
# enum members is a future, isolated change to the audit app.
AUDIT_EVENT_APPOINTMENT_CREATED = "appointment_created"
AUDIT_EVENT_APPOINTMENT_CANCELLED = "appointment_cancelled"
AUDIT_EVENT_APPOINTMENT_RESCHEDULED = "appointment_rescheduled"
AUDIT_EVENT_APPOINTMENT_COMPLETED = "appointment_completed"
AUDIT_EVENT_APPOINTMENT_NO_SHOW = "appointment_no_show"

_TERMINAL_STATUSES = frozenset(
    {
        Appointment.Status.CANCELLED,
        Appointment.Status.COMPLETED,
        Appointment.Status.NO_SHOW,
    }
)


# ---------------------------------------------------------------------------
# Pure helpers (no side effects, safe to call outside a transaction)
# ---------------------------------------------------------------------------

def check_technician_conflict(
    technician: TechnicianProfile,
    scheduled_start: datetime,
    scheduled_end: datetime,
    *,
    exclude_appointment_id: int | None = None,
) -> bool:
    """Return ``True`` if *technician* already has an active appointment
    overlapping the half-open window ``[scheduled_start, scheduled_end)``.

    Only :data:`Appointment.ACTIVE_STATUSES` are considered; cancelled,
    completed and no-show appointments are ignored. Pass
    ``exclude_appointment_id`` to skip the current appointment when
    rescheduling.

    The function is read-only and never starts a transaction. For race-safe
    booking, callers (``create_appointment`` and ``reschedule_appointment``)
    invoke it after acquiring a ``SELECT FOR UPDATE`` lock on the
    technician row.
    """
    queryset = Appointment.objects.filter(
        technician=technician,
        status__in=Appointment.ACTIVE_STATUSES,
        scheduled_start__lt=scheduled_end,
        scheduled_end__gt=scheduled_start,
    )
    if exclude_appointment_id is not None:
        queryset = queryset.exclude(pk=exclude_appointment_id)
    return queryset.exists()


def is_within_availability(
    technician: TechnicianProfile,
    scheduled_start: datetime,
    scheduled_end: datetime,
) -> bool:
    """Return ``True`` if the proposed time window fits entirely inside one of
    the technician's active :class:`catalog.TechnicianAvailability` windows.

    Availability windows are stored as ``(weekday, start_time, end_time)`` in
    local time (``settings.TIME_ZONE``), so the check converts the incoming
    datetimes to local time before comparing.

    Cross-midnight bookings are unsupported (the underlying schema uses
    ``TimeField``); the window must start and end on the same local
    calendar day.

    This function deliberately does NOT consult
    ``TechnicianProfile.availability_status`` -- that flag is a soft signal
    consumed by the recommender, not a booking constraint.
    """
    if scheduled_end <= scheduled_start:
        return False

    local_start = _to_local(scheduled_start)
    local_end = _to_local(scheduled_end)

    if local_start.date() != local_end.date():
        return False

    weekday = local_start.isoweekday()  # Monday=1 .. Sunday=7

    return TechnicianAvailability.objects.filter(
        technician=technician,
        is_active=True,
        weekday=weekday,
        start_time__lte=local_start.time(),
        end_time__gte=local_end.time(),
    ).exists()


def compute_cancellation_timing(
    appointment: Appointment,
    *,
    now: datetime | None = None,
) -> str:
    """Return either ``Appointment.CancellationTiming.EARLY`` or ``LATE``.

    The cut-off is :data:`LATE_CANCELLATION_THRESHOLD_HOURS` hours before
    ``appointment.scheduled_start``. Cancelling at or after the cut-off
    (including after the appointment has already started) is "late".
    """
    reference = now if now is not None else timezone.now()
    threshold = appointment.scheduled_start - timedelta(
        hours=LATE_CANCELLATION_THRESHOLD_HOURS
    )
    if reference < threshold:
        return Appointment.CancellationTiming.EARLY
    return Appointment.CancellationTiming.LATE


# ---------------------------------------------------------------------------
# Lifecycle transitions (all transactional, all side-effecting)
# ---------------------------------------------------------------------------

def create_appointment(
    *,
    client,
    technician: TechnicianProfile,
    scheduled_start: datetime,
    scheduled_end: datetime,
    service: Service | None = None,
    lead: ServiceLead | None = None,
    status: str = Appointment.Status.CONFIRMED,
    metadata: dict | None = None,
    actor=None,
) -> Appointment:
    """Create an appointment after enforcing availability and conflict checks.

    Side effects:

    * emits an ``appointment_created`` audit event;
    * synchronizes the linked ``ServiceLead`` status (PENDING -> CONTACTED,
      CONFIRMED/RESCHEDULED -> ACCEPTED);
    * creates dashboard notifications for both the client and the
      technician's user.

    Permission/role enforcement (e.g. "only client users may create") belongs
    in the view layer; this function only validates data integrity.
    """
    if scheduled_end <= scheduled_start:
        raise ValidationError(
            {"scheduled_end": "scheduled_end must be greater than scheduled_start."}
        )

    if service is not None and service.technician_id != technician.pk:
        raise ValidationError(
            {"service": "The service does not belong to the selected technician."}
        )

    if lead is not None and lead.technician_id != technician.pk:
        raise ValidationError(
            {"lead": "The lead does not belong to the selected technician."}
        )

    with transaction.atomic():
        locked_technician = _lock_technician(technician.pk)

        if not is_within_availability(
            locked_technician, scheduled_start, scheduled_end
        ):
            raise ValidationError(
                {
                    "scheduled_start": (
                        "The technician has no active availability window "
                        "covering that time slot."
                    )
                }
            )

        if check_technician_conflict(
            locked_technician, scheduled_start, scheduled_end
        ):
            raise ValidationError(
                {
                    "scheduled_start": (
                        "Technician already has an active appointment "
                        "overlapping that window."
                    )
                }
            )

        appointment = Appointment.objects.create(
            client=client,
            technician=locked_technician,
            service=service,
            lead=lead,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            status=status,
            metadata=dict(metadata) if metadata else {},
        )

        # Re-fetch with related objects so downstream helpers do not trigger
        # extra queries (technician__user, client, lead are touched below).
        appointment = (
            Appointment.objects.select_related(
                "technician__user", "client", "service", "lead"
            ).get(pk=appointment.pk)
        )

        _sync_lead_for_appointment(appointment)
        _log_lifecycle_event(
            appointment,
            event_type=AUDIT_EVENT_APPOINTMENT_CREATED,
            actor=actor if actor is not None else client,
            source="appointments.create",
            message="Appointment created",
        )
        _notify_participants(
            appointment,
            title="Cita creada",
            message=(
                f"Se creo una cita para el "
                f"{_format_local(appointment.scheduled_start)}."
            ),
            event_type=AUDIT_EVENT_APPOINTMENT_CREATED,
        )

    return appointment


def cancel_appointment(
    appointment: Appointment,
    *,
    actor,
    reason: str = "",
    now: datetime | None = None,
) -> Appointment:
    """Transition *appointment* to ``CANCELLED``.

    Computes the cancellation timing (``EARLY``/``LATE``), mirrors the
    "late" signal onto the linked ``ServiceLead.metadata`` so that the
    existing reputation rules in ``reputation.services`` keep working, and
    invokes :func:`evaluate_automatic_penalties` to refresh the technician's
    reputation snapshot.
    """
    with transaction.atomic():
        _lock_technician(appointment.technician_id)
        locked = _lock_appointment(appointment.pk)

        if locked.status in _TERMINAL_STATUSES:
            raise ValidationError(
                {
                    "status": (
                        f"Cannot cancel an appointment in status "
                        f"'{locked.status}'."
                    )
                }
            )

        timing = compute_cancellation_timing(locked, now=now)
        locked.status = Appointment.Status.CANCELLED
        locked.cancellation_reason = reason
        locked.cancellation_timing = timing
        locked.save(
            update_fields=[
                "status",
                "cancellation_reason",
                "cancellation_timing",
                "updated_at",
            ]
        )

        _sync_lead_for_appointment(
            locked,
            late_cancellation=timing == Appointment.CancellationTiming.LATE,
        )
        _log_lifecycle_event(
            locked,
            event_type=AUDIT_EVENT_APPOINTMENT_CANCELLED,
            actor=actor,
            source="appointments.cancel",
            message="Appointment cancelled",
            extra_metadata={
                "reason": reason,
                "cancellation_timing": timing,
            },
        )
        _notify_participants(
            locked,
            title="Cita cancelada",
            message=(
                f"La cita del {_format_local(locked.scheduled_start)} "
                "fue cancelada."
            ),
            event_type=AUDIT_EVENT_APPOINTMENT_CANCELLED,
        )
        evaluate_automatic_penalties(locked.technician)

    return locked


def reschedule_appointment(
    appointment: Appointment,
    *,
    actor,
    new_start: datetime,
    new_end: datetime,
    reason: str = "",
) -> Appointment:
    """Move *appointment* to a new time window and mark it ``RESCHEDULED``.

    Enforces the same availability and conflict checks as
    :func:`create_appointment`, excluding the appointment itself from the
    overlap query so it can be "moved in place".
    """
    if new_end <= new_start:
        raise ValidationError(
            {"new_end": "new_end must be greater than new_start."}
        )

    with transaction.atomic():
        _lock_technician(appointment.technician_id)
        locked = _lock_appointment(appointment.pk)

        if locked.status in _TERMINAL_STATUSES:
            raise ValidationError(
                {
                    "status": (
                        f"Cannot reschedule an appointment in status "
                        f"'{locked.status}'."
                    )
                }
            )

        if not is_within_availability(locked.technician, new_start, new_end):
            raise ValidationError(
                {
                    "new_start": (
                        "The technician has no active availability window "
                        "covering that time slot."
                    )
                }
            )

        if check_technician_conflict(
            locked.technician,
            new_start,
            new_end,
            exclude_appointment_id=locked.pk,
        ):
            raise ValidationError(
                {
                    "new_start": (
                        "Technician already has an active appointment "
                        "overlapping that window."
                    )
                }
            )

        previous_start = locked.scheduled_start
        previous_end = locked.scheduled_end
        locked.scheduled_start = new_start
        locked.scheduled_end = new_end
        locked.status = Appointment.Status.RESCHEDULED
        locked.reschedule_reason = reason
        locked.save(
            update_fields=[
                "scheduled_start",
                "scheduled_end",
                "status",
                "reschedule_reason",
                "updated_at",
            ]
        )

        _sync_lead_for_appointment(locked)
        _log_lifecycle_event(
            locked,
            event_type=AUDIT_EVENT_APPOINTMENT_RESCHEDULED,
            actor=actor,
            source="appointments.reschedule",
            message="Appointment rescheduled",
            extra_metadata={
                "reason": reason,
                "previous_start": previous_start.isoformat(),
                "previous_end": previous_end.isoformat(),
            },
        )
        _notify_participants(
            locked,
            title="Cita reagendada",
            message=(
                f"La cita fue reagendada al "
                f"{_format_local(locked.scheduled_start)}."
            ),
            event_type=AUDIT_EVENT_APPOINTMENT_RESCHEDULED,
        )

    return locked


def complete_appointment(
    appointment: Appointment,
    *,
    actor,
) -> Appointment:
    """Transition *appointment* to ``COMPLETED`` and refresh reputation.

    Sets the linked lead to ``CLOSED`` and tags ``lead.metadata.outcome``
    with ``"completed"`` so dashboards can distinguish completed visits from
    cancellations or no-shows. Reputation counters are recomputed via
    :func:`refresh_technician_reputation` (no new penalty signal here).
    """
    with transaction.atomic():
        _lock_technician(appointment.technician_id)
        locked = _lock_appointment(appointment.pk)

        if locked.status in _TERMINAL_STATUSES:
            raise ValidationError(
                {
                    "status": (
                        f"Cannot complete an appointment in status "
                        f"'{locked.status}'."
                    )
                }
            )

        locked.status = Appointment.Status.COMPLETED
        locked.save(update_fields=["status", "updated_at"])

        _sync_lead_for_appointment(locked)
        _log_lifecycle_event(
            locked,
            event_type=AUDIT_EVENT_APPOINTMENT_COMPLETED,
            actor=actor,
            source="appointments.complete",
            message="Appointment completed",
        )
        _notify_participants(
            locked,
            title="Cita completada",
            message=(
                f"La cita del {_format_local(locked.scheduled_start)} se "
                "marco como completada."
            ),
            event_type=AUDIT_EVENT_APPOINTMENT_COMPLETED,
        )
        refresh_technician_reputation(locked.technician)

    return locked


def mark_no_show(
    appointment: Appointment,
    *,
    actor,
    reason: str = "",
) -> Appointment:
    """Transition *appointment* to ``NO_SHOW`` and trigger penalty evaluation.

    Mirrors the ``outcome="no_show"`` flag onto the linked
    ``ServiceLead.metadata`` so the existing rule in
    :func:`reputation.services.evaluate_automatic_penalties` produces the
    ``Penalty.Code.NO_SHOW`` entry without any change to the reputation
    module.

    Per the product spec this transition does NOT create dashboard
    notifications (only ``created``, ``cancelled``, ``rescheduled`` and
    ``completed`` do).
    """
    with transaction.atomic():
        _lock_technician(appointment.technician_id)
        locked = _lock_appointment(appointment.pk)

        if locked.status in _TERMINAL_STATUSES:
            raise ValidationError(
                {
                    "status": (
                        f"Cannot mark no-show on an appointment in status "
                        f"'{locked.status}'."
                    )
                }
            )

        metadata = dict(locked.metadata or {})
        if reason:
            metadata["no_show_reason"] = reason
        locked.status = Appointment.Status.NO_SHOW
        locked.metadata = metadata
        locked.save(update_fields=["status", "metadata", "updated_at"])

        _sync_lead_for_appointment(locked)
        _log_lifecycle_event(
            locked,
            event_type=AUDIT_EVENT_APPOINTMENT_NO_SHOW,
            actor=actor,
            source="appointments.no_show",
            message="Appointment marked as no-show",
            extra_metadata={"reason": reason} if reason else None,
        )
        evaluate_automatic_penalties(locked.technician)

    return locked


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _lock_technician(technician_id: int) -> TechnicianProfile:
    """Acquire a row lock on the technician profile and return it.

    ``select_related("user")`` is kept tight here because downstream helpers
    (notifications, lead sync) only need ``technician.user_id``, which is
    already on the row.
    """
    return (
        TechnicianProfile.objects.select_for_update()
        .select_related("user")
        .get(pk=technician_id)
    )


def _lock_appointment(appointment_id: int) -> Appointment:
    """Acquire a row lock on the appointment and pre-fetch its related rows.

    The ``select_related`` chain matches the joins used by audit, lead-sync
    and notification helpers, so a single query is enough to drive the rest
    of the transition.
    """
    return (
        Appointment.objects.select_for_update()
        .select_related("technician__user", "client", "service", "lead")
        .get(pk=appointment_id)
    )


def _to_local(value: datetime) -> datetime:
    """Return *value* converted to the project's default timezone.

    Naive datetimes are interpreted as being in the current timezone; this
    matches Django's behavior under ``USE_TZ=True`` and keeps the function
    robust against callers that forget to localize.
    """
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    return timezone.localtime(value)


def _format_local(value: datetime) -> str:
    return _to_local(value).strftime("%Y-%m-%d %H:%M")


def _sync_lead_for_appointment(
    appointment: Appointment,
    *,
    late_cancellation: bool = False,
) -> None:
    """Mirror the appointment outcome onto the linked ``ServiceLead``.

    The existing reputation engine (``reputation.services``) reads
    ``lead.metadata`` flags (``outcome``, ``cancellation_timing``) and counts
    leads with ``status=CLOSED`` as completed services. Mirroring appointment
    outcomes into those exact fields lets the existing rules keep working
    without modifying the reputation module.

    No-op when the appointment has no linked lead.
    """
    if not appointment.lead_id:
        return

    lead = appointment.lead
    metadata = dict(lead.metadata or {})
    metadata_changed = False
    new_status: str | None

    status = appointment.status
    if status == Appointment.Status.PENDING:
        new_status = ServiceLead.Status.CONTACTED
    elif status in (
        Appointment.Status.CONFIRMED,
        Appointment.Status.RESCHEDULED,
    ):
        new_status = ServiceLead.Status.ACCEPTED
    elif status == Appointment.Status.COMPLETED:
        new_status = ServiceLead.Status.CLOSED
        if metadata.get("outcome") != "completed":
            metadata["outcome"] = "completed"
            metadata_changed = True
    elif status == Appointment.Status.CANCELLED:
        new_status = ServiceLead.Status.CLOSED
        if late_cancellation and metadata.get("cancellation_timing") != "late":
            metadata["cancellation_timing"] = "late"
            metadata_changed = True
    elif status == Appointment.Status.NO_SHOW:
        new_status = ServiceLead.Status.CLOSED
        if metadata.get("outcome") != "no_show":
            metadata["outcome"] = "no_show"
            metadata_changed = True
    else:
        return

    status_changed = lead.status != new_status
    if not status_changed and not metadata_changed:
        return

    update_fields = ["updated_at"]
    if status_changed:
        lead.status = new_status
        update_fields.append("status")
    if metadata_changed:
        lead.metadata = metadata
        update_fields.append("metadata")
    lead.save(update_fields=update_fields)


def _log_lifecycle_event(
    appointment: Appointment,
    *,
    event_type: str,
    actor,
    source: str,
    message: str,
    status: str = "success",
    extra_metadata: dict | None = None,
) -> None:
    """Emit an :class:`audit.models.AuditEvent` for a lifecycle transition.

    Metadata shape matches the existing convention used by
    ``disputes/views.py`` and ``leads/views.py`` (snake_case keys, plain
    JSON values).
    """
    metadata: dict = {
        "appointment_status": appointment.status,
        "technician_id": appointment.technician_id,
        "client_id": appointment.client_id,
        "service_id": appointment.service_id,
        "lead_id": appointment.lead_id,
        "scheduled_start": appointment.scheduled_start.isoformat(),
        "scheduled_end": appointment.scheduled_end.isoformat(),
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    log_audit_event(
        event_type=event_type,
        actor=actor,
        source=source,
        entity_type="appointment",
        entity_id=appointment.id,
        status=status,
        message=message,
        metadata=metadata,
    )


def _notify_participants(
    appointment: Appointment,
    *,
    title: str,
    message: str,
    event_type: str,
) -> None:
    """Create dashboard notifications for the client and the technician's user.

    Issues a single ``bulk_create`` to avoid N+1 inserts. The technician's
    ``user_id`` is read off the already-prefetched relation, so no extra
    query is generated.
    """
    technician_user_id = (
        appointment.technician.user_id if appointment.technician_id else None
    )
    recipient_ids: Iterable[int] = {
        user_id
        for user_id in (appointment.client_id, technician_user_id)
        if user_id
    }
    if not recipient_ids:
        return

    metadata = {
        "appointment_id": appointment.id,
        "event_type": event_type,
        "status": appointment.status,
        "scheduled_start": appointment.scheduled_start.isoformat(),
    }
    Notification.objects.bulk_create(
        [
            Notification(
                user_id=user_id,
                title=title,
                message=message,
                channel=Notification.Channel.DASHBOARD,
                metadata=metadata,
            )
            for user_id in recipient_ids
        ]
    )
