from rest_framework import serializers

from .models import Penalty, Rating


class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = ["id", "technician", "client", "service", "score", "comment", "created_at"]
        read_only_fields = ["id", "client", "created_at"]


class PenaltySerializer(serializers.ModelSerializer):
    class Meta:
        model = Penalty
        fields = ["id", "technician", "reason", "points", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]
