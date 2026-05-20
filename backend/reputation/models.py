from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models import Q
from django.db import models


class Rating(models.Model):
    class TargetRole(models.TextChoices):
        TECHNICIAN = "technician", "Technician"
        CLIENT = "client", "Client"

    technician = models.ForeignKey(
        "catalog.TechnicianProfile",
        on_delete=models.CASCADE,
        related_name="ratings",
        null=True,
        blank=True,
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ratings_received",
        null=True,
        blank=True,
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ratings_given")
    service = models.ForeignKey("catalog.Service", on_delete=models.SET_NULL, null=True, blank=True, related_name="ratings")
    lead = models.ForeignKey("leads.ServiceLead", on_delete=models.SET_NULL, null=True, blank=True, related_name="ratings")
    target_role = models.CharField(max_length=20, choices=TargetRole.choices)
    score = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(target_role="technician", technician__isnull=False, client__isnull=True)
                    | Q(target_role="client", technician__isnull=True, client__isnull=False)
                ),
                name="rating_target_matches_role",
            ),
            models.UniqueConstraint(
                fields=["author", "technician", "service", "target_role"],
                condition=Q(target_role="technician", lead__isnull=True),
                name="unique_technician_rating_per_service",
            ),
            models.UniqueConstraint(
                fields=["author", "technician", "lead", "target_role"],
                condition=Q(target_role="technician", lead__isnull=False),
                name="unique_technician_rating_per_lead",
            ),
            models.UniqueConstraint(
                fields=["author", "client", "lead", "target_role"],
                condition=Q(target_role="client"),
                name="unique_client_rating_per_lead",
            ),
        ]

    def clean(self):
        if self.target_role == self.TargetRole.TECHNICIAN and not self.technician_id:
            raise ValidationError({"technician": "Technician ratings must target a technician profile."})
        if self.target_role == self.TargetRole.CLIENT and not self.client_id:
            raise ValidationError({"client": "Client ratings must target a client user."})
        if self.target_role == self.TargetRole.CLIENT and not self.lead_id:
            raise ValidationError({"lead": "Client ratings must be linked to a service lead."})
        if self.service_id and self.lead_id and self.lead and self.lead.service_id and self.lead.service_id != self.service_id:
            raise ValidationError({"service": "The selected service does not match the lead service."})
        if self.target_role == self.TargetRole.TECHNICIAN and self.client_id:
            raise ValidationError({"client": "Technician-target ratings cannot target a client user."})
        if self.target_role == self.TargetRole.CLIENT and self.technician_id:
            raise ValidationError({"technician": "Client-target ratings cannot target a technician profile."})
        if self.author_id and self.client_id and self.author_id == self.client_id:
            raise ValidationError({"client": "A user cannot rate themselves."})
        if self.author_id and self.technician_id and self.technician and self.technician.user_id == self.author_id:
            raise ValidationError({"technician": "A technician cannot rate themselves."})


class Penalty(models.Model):
    class Code(models.TextChoices):
        MANUAL = "manual", "Manual"
        NO_SHOW = "no_show", "No show"
        LATE_CANCELLATION = "late_cancellation", "Late cancellation"
        LOW_REPUTATION = "low_reputation", "Low reputation"
        LOST_DISPUTE = "lost_dispute", "Lost dispute"

    technician = models.ForeignKey("catalog.TechnicianProfile", on_delete=models.CASCADE, related_name="penalties")
    code = models.CharField(max_length=32, choices=Code.choices, default=Code.MANUAL)
    reason = models.CharField(max_length=180)
    points = models.PositiveSmallIntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
