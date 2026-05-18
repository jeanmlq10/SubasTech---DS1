from django.db.models import Q
from rest_framework import permissions, viewsets

from accounts.models import User
from accounts.permissions import IsPlatformAdmin
from .models import Penalty, Rating
from .services import evaluate_automatic_penalties, refresh_technician_reputation
from .serializers import PenaltySerializer, RatingSerializer


class RatingViewSet(viewsets.ModelViewSet):
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Rating.objects.select_related("author", "technician__user", "client", "service", "lead")
        user = self.request.user
        if user.is_staff or user.is_superuser or getattr(user, "role", "") == User.Role.ADMIN:
            return queryset
        if getattr(user, "role", "") == User.Role.TECHNICIAN:
            return queryset.filter(Q(author=user) | Q(technician__user=user) | Q(client=user)).distinct()
        return queryset.filter(Q(author=user) | Q(client=user)).distinct()

    def perform_create(self, serializer):
        rating = serializer.save(author=self.request.user)
        profile = rating.technician or (rating.lead.technician if rating.lead_id else None)
        if profile:
            evaluate_automatic_penalties(profile)

    def perform_destroy(self, instance):
        profile = instance.technician or (instance.lead.technician if instance.lead_id else None)
        instance.delete()
        if profile:
            evaluate_automatic_penalties(profile)


class PenaltyViewSet(viewsets.ModelViewSet):
    queryset = Penalty.objects.all()
    serializer_class = PenaltySerializer

    def get_queryset(self):
        queryset = Penalty.objects.select_related("technician__user")
        user = self.request.user
        if user.is_staff or user.is_superuser or getattr(user, "role", "") == User.Role.ADMIN:
            return queryset
        if getattr(user, "role", "") == User.Role.TECHNICIAN and hasattr(user, "technician_profile"):
            return queryset.filter(technician=user.technician_profile)
        return queryset.none()

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsPlatformAdmin()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        penalty = serializer.save()
        refresh_technician_reputation(penalty.technician)

    def perform_update(self, serializer):
        penalty = serializer.save()
        refresh_technician_reputation(penalty.technician)

    def perform_destroy(self, instance):
        profile = instance.technician
        instance.delete()
        refresh_technician_reputation(profile)
