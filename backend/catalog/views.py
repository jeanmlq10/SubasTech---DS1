from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdminOrTechnicianProfileOwnerOrReadOnly, IsPlatformAdminOrReadOnly
from .models import Category, Service, ServicePhoto, TechnicianProfile, Zone
from .serializers import (
    CategorySerializer,
    ServicePhotoSerializer,
    ServiceSerializer,
    TechnicianProfileSerializer,
    TechnicianServiceSerializer,
    ZoneSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsPlatformAdminOrReadOnly]


class ZoneViewSet(viewsets.ModelViewSet):
    queryset = Zone.objects.all()
    serializer_class = ZoneSerializer
    permission_classes = [IsPlatformAdminOrReadOnly]


class TechnicianProfileViewSet(viewsets.ModelViewSet):
    queryset = TechnicianProfile.objects.select_related("user").prefetch_related("zones")
    serializer_class = TechnicianProfileSerializer
    permission_classes = [IsAdminOrTechnicianProfileOwnerOrReadOnly]

    def perform_create(self, serializer):
        self._ensure_technician(self.request.user)
        if TechnicianProfile.objects.filter(user=self.request.user).exists():
            raise ValidationError({"detail": "This user already has a technician profile."})
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        self._ensure_technician(serializer.instance.user)
        serializer.save()


class TechnicianOnboardingAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "technician_profile", None)
        return Response(
            {
                "role": request.user.role,
                "onboarding_complete": bool(profile and profile.zones.exists()),
                "profile": TechnicianProfileSerializer(profile).data if profile else None,
            }
        )

    def post(self, request):
        self._ensure_technician(request.user)
        profile, _created = TechnicianProfile.objects.get_or_create(user=request.user)
        serializer = TechnicianProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(
            {
                "onboarding_complete": serializer.instance.zones.exists(),
                "profile": TechnicianProfileSerializer(serializer.instance).data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        return self.post(request)

    def _ensure_technician(self, user: User):
        if user.role != User.Role.TECHNICIAN:
            raise PermissionDenied("Only technician users can complete technician onboarding.")


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.select_related("technician__user", "category").prefetch_related("technician__zones", "photos")
    serializer_class = ServiceSerializer
    permission_classes = [IsPlatformAdminOrReadOnly]


class TechnicianServiceViewSet(viewsets.ModelViewSet):
    serializer_class = TechnicianServiceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        profile = getattr(self.request.user, "technician_profile", None)
        if not profile:
            return Service.objects.none()
        return Service.objects.filter(technician=profile).select_related("category").prefetch_related("photos")

    def perform_create(self, serializer):
        profile = getattr(self.request.user, "technician_profile", None)
        if not profile:
            raise ValidationError({"technician_profile": "Complete technician onboarding before creating services."})
        serializer.save(technician=profile)


class TechnicianServicePhotoViewSet(viewsets.ModelViewSet):
    serializer_class = ServicePhotoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        profile = getattr(self.request.user, "technician_profile", None)
        if not profile:
            return ServicePhoto.objects.none()
        return ServicePhoto.objects.filter(service__technician=profile).select_related("service")

    def perform_create(self, serializer):
        profile = getattr(self.request.user, "technician_profile", None)
        if not profile:
            raise ValidationError({"technician_profile": "Complete technician onboarding before uploading photos."})
        service = get_object_or_404(Service, pk=self.request.data.get("service_id"), technician=profile)
        serializer.save(service=service)
