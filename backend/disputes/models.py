from django.conf import settings
from django.db import models
from django.utils import timezone


class Dispute(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_REVIEW = "in_review", "In review"
        RESOLVED = "resolved", "Resolved"
        REJECTED = "rejected", "Rejected"

    class Decision(models.TextChoices):
        PENDING = "pending", "Pending"
        FAVOR_CLIENT = "favor_client", "Favor client"
        FAVOR_TECHNICIAN = "favor_technician", "Favor technician"
        PARTIAL = "partial", "Partial resolution"

    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="client_disputes")
    technician = models.ForeignKey("catalog.TechnicianProfile", on_delete=models.CASCADE, related_name="disputes")
    service = models.ForeignKey("catalog.Service", on_delete=models.SET_NULL, null=True, blank=True, related_name="disputes")
    title = models.CharField(max_length=180)
    description = models.TextField()
    ai_summary = models.TextField(blank=True)
    priority = models.CharField(max_length=20, default="normal")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    decision = models.CharField(max_length=24, choices=Decision.choices, default=Decision.PENDING)
    arbiter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_disputes")
    arbiter_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def resolve(self, decision: str, arbiter, notes: str = ""):
        self.decision = decision
        self.status = self.Status.RESOLVED
        self.arbiter = arbiter
        self.arbiter_notes = notes
        self.resolved_at = timezone.now()
        self.save(update_fields=["decision", "status", "arbiter", "arbiter_notes", "resolved_at", "updated_at"])


class DisputeEvidence(models.Model):
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name="evidence")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dispute_evidence")
    file = models.FileField(upload_to="dispute-evidence/", blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
