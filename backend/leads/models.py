from django.db import models


class ServiceLead(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        ACCEPTED = "accepted", "Accepted"
        CLOSED = "closed", "Closed"

    class Source(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        TELEGRAM = "telegram", "Telegram"
        DASHBOARD = "dashboard", "Dashboard"

    technician = models.ForeignKey("catalog.TechnicianProfile", on_delete=models.CASCADE, related_name="leads")
    client_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_leads",
    )
    service = models.ForeignKey("catalog.Service", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads")
    client_name = models.CharField(max_length=160, blank=True)
    client_phone = models.CharField(max_length=40)
    message = models.TextField()
    category = models.CharField(max_length=120, blank=True)
    location = models.CharField(max_length=160, blank=True)
    urgency = models.CharField(max_length=20, default="normal")
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.WHATSAPP)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.client_phone} -> {self.technician} ({self.status})"
