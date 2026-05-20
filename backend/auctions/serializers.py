from rest_framework import serializers

from accounts.models import User
from catalog.models import Category, Service, TechnicianProfile, Zone

from .models import Auction, Bid


class BidSerializer(serializers.ModelSerializer):
    auction_title = serializers.CharField(source="auction.title", read_only=True)
    technician_name = serializers.SerializerMethodField()
    service_title = serializers.CharField(source="service.title", read_only=True)

    class Meta:
        model = Bid
        fields = [
            "id",
            "auction",
            "auction_title",
            "technician",
            "technician_name",
            "service",
            "service_title",
            "amount",
            "message",
            "estimated_minutes",
            "available_from",
            "status",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "auction_title",
            "technician",
            "technician_name",
            "service_title",
            "status",
            "metadata",
            "created_at",
            "updated_at",
        ]

    def get_technician_name(self, obj):
        return obj.technician.user.get_full_name() or obj.technician.user.username

    def validate_auction(self, value):
        if value.status != Auction.Status.OPEN:
            raise serializers.ValidationError("Only open auctions can receive bids.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        profile = getattr(user, "technician_profile", None)
        service = attrs.get("service")

        if not user or user.role != User.Role.TECHNICIAN or not profile:
            raise serializers.ValidationError("Only technicians can create bids.")
        if not profile.is_verified:
            raise serializers.ValidationError("Only verified technicians can create bids.")
        if service is not None and service.technician_id != profile.id:
            raise serializers.ValidationError({"service": "The service must belong to the authenticated technician."})
        return attrs


class AuctionSerializer(serializers.ModelSerializer):
    client_username = serializers.CharField(source="client.username", read_only=True)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.filter(is_active=True))
    category_name = serializers.CharField(source="category.name", read_only=True)
    zone = serializers.PrimaryKeyRelatedField(queryset=Zone.objects.filter(is_active=True), required=False, allow_null=True)
    zone_name = serializers.CharField(source="zone.name", read_only=True)
    bids = serializers.SerializerMethodField()

    class Meta:
        model = Auction
        fields = [
            "id",
            "client",
            "client_username",
            "category",
            "category_name",
            "zone",
            "zone_name",
            "title",
            "description",
            "location",
            "urgency",
            "budget_min",
            "budget_max",
            "status",
            "source",
            "closes_at",
            "winning_bid",
            "metadata",
            "bids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "client",
            "client_username",
            "category_name",
            "zone_name",
            "status",
            "source",
            "winning_bid",
            "metadata",
            "bids",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        budget_min = attrs.get("budget_min")
        budget_max = attrs.get("budget_max")
        if budget_min is not None and budget_max is not None and budget_max < budget_min:
            raise serializers.ValidationError({"budget_max": "budget_max must be greater than or equal to budget_min."})
        return attrs

    def get_bids(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        bids = obj.bids.all()
        if user and user.role == User.Role.TECHNICIAN and not user.is_staff and not user.is_superuser:
            profile = getattr(user, "technician_profile", None)
            bids = bids.filter(technician=profile) if profile else bids.none()
        return BidSerializer(bids, many=True, context=self.context).data


class AuctionAwardSerializer(serializers.Serializer):
    bid_id = serializers.PrimaryKeyRelatedField(queryset=Bid.objects.select_related("auction", "technician", "service"))
