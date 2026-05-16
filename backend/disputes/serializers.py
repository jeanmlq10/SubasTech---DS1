from rest_framework import serializers

from .models import Dispute, DisputeEvidence


class DisputeEvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisputeEvidence
        fields = ["id", "uploaded_by", "file", "note", "created_at"]
        read_only_fields = ["id", "uploaded_by", "created_at"]


class DisputeSerializer(serializers.ModelSerializer):
    evidence = DisputeEvidenceSerializer(many=True, read_only=True)

    class Meta:
        model = Dispute
        fields = [
            "id",
            "client",
            "technician",
            "service",
            "title",
            "description",
            "ai_summary",
            "priority",
            "status",
            "decision",
            "arbiter",
            "arbiter_notes",
            "evidence",
            "created_at",
            "updated_at",
            "resolved_at",
        ]
        read_only_fields = ["id", "client", "ai_summary", "arbiter", "created_at", "updated_at", "resolved_at"]


class ArbiterDisputeSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.username", read_only=True)
    technician_name = serializers.SerializerMethodField()
    service_title = serializers.CharField(source="service.title", read_only=True)
    evidence = DisputeEvidenceSerializer(many=True, read_only=True)
    assistant = serializers.SerializerMethodField()

    class Meta:
        model = Dispute
        fields = [
            "id",
            "client_name",
            "technician_name",
            "service_title",
            "title",
            "description",
            "ai_summary",
            "assistant",
            "priority",
            "status",
            "decision",
            "arbiter",
            "arbiter_notes",
            "evidence",
            "created_at",
            "updated_at",
            "resolved_at",
        ]
        read_only_fields = fields

    def get_technician_name(self, obj):
        return obj.technician.user.get_full_name() or obj.technician.user.username

    def get_assistant(self, obj):
        from .services import build_dispute_assistant_payload

        return build_dispute_assistant_payload(obj)


class ArbiterDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(
        choices=[
            Dispute.Decision.FAVOR_CLIENT,
            Dispute.Decision.FAVOR_TECHNICIAN,
            Dispute.Decision.PARTIAL,
        ]
    )
    notes = serializers.CharField(required=False, allow_blank=True)
