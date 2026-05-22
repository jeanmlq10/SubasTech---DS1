from django.contrib import admin

from .models import EscrowPayment, PaymentTransaction


class PaymentTransactionInline(admin.TabularInline):
    model = PaymentTransaction
    extra = 0
    readonly_fields = ["transaction_type", "amount", "status", "provider_reference", "metadata", "created_at"]
    can_delete = False


@admin.register(EscrowPayment)
class EscrowPaymentAdmin(admin.ModelAdmin):
    list_display = ["id", "client", "technician", "total_amount", "deposit_amount", "remaining_amount", "status", "provider", "created_at"]
    list_filter = ["status", "provider", "currency"]
    search_fields = ["client__username", "client__email", "technician__user__username"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [PaymentTransactionInline]


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ["id", "payment", "transaction_type", "amount", "status", "created_at"]
    list_filter = ["transaction_type", "status"]
    readonly_fields = ["created_at"]
