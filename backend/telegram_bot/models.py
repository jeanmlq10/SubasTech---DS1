from django.conf import settings
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


class ChatSession(models.Model):
    chat_id = models.BigIntegerField(unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="telegram_chat_sessions",
    )
    current_step = models.CharField(max_length=50, default="initial")
    state_data = models.JSONField(default=dict)
    last_telegram_message_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"ChatSession {self.chat_id} ({self.current_step})"


class ConversationMessage(models.Model):
    class Direction(models.TextChoices):
        INBOUND = "inbound", "Inbound"
        OUTBOUND = "outbound", "Outbound"

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    direction = models.CharField(max_length=10, choices=Direction.choices)
    text = models.TextField()
    intent = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self) -> str:
        return f"{self.direction} @ {self.timestamp:%Y-%m-%d %H:%M}"
