from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsPlatformArbiter
from audit.models import AuditEvent
from audit.services import log_audit_event
from payments.models import EscrowPayment
from payments.services import hold_for_dispute, refund_payment, release_payment
from reputation.services import evaluate_automatic_penalties
from .models import Dispute
from .serializers import ArbiterDecisionSerializer, ArbiterDisputeSerializer, DisputeEvidenceSerializer, DisputeSerializer
from .services import summarize_dispute


DISPUTE_STRIKE_THRESHOLD = 3


def _hold_payment_for_dispute(dispute: "Dispute") -> None:
    payment = EscrowPayment.objects.filter(
        client=dispute.client,
        technician=dispute.technician,
    ).exclude(
        status__in=[EscrowPayment.Status.RELEASED, EscrowPayment.Status.REFUNDED, EscrowPayment.Status.CANCELLED]
    ).order_by("-created_at").first()
    if payment:
        hold_for_dispute(payment, dispute)


def _settle_payment_for_dispute(dispute: "Dispute", actor) -> None:
    payment = EscrowPayment.objects.filter(
        client=dispute.client,
        technician=dispute.technician,
        status=EscrowPayment.Status.DISPUTED,
    ).order_by("-created_at").first()
    if payment is None:
        return
    if dispute.decision == Dispute.Decision.FAVOR_TECHNICIAN:
        release_payment(payment, actor=actor)
    elif dispute.decision in {Dispute.Decision.FAVOR_CLIENT, Dispute.Decision.PARTIAL}:
        refund_payment(payment, actor=actor, reason=f"dispute:{dispute.decision}")


def _apply_client_dispute_strike(dispute: "Dispute") -> None:
    if dispute.decision != Dispute.Decision.FAVOR_TECHNICIAN:
        return
    client = dispute.client
    client.dispute_strikes = (client.dispute_strikes or 0) + 1
    if client.dispute_strikes >= DISPUTE_STRIKE_THRESHOLD:
        client.auction_blocked = True
    client.save(update_fields=["dispute_strikes", "auction_blocked"])


