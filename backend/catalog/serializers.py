from rest_framework import serializers

from accounts.serializers import UserSerializer
from .models import Category, Service, ServicePhoto, TechnicianAvailability, TechnicianProfile, Zone


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "is_active"]
        read_only_fields = ["id", "slug"]


class ZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Zone
        fields = ["id", "name", "slug", "city", "is_active"]
        read_only_fields = ["id", "slug"]


class TechnicianAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = TechnicianAvailability
        fields = ["id", "weekday", "start_time", "end_time", "is_active"]
        read_only_fields = ["id"]


class ServicePhotoSerializer(serializers.ModelSerializer):
    service_id = serializers.PrimaryKeyRelatedField(source="service", queryset=Service.objects.all(), write_only=True)

    class Meta:
        model = ServicePhoto
        fields = ["id", "service_id", "image", "caption", "created_at"]
        read_only_fields = ["id", "created_at"]


class TechnicianProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    zone_ids = serializers.PrimaryKeyRelatedField(source="zones", queryset=Zone.objects.all(), many=True, write_only=True, required=False)
    zones = ZoneSerializer(many=True, read_only=True)

    class Meta:
        model = TechnicianProfile
        fields = [
            "id",
            "user",
            "bio",
            "is_verified",
            "availability_status",
            "response_time_minutes",
            "completed_services",
            "service_completion_rate",
            "zones",
            "zone_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_verified", "completed_services", "service_completion_rate", "created_at", "updated_at"]


class ServiceSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(source="category", queryset=Category.objects.all(), write_only=True)
    technician = TechnicianProfileSerializer(read_only=True)
    technician_id = serializers.PrimaryKeyRelatedField(source="technician", queryset=TechnicianProfile.objects.all(), write_only=True)
    photos = ServicePhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Service
        fields = [
            "id",
            "technician",
            "technician_id",
            "category",
            "category_id",
            "title",
            "description",
            "base_price",
            "is_active",
            "photos",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class TechnicianServiceSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(source="category", queryset=Category.objects.filter(is_active=True), write_only=True)
    photos = ServicePhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Service
        fields = [
            "id",
            "category",
            "category_id",
            "title",
            "description",
            "base_price",
            "is_active",
            "photos",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "category", "photos", "created_at", "updated_at"]
