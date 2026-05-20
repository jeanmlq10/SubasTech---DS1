from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Appointment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        RESCHEDULED = "rescheduled", "Rescheduled"
        COMPLETED = "completed", "Completed"
        NO_SHOW = "no_show", "No show"

    class CancellationTiming(models.TextChoices):
        EARLY = "early", "Early"
        LATE = "late", "Late"

    # Statuses that occupy a calendar slot. Used by Python-level overlap
    # validation and reserved for a future PostgreSQL ExclusionConstraint.
    ACTIVE_STATUSES = (Status.PENDING, Status.CONFIRMED, Status.RESCHEDULED)

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="appointments_as_client",
    )
    technician = models.ForeignKey(
        "catalog.TechnicianProfile",
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    service = models.ForeignKey(
        "catalog.Service",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )
    lead = models.OneToOneField(
        "leads.ServiceLead",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointment",
    )
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    cancellation_reason = models.TextField(blank=True)
    cancellation_timing = models.CharField(
        max_length=10,
        choices=CancellationTiming.choices,
        blank=True,
    )
    reschedule_reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-scheduled_start"]
        verbose_name = "appointment"
        verbose_name_plural = "appointments"
        indexes = [
            models.Index(fields=["technician"], name="appointment_techni_idx"),
            models.Index(fields=["scheduled_start"], name="appointment_start_idx"),
            models.Index(fields=["status"], name="appointment_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(scheduled_end__gt=models.F("scheduled_start")),
                name="appointment_end_after_start",
            ),
        ]

    def __str__(self) -> str:
        return f"Appointment #{self.pk or 'new'} ({self.status})"

    def clean(self):
        super().clean()
        if (
            self.scheduled_start
            and self.scheduled_end
            and self.scheduled_end <= self.scheduled_start
        ):
            raise ValidationError(
                {"scheduled_end": "scheduled_end must be greater than scheduled_start."}
            )

        if (
            self.technician_id
            and self.scheduled_start
            and self.scheduled_end
            and self.status in self.ACTIVE_STATUSES
        ):
            overlapping = Appointment.objects.filter(
                technician_id=self.technician_id,
                status__in=self.ACTIVE_STATUSES,
                scheduled_start__lt=self.scheduled_end,
                scheduled_end__gt=self.scheduled_start,
            )
            if self.pk:
                overlapping = overlapping.exclude(pk=self.pk)
            if overlapping.exists():
                raise ValidationError(
                    {
                        "scheduled_start": (
                            "Technician already has an active appointment overlapping that window."
                        )
                    }
                )
