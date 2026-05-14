from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import ServiceLead
from .serializers import ServiceLeadSerializer, TechnicianLeadStatusSerializer


class TechnicianLeadViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ServiceLeadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        profile = getattr(self.request.user, "technician_profile", None)
        if not profile:
            return ServiceLead.objects.none()
        return ServiceLead.objects.filter(technician=profile).select_related("technician__user", "service")

    @action(detail=True, methods=["post"])
    def status(self, request, pk=None):
        lead = self.get_object()
        serializer = TechnicianLeadStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead.status = serializer.validated_data["status"]
        lead.save(update_fields=["status", "updated_at"])
        return Response(ServiceLeadSerializer(lead).data)
