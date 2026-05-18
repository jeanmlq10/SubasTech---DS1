from rest_framework import serializers

from .models import ServiceLead


class ServiceLeadSerializer(serializers.ModelSerializer):
    technician_name = serializers.SerializerMethodField()
    service_title = serializers.CharField(source="service.title", read_only=True)
    client_username = serializers.CharField(source="client_user.username", read_only=True)

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
            "created_at",
            "updated_at",
        ]

    def get_technician_name(self, obj):
        return obj.technician.user.get_full_name() or obj.technician.user.username


class TechnicianLeadStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ServiceLead.Status.choices)