class DisputeViewSet(viewsets.ModelViewSet):
    queryset = Dispute.objects.all()
    serializer_class = DisputeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Dispute.objects.select_related("client", "technician__user", "service", "arbiter").prefetch_related("evidence")
        user = self.request.user

        if user.is_staff or user.is_superuser or getattr(user, "role", "") in {User.Role.ADMIN, User.Role.ARBITER}:
            return queryset
        if getattr(user, "role", "") == User.Role.TECHNICIAN:
            return queryset.filter(technician__user=user)
        return queryset.filter(client=user)

    def perform_create(self, serializer):
        if self.request.user.role != User.Role.CLIENT:
            raise PermissionDenied("Only client users can open disputes.")
        description = serializer.validated_data.get("description", "")
        dispute = serializer.save(client=self.request.user, ai_summary=summarize_dispute(description))
        _hold_payment_for_dispute(dispute)
        log_audit_event(
            event_type=AuditEvent.EventType.DISPUTE_CREATED,
            actor=self.request.user,
            source="disputes.create",
            entity_type="dispute",
            entity_id=dispute.id,
            status="success",
            message="Dispute created by client",
            metadata={"technician_id": dispute.technician_id, "service_id": dispute.service_id},
        )

    @action(detail=True, methods=["post"])
    def evidence(self, request, pk=None):
        dispute = self.get_object()
        if dispute.status == Dispute.Status.RESOLVED:
            return Response({"detail": "Resolved disputes cannot receive more evidence."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = DisputeEvidenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(dispute=dispute, uploaded_by=request.user)
        log_audit_event(
            event_type=AuditEvent.EventType.ADMIN_ACTION,
            actor=request.user,
            source="disputes.evidence",
            entity_type="dispute",
            entity_id=dispute.id,
            status="success",
            message="Dispute evidence added",
            metadata={"dispute_id": dispute.id, "role": getattr(request.user, "role", "")},
        )
        dispute.refresh_from_db()
        return Response(DisputeSerializer(dispute, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED)


class ArbiterQueueAPIView(APIView):
    permission_classes = [IsPlatformArbiter]

    def get(self, request):
        queryset = self._queue_queryset(request.user)
        metrics = {
            "open": queryset.filter(status=Dispute.Status.OPEN).count(),
            "in_review": queryset.filter(status=Dispute.Status.IN_REVIEW).count(),
            "resolved_by_me": Dispute.objects.filter(status=Dispute.Status.RESOLVED, arbiter=request.user).count(),
            "high_priority": queryset.filter(priority="high").count(),
        }
        by_status = {
            row["status"]: row["total"]
            for row in queryset.values("status").annotate(total=Count("id"))
        }
        return Response(
            {
                "metrics": metrics,
                "by_status": by_status,
                "disputes": ArbiterDisputeSerializer(queryset.order_by("-created_at"), many=True).data,
            }
        )

    def _queue_queryset(self, user):
        queryset = Dispute.objects.select_related("client", "technician__user", "service", "arbiter").prefetch_related("evidence")
        if user.is_staff or user.is_superuser or getattr(user, "role", "") == "admin":
            return queryset.filter(status__in=[Dispute.Status.OPEN, Dispute.Status.IN_REVIEW])
        return queryset.filter(
            Q(status=Dispute.Status.OPEN, arbiter__isnull=True)
            | Q(status=Dispute.Status.IN_REVIEW, arbiter=user)
        )


class ArbiterDecisionAPIView(APIView):
    permission_classes = [IsPlatformArbiter]

    def post(self, request, pk: int):
        dispute = get_object_or_404(
            Dispute.objects.select_related("client", "technician__user", "service", "arbiter"),
            pk=pk,
        )
        serializer = ArbiterDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if dispute.status == Dispute.Status.RESOLVED:
            return Response({"detail": "This dispute is already resolved."}, status=status.HTTP_400_BAD_REQUEST)

        dispute.resolve(
            decision=serializer.validated_data["decision"],
            arbiter=request.user,
            notes=serializer.validated_data.get("notes", ""),
        )
        evaluate_automatic_penalties(dispute.technician)
        _apply_client_dispute_strike(dispute)
        _settle_payment_for_dispute(dispute, actor=request.user)
        log_audit_event(
            event_type=AuditEvent.EventType.DISPUTE_RESOLVED,
            actor=request.user,
            source="arbiter.disputes.decision",
            entity_type="dispute",
            entity_id=dispute.id,
            status="success",
            message="Dispute resolved by arbiter",
            metadata={
                "decision": dispute.decision,
                "technician_id": dispute.technician_id,
                "client_strikes": dispute.client.dispute_strikes,
                "client_blocked": dispute.client.auction_blocked,
            },
        )
        return Response(ArbiterDisputeSerializer(dispute).data)


class ArbiterClaimAPIView(APIView):
    permission_classes = [IsPlatformArbiter]

    def post(self, request, pk: int):
        dispute = get_object_or_404(Dispute, pk=pk)
        if dispute.status == Dispute.Status.RESOLVED:
            return Response({"detail": "Resolved disputes cannot be claimed."}, status=status.HTTP_400_BAD_REQUEST)
        dispute.status = Dispute.Status.IN_REVIEW
        dispute.arbiter = request.user
        dispute.save(update_fields=["status", "arbiter", "updated_at"])
        log_audit_event(
            event_type=AuditEvent.EventType.DISPUTE_CLAIMED,
            actor=request.user,
            source="arbiter.disputes.claim",
            entity_type="dispute",
            entity_id=dispute.id,
            status="success",
            message="Dispute claimed by arbiter",
            metadata={"technician_id": dispute.technician_id},
        )
        return Response(ArbiterDisputeSerializer(dispute).data)
