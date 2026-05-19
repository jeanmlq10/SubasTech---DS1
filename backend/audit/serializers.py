from rest_framework import serializers

from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "event_type",
            "actor",
            "actor_username",
            "channel",
            "source",
            "entity_type",
            "entity_id",
            "status",
            "message",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields
