from rest_framework import serializers

from .models import Penalty, Rating


class RatingSerializer(serializers.ModelSerializer):
    author = serializers.PrimaryKeyRelatedField(read_only=True)
    author_username = serializers.CharField(source="author.username", read_only=True)
    technician_name = serializers.CharField(source="technician.user.username", read_only=True)
    client_username = serializers.CharField(source="client.username", read_only=True)

    class Meta:
        model = Rating
        fields = [
            "id",
            "author",
            "author_username",
            "target_role",
            "technician",
            "technician_name",
            "client",
            "client_username",
            "lead",
            "service",
            "score",
            "comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "author", "author_username", "technician_name", "client_username", "created_at", "updated_at"]

    def validate(self, attrs):
        request = self.context.get("request")
        author = request.user if request else None
        target_role = attrs.get("target_role") or getattr(self.instance, "target_role", None)
        technician = attrs.get("technician") if "technician" in attrs else getattr(self.instance, "technician", None)
        client = attrs.get("client") if "client" in attrs else getattr(self.instance, "client", None)
        service = attrs.get("service") if "service" in attrs else getattr(self.instance, "service", None)
        lead = attrs.get("lead") if "lead" in attrs else getattr(self.instance, "lead", None)

        if target_role == Rating.TargetRole.TECHNICIAN:
            if not technician:
                raise serializers.ValidationError({"technician": "Select a technician to rate."})
            if author and getattr(author, "role", "") != "client":
                raise serializers.ValidationError({"target_role": "Only client users can rate technicians."})
            if service and technician != service.technician:
                raise serializers.ValidationError({"service": "The selected service does not belong to the technician."})
            if lead:
                if lead.technician != technician:
                    raise serializers.ValidationError({"lead": "The selected lead does not belong to the technician."})
                if service and lead.service_id and lead.service_id != service.id:
                    raise serializers.ValidationError({"service": "The selected service does not match the lead."})
                attrs.setdefault("service", lead.service)
            if author:
                duplicate_query = Rating.objects.filter(
                    author=author,
                    technician=technician,
                    service=attrs.get("service", service),
                    target_role=Rating.TargetRole.TECHNICIAN,
                )
                if lead:
                    duplicate_query = duplicate_query.filter(lead=lead)
                else:
                    duplicate_query = duplicate_query.filter(lead__isnull=True)
                if self.instance:
                    duplicate_query = duplicate_query.exclude(pk=self.instance.pk)
                if duplicate_query.exists():
                    raise serializers.ValidationError({"non_field_errors": ["You already rated this technician for the selected interaction."]})
            attrs["client"] = None

        if target_role == Rating.TargetRole.CLIENT:
            if not client:
                raise serializers.ValidationError({"client": "Select a client user to rate."})
            if author and getattr(author, "role", "") != "technician":
                raise serializers.ValidationError({"target_role": "Only technician users can rate clients."})
            if not lead:
                raise serializers.ValidationError({"lead": "Client ratings must reference a service lead."})
            if not hasattr(author, "technician_profile"):
                raise serializers.ValidationError({"target_role": "Complete technician onboarding before rating clients."})
            if lead.technician_id != author.technician_profile.id:
                raise serializers.ValidationError({"lead": "You can only rate clients from your own leads."})
            if not lead.client_user_id or lead.client_user_id != client.id:
                raise serializers.ValidationError({"client": "The selected lead is not linked to that client user."})
            attrs["technician"] = None
            attrs.setdefault("service", lead.service)
            if author:
                duplicate_query = Rating.objects.filter(
                    author=author,
                    client=client,
                    lead=lead,
                    target_role=Rating.TargetRole.CLIENT,
                )
                if self.instance:
                    duplicate_query = duplicate_query.exclude(pk=self.instance.pk)
                if duplicate_query.exists():
                    raise serializers.ValidationError({"non_field_errors": ["You already rated this client for the selected lead."]})

        return attrs


class PenaltySerializer(serializers.ModelSerializer):
    technician_name = serializers.CharField(source="technician.user.username", read_only=True)

    class Meta:
        model = Penalty
        fields = ["id", "technician", "technician_name", "code", "reason", "points", "metadata", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "technician_name", "created_at", "updated_at"]
