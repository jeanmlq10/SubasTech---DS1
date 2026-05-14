from django.db import connection
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Category, Service, TechnicianProfile, Zone
from disputes.models import Dispute
from leads.models import ServiceLead


class HealthAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            database_ok = cursor.fetchone()[0] == 1

        return Response(
            {
                "status": "ok" if database_ok else "degraded",
                "database": "ok" if database_ok else "error",
                "counts": {
                    "categories": Category.objects.count(),
                    "zones": Zone.objects.count(),
                    "technicians": TechnicianProfile.objects.count(),
                    "active_services": Service.objects.filter(is_active=True).count(),
                    "leads": ServiceLead.objects.count(),
                    "open_disputes": Dispute.objects.filter(status=Dispute.Status.OPEN).count(),
                },
            }
        )
