from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    class EventType(models.TextChoices):
        WEBHOOK_RECEIVED = "webhook_received", "Webhook received"
        MESSAGE_SENT = "message_sent", "Message sent"
        LEAD_CREATED = "lead_created", "Lead created"
        LEAD_STATUS_CHANGED = "lead_status_changed", "Lead status changed"
        DISPUTE_CREATED = "dispute_created", "Dispute created"
        DISPUTE_CLAIMED = "dispute_claimed", "Dispute claimed"
        DISPUTE_RESOLVED = "dispute_resolved", "Dispute resolved"
        ADMIN_ACTION = "admin_action", "Admin action"
        INTEGRATION_ERROR = "integration_error", "Integration error"

    event_type = models.CharField(max_length=40, choices=EventType.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    channel = models.CharField(max_length=40, blank=True)
    source = models.CharField(max_length=80, blank=True)
    entity_type = models.CharField(max_length=80, blank=True)
    entity_id = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=20, default="info")
    message = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.event_type}: {self.message}"
