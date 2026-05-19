from rest_framework import permissions, viewsets

from accounts.models import User
from accounts.permissions import IsPlatformAdmin

from .models import AuditEvent
from .serializers import AuditEventSerializer


class AuditEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditEvent.objects.select_related("actor")
    serializer_class = AuditEventSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_staff or user.is_superuser or getattr(user, "role", "") == User.Role.ADMIN:
            return queryset
        return queryset.filter(actor=user)

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [IsPlatformAdmin()]
        return super().get_permissions()
