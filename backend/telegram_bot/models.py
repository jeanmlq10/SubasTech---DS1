from django.db import models


class TelegramConversation(models.Model):
    phone_number = models.CharField(max_length=40, unique=True)
    last_message = models.TextField(blank=True)
    last_intent = models.JSONField(default=dict, blank=True)
    last_recommendations = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.phone_number