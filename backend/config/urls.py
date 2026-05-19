from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from audit.views import AuditEventViewSet
from accounts.views import MeAPIView, RegisterAPIView
from adminpanel.views import AdminSummaryAPIView, AdminTechnicianActionAPIView
from appointments.views import AppointmentViewSet, TechnicianAvailableSlotsAPIView
from catalog.views import (
    CategoryViewSet,
    ServiceViewSet,
    TechnicianOnboardingAPIView,
    TechnicianProfileViewSet,
    TechnicianServicePhotoViewSet,
    TechnicianServiceViewSet,
    ZoneViewSet,
)
from disputes.views import ArbiterClaimAPIView, ArbiterDecisionAPIView, ArbiterQueueAPIView, DisputeViewSet
from leads.views import TechnicianLeadViewSet
from notifications.views import NotificationViewSet
from recommendations.views import RecommendationAPIView
from reputation.views import PenaltyViewSet, RatingViewSet
from config.views import HealthAPIView

router = DefaultRouter()
router.register("categories", CategoryViewSet)
router.register("zones", ZoneViewSet)
router.register("audit/events", AuditEventViewSet, basename="audit-events")
router.register("technicians", TechnicianProfileViewSet)
router.register("services", ServiceViewSet)
router.register("technician/services", TechnicianServiceViewSet, basename="technician-services")
router.register("technician/service-photos", TechnicianServicePhotoViewSet, basename="technician-service-photos")
router.register("technician/leads", TechnicianLeadViewSet, basename="technician-leads")
router.register("ratings", RatingViewSet)
router.register("penalties", PenaltyViewSet)
router.register("disputes", DisputeViewSet)
router.register("notifications", NotificationViewSet, basename="notifications")
router.register("appointments", AppointmentViewSet, basename="appointment")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/register/", RegisterAPIView.as_view(), name="register"),
    path("api/auth/me/", MeAPIView.as_view(), name="me"),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/health/", HealthAPIView.as_view(), name="health"),
    path("api/admin/summary/", AdminSummaryAPIView.as_view(), name="admin_summary"),
    path("api/admin/technicians/<int:pk>/<str:action>/", AdminTechnicianActionAPIView.as_view(), name="admin_technician_action"),
    path("api/arbiter/queue/", ArbiterQueueAPIView.as_view(), name="arbiter_queue"),
    path("api/arbiter/disputes/<int:pk>/claim/", ArbiterClaimAPIView.as_view(), name="arbiter_claim"),
    path("api/arbiter/disputes/<int:pk>/decision/", ArbiterDecisionAPIView.as_view(), name="arbiter_decision"),
    path("api/technician/onboarding/", TechnicianOnboardingAPIView.as_view(), name="technician_onboarding"),
    path("api/technicians/<int:pk>/available-slots/", TechnicianAvailableSlotsAPIView.as_view(), name="technician_available_slots"),
    path("api/recommendations/", RecommendationAPIView.as_view(), name="recommendations"),
    path("api/telegram/", include("telegram_bot.urls")),
    path("api/chatbot/", include("telegram_bot.urls")),
    path("api/", include(router.urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
