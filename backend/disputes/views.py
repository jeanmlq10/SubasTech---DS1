from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsPlatformArbiter
from .models import Dispute
from .serializers import ArbiterDecisionSerializer, ArbiterDisputeSerializer, DisputeSerializer
from .services import summarize_dispute


class DisputeViewSet(viewsets.ModelViewSet):
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
        serializer.save(client=self.request.user, ai_summary=summarize_dispute(description))


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
        return Response(ArbiterDisputeSerializer(dispute).data)
