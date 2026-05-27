from rest_framework import serializers

from .models import ServiceLead


class ServiceLeadSerializer(serializers.ModelSerializer):
    technician_name = serializers.SerializerMethodField()
    service_title = serializers.CharField(
        source="service.title", read_only=True)
    client_username = serializers.CharField(
        source="client_user.username", read_only=True)
    appointment = serializers.SerializerMethodField()

    class Meta:
        model = ServiceLead
        fields = [
            "id",
            "technician",
            "technician_name",
            "client_user",
            "client_username",
            "service",
            "service_title",
            "client_name",
            "client_phone",
            "message",
            "category",
            "location",
            "urgency",
            "source",
            "status",
            "metadata",
            "appointment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "technician",
            "technician_name",
            "client_user",
            "client_username",
            "service_title",
            "source",
            "metadata",
            "appointment",
            "created_at",
            "updated_at",
        ]

    def get_technician_name(self, obj):
        return obj.technician.user.get_full_name() or obj.technician.user.username

    def get_appointment(self, obj):
        appointment = getattr(obj, "appointment", None)
        if appointment is None:
            return None

        metadata = appointment.metadata or {}
        return {
            "id": appointment.id,
            "scheduled_start": appointment.scheduled_start,
            "scheduled_end": appointment.scheduled_end,
            "status": appointment.status,
            "technician_status": metadata.get("technician_status") or "",
            "service_title": appointment.service.title if appointment.service_id else (obj.service.title if obj.service_id else ""),
            "client_name": appointment.client.get_full_name() or appointment.client.username,
            "client_address": metadata.get("client_address") or getattr(appointment.client, "address", ""),
            "request_text": metadata.get("request_text") or obj.message,
            "location": metadata.get("location") or obj.location,
            "created_at": appointment.created_at,
            "updated_at": appointment.updated_at,
        }


class TechnicianLeadStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ServiceLead.Status.choices)
