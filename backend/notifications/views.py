from rest_framework import permissions, viewsets

from accounts.models import User
from accounts.permissions import IsPlatformAdmin
from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser or getattr(user, "role", "") == User.Role.ADMIN:
            return Notification.objects.all()
        return Notification.objects.filter(user=user)

    def get_permissions(self):
        if self.action == "create":
            return [IsPlatformAdmin()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        target_user_id = self.request.data.get("user")
        if not target_user_id:
            serializer.save(user=self.request.user)
            return
        serializer.save(user_id=target_user_id)
