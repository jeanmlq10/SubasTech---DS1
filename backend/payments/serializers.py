from rest_framework import serializers

from .models import EscrowPayment, PaymentTransaction


class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = ["id", "transaction_type", "amount", "status", "provider_reference", "metadata", "created_at"]
        read_only_fields = fields


class EscrowPaymentSerializer(serializers.ModelSerializer):
    transactions = PaymentTransactionSerializer(many=True, read_only=True)
    client_username = serializers.CharField(source="client.username", read_only=True)
    technician_name = serializers.SerializerMethodField()
    appointment_id = serializers.IntegerField(source="appointment.id", read_only=True, default=None)
    auction_id = serializers.IntegerField(source="auction.id", read_only=True, default=None)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = EscrowPayment
        fields = [
            "id",
            "appointment_id",
            "auction_id",
            "client_username",
            "technician_name",
            "total_amount",
            "deposit_amount",
            "remaining_amount",
            "currency",
            "status",
            "status_display",
            "provider",
            "provider_reference",
            "metadata",
            "transactions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_technician_name(self, obj):
        return obj.technician.user.get_full_name() or obj.technician.user.username
