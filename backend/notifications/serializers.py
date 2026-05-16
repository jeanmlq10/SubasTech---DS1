from django.utils import timezone
from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "message", "channel", "metadata", "is_read", "created_at", "read_at"]
        read_only_fields = ["id", "created_at", "read_at"]

    def update(self, instance, validated_data):
        was_unread = not instance.is_read
        instance = super().update(instance, validated_data)
        if was_unread and instance.is_read and instance.read_at is None:
            instance.read_at = timezone.now()
            instance.save(update_fields=["read_at"])
        return instance
