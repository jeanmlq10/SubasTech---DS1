from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


class User(AbstractUser):
    class TechnicianTrade(models.TextChoices):
        ELECTRICIAN = "electrician", "Electrician"
        PLUMBER = "plumber", "Plumber"
        LOCKSMITH = "locksmith", "Locksmith"
        GENERAL_HANDYMAN = "general-handyman", "General Handyman"

    class Role(models.TextChoices):
        CLIENT = "client", "Client"
        TECHNICIAN = "technician", "Technician"
        ADMIN = "admin", "Administrator"
        ARBITER = "arbiter", "Arbiter"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)
    technician_trade = models.CharField(max_length=40, choices=TechnicianTrade.choices, blank=True)
    phone_number = models.CharField(max_length=32, blank=True)
    address = models.CharField(max_length=255, blank=True)
    telegram_chat_id = models.CharField(max_length=64, unique=True, blank=True, null=True)
    whatsapp_id = models.CharField(max_length=64, unique=True, blank=True, null=True)
    dispute_strikes = models.PositiveSmallIntegerField(default=0)
    auction_blocked = models.BooleanField(default=False)

    @property
    def is_technician(self) -> bool:
        return self.role == self.Role.TECHNICIAN

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                condition=~Q(email=""),
                name="unique_non_blank_user_email_ci",
            )
        ]
