from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from audit.models import AuditEvent
from audit.services import log_audit_event
from reputation.services import evaluate_automatic_penalties
from .models import ServiceLead
from .serializers import ServiceLeadSerializer, TechnicianLeadStatusSerializer


class TechnicianLeadViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ServiceLeadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        profile = getattr(self.request.user, "technician_profile", None)
        if not profile:
            return ServiceLead.objects.none()
        return ServiceLead.objects.filter(technician=profile).select_related(
            "technician__user",
            "service",
            "appointment__client",
            "appointment__service",
        )

    @action(detail=True, methods=["post"])
    def status(self, request, pk=None):
        lead = self.get_object()
        previous_status = lead.status
        serializer = TechnicianLeadStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead.status = serializer.validated_data["status"]
        lead.save(update_fields=["status", "updated_at"])
        evaluate_automatic_penalties(lead.technician)
        log_audit_event(
            event_type=AuditEvent.EventType.LEAD_STATUS_CHANGED,
            actor=request.user,
            source="technician.leads.status",
            entity_type="lead",
            entity_id=lead.id,
            status="success",
            message="Lead status updated by technician",
            metadata={"previous_status": previous_status, "new_status": lead.status, "technician_id": lead.technician_id},
        )
        return Response(ServiceLeadSerializer(lead).data)
