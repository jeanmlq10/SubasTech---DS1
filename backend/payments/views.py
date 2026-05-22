from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsPlatformArbiter

from .models import EscrowPayment
from .serializers import EscrowPaymentSerializer
from .services import cancel_payment, mark_deposit_paid, mark_remaining_paid, refund_payment, release_payment


def _is_admin(user):
    return user.is_staff or user.is_superuser or getattr(user, "role", "") in {User.Role.ADMIN, User.Role.ARBITER}


class EscrowPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EscrowPaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = EscrowPayment.objects.select_related(
            "appointment", "auction", "bid", "client", "technician__user"
        ).prefetch_related("transactions")
        user = self.request.user
        if _is_admin(user):
            return qs
        if user.role == User.Role.TECHNICIAN:
            profile = getattr(user, "technician_profile", None)
            return qs.filter(technician=profile) if profile else EscrowPayment.objects.none()
        return qs.filter(client=user)

    def _get_payment_for_action(self, pk):
        payment = self.get_object()
        return payment

    @action(detail=True, methods=["post"], url_path="pay-deposit")
    def pay_deposit(self, request, pk=None):
        payment = self.get_object()
        if payment.client_id != request.user.id and not _is_admin(request.user):
            raise PermissionDenied("Solo el cliente puede pagar la reserva.")
        try:
            mark_deposit_paid(payment, actor=request.user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
        return Response(EscrowPaymentSerializer(payment).data)

    @action(detail=True, methods=["post"], url_path="pay-remaining")
    def pay_remaining(self, request, pk=None):
        payment = self.get_object()
        if payment.client_id != request.user.id and not _is_admin(request.user):
            raise PermissionDenied("Solo el cliente puede pagar el saldo restante.")
        try:
            mark_remaining_paid(payment, actor=request.user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
        return Response(EscrowPaymentSerializer(payment).data)

    @action(detail=True, methods=["post"])
    def release(self, request, pk=None):
        if not _is_admin(request.user):
            raise PermissionDenied("Solo admin o árbitro puede liberar un pago manualmente.")
        payment = self.get_object()
        try:
            release_payment(payment, actor=request.user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
        return Response(EscrowPaymentSerializer(payment).data)

    @action(detail=True, methods=["post"])
    def refund(self, request, pk=None):
        if not _is_admin(request.user):
            raise PermissionDenied("Solo admin o árbitro puede emitir reembolsos manualmente.")
        payment = self.get_object()
        reason = request.data.get("reason", "")
        try:
            refund_payment(payment, actor=request.user, reason=reason)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
        return Response(EscrowPaymentSerializer(payment).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        payment = self.get_object()
        if payment.client_id != request.user.id and not _is_admin(request.user):
            raise PermissionDenied("Solo el cliente o admin puede cancelar este pago.")
        reason = request.data.get("reason", "")
        try:
            cancel_payment(payment, actor=request.user, reason=reason)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
        return Response(EscrowPaymentSerializer(payment).data)
