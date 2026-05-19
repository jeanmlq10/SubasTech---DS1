from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        CLIENT = "client", "Client"
        TECHNICIAN = "technician", "Technician"
        ADMIN = "admin", "Administrator"
        ARBITER = "arbiter", "Arbiter"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)
    phone_number = models.CharField(max_length=32, blank=True)
    address = models.CharField(max_length=255, blank=True)
    telegram_chat_id = models.CharField(max_length=64, unique=True, blank=True, null=True)
    whatsapp_id = models.CharField(max_length=64, unique=True, blank=True, null=True)

    @property
    def is_technician(self) -> bool:
        return self.role == self.Role.TECHNICIAN
