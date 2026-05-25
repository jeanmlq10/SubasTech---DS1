from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Auction(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        AWARDED = "awarded", "Awarded"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    class Source(models.TextChoices):
        TELEGRAM = "telegram", "Telegram"
        DASHBOARD = "dashboard", "Dashboard"

    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="auctions")
    category = models.ForeignKey("catalog.Category", on_delete=models.PROTECT, related_name="auctions")
    zone = models.ForeignKey("catalog.Zone", on_delete=models.SET_NULL, null=True, blank=True, related_name="auctions")
    title = models.CharField(max_length=160)
    description = models.TextField()
    location = models.CharField(max_length=160, blank=True)
    urgency = models.CharField(max_length=20, default="normal")
    budget_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    budget_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.DASHBOARD)
    closes_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    winning_bid = models.ForeignKey("auctions.Bid", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["client"], name="auction_client_idx"),
            models.Index(fields=["status"], name="auction_status_idx"),
            models.Index(fields=["category"], name="auction_category_idx"),
        ]

    def __str__(self) -> str:
        return f"Auction #{self.pk or 'new'} - {self.title}"


class Bid(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name="bids")
    technician = models.ForeignKey("catalog.TechnicianProfile", on_delete=models.CASCADE, related_name="bids")
    service = models.ForeignKey("catalog.Service", on_delete=models.SET_NULL, null=True, blank=True, related_name="bids")
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    message = models.TextField(blank=True)
    estimated_minutes = models.PositiveIntegerField(default=60)
    available_from = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["amount", "created_at"]
        constraints = [
            models.UniqueConstraint(fields=["auction", "technician"], name="unique_bid_per_technician_auction"),
        ]
        indexes = [
            models.Index(fields=["auction"], name="bid_auction_idx"),
            models.Index(fields=["technician"], name="bid_technician_idx"),
            models.Index(fields=["status"], name="bid_status_idx"),
        ]

    def __str__(self) -> str:
        return f"Bid #{self.pk or 'new'} - {self.technician} on auction {self.auction_id}"
