from django.db.models import Avg, Count, Q
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsPlatformAdmin
from audit.models import AuditEvent
from audit.services import log_audit_event
from catalog.models import Category, Service, TechnicianDocument, TechnicianProfile, Zone
from disputes.models import Dispute
from leads.models import ServiceLead
from reputation.models import Rating
from reputation.services import calculate_technician_reputation


class AdminSummaryAPIView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        technicians = TechnicianProfile.objects.select_related("user").prefetch_related("zones")
        services = Service.objects.select_related("category", "technician__user")
        disputes = Dispute.objects.select_related("client", "technician__user", "service")
        leads = ServiceLead.objects.select_related("technician__user", "service")
        error_events = AuditEvent.objects.filter(
            Q(event_type=AuditEvent.EventType.INTEGRATION_ERROR) | Q(status="error")
        ).select_related("actor")
        recent_errors = error_events[:5]

        average_rating = Rating.objects.filter(target_role=Rating.TargetRole.TECHNICIAN).aggregate(value=Avg("score"))["value"] or 0
        technician_snapshots = [calculate_technician_reputation(technician) for technician in technicians]
        average_reputation_score = 0
        if technician_snapshots:
            average_reputation_score = round(
                sum(snapshot["reputation_score"] for snapshot in technician_snapshots) / len(technician_snapshots),
                2,
            )

        lead_status_breakdown = {
            row["status"]: row["total"]
            for row in leads.values("status").annotate(total=Count("id"))
        }
        metrics = {
            "total_technicians": technicians.count(),
            "verified_technicians": technicians.filter(is_verified=True).count(),
            "pending_verification": technicians.filter(is_verified=False).count(),
            "pending_technician_documents": TechnicianDocument.objects.filter(
                review_status=TechnicianDocument.ReviewStatus.PENDING
            ).count(),
            "suspended_technicians": technicians.filter(user__is_active=False).count(),
            "active_services": services.filter(is_active=True).count(),
            "inactive_services": services.filter(is_active=False).count(),
            "total_leads": leads.count(),
            "new_leads": lead_status_breakdown.get(ServiceLead.Status.NEW, 0),
            "contacted_leads": lead_status_breakdown.get(ServiceLead.Status.CONTACTED, 0),
            "accepted_leads": lead_status_breakdown.get(ServiceLead.Status.ACCEPTED, 0),
            "closed_leads": lead_status_breakdown.get(ServiceLead.Status.CLOSED, 0),
            "open_disputes": disputes.filter(status=Dispute.Status.OPEN).count(),
            "in_review_disputes": disputes.filter(status=Dispute.Status.IN_REVIEW).count(),
            "resolved_disputes": disputes.filter(status=Dispute.Status.RESOLVED).count(),
            "average_rating": round(float(average_rating), 2),
            "average_reputation_score": average_reputation_score,
            "recent_integration_errors": error_events.count(),
            "total_categories": Category.objects.filter(is_active=True).count(),
            "total_zones": Zone.objects.filter(is_active=True).count(),
        }

        recent_technicians = technicians.annotate(
            service_count=Count("services", distinct=True),
            avg_rating=Avg("ratings__score", filter=Q(ratings__target_role=Rating.TargetRole.TECHNICIAN)),
        ).order_by("-created_at")[:5]

        recent_services = services.order_by("-created_at")[:5]
        recent_disputes = disputes.order_by("-created_at")[:5]

        return Response(
            {
                "metrics": metrics,
                "recent_technicians": [self._technician_payload(technician) for technician in recent_technicians],
                "recent_services": [self._service_payload(service) for service in recent_services],
                "recent_disputes": [self._dispute_payload(dispute) for dispute in recent_disputes],
                "lead_status_breakdown": lead_status_breakdown,
                "recent_errors": [self._audit_payload(event) for event in recent_errors],
                "role_breakdown": self._role_breakdown(),
                "alerts": self._alerts(metrics),
            }
        )

    def _technician_payload(self, technician: TechnicianProfile) -> dict:
        return {
            "id": technician.id,
            "name": technician.user.get_full_name() or technician.user.username,
            "email": technician.user.email,
            "is_verified": technician.is_verified,
            "user_is_active": technician.user.is_active,
            "availability_status": technician.availability_status,
            "response_time_minutes": technician.response_time_minutes,
            "service_count": technician.service_count,
            "average_rating": round(float(technician.avg_rating or 0), 2),
            "document_counts": {
                "pending": technician.documents.filter(review_status=TechnicianDocument.ReviewStatus.PENDING).count(),
                "approved": technician.documents.filter(review_status=TechnicianDocument.ReviewStatus.APPROVED).count(),
                "rejected": technician.documents.filter(review_status=TechnicianDocument.ReviewStatus.REJECTED).count(),
            },
            "zones": [zone.name for zone in technician.zones.all()],
            "created_at": technician.created_at.isoformat(),
        }

    def _service_payload(self, service: Service) -> dict:
        return {
            "id": service.id,
            "title": service.title,
            "category": service.category.name,
            "technician": service.technician.user.get_full_name() or service.technician.user.username,
            "base_price": str(service.base_price),
            "is_active": service.is_active,
            "created_at": service.created_at.isoformat(),
        }

    def _dispute_payload(self, dispute: Dispute) -> dict:
        return {
            "id": dispute.id,
            "title": dispute.title,
            "status": dispute.status,
            "priority": dispute.priority,
            "client": dispute.client.get_full_name() or dispute.client.username,
            "technician": dispute.technician.user.get_full_name() or dispute.technician.user.username,
            "service": dispute.service.title if dispute.service else None,
            "created_at": dispute.created_at.isoformat(),
        }

    def _audit_payload(self, event: AuditEvent) -> dict:
        return {
            "id": event.id,
            "event_type": event.event_type,
            "status": event.status,
            "source": event.source,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "message": event.message,
            "created_at": event.created_at.isoformat(),
        }

    def _role_breakdown(self) -> dict:
        rows = User.objects.values("role").annotate(total=Count("id"))
        return {row["role"]: row["total"] for row in rows}

    def _alerts(self, metrics: dict) -> list[dict]:
        alerts = []
        if metrics["pending_verification"]:
            alerts.append(
                {
                    "type": "warning",
                    "title": "Technicians pending verification",
                    "message": f"{metrics['pending_verification']} technicians need administrator review.",
                }
            )
        if metrics["open_disputes"]:
            alerts.append(
                {
                    "type": "critical",
                    "title": "Open disputes",
                    "message": f"{metrics['open_disputes']} disputes are waiting for moderation.",
                }
            )
        if metrics["recent_integration_errors"]:
            alerts.append(
                {
                    "type": "critical",
                    "title": "Recent integration errors",
                    "message": f"{metrics['recent_integration_errors']} operational errors need review in audit logs.",
                }
            )
        if metrics["suspended_technicians"]:
            alerts.append(
                {
                    "type": "warning",
                    "title": "Suspended technicians",
                    "message": f"{metrics['suspended_technicians']} technicians are currently suspended.",
                }
            )
        if metrics["active_services"] == 0:
            alerts.append(
                {
                    "type": "info",
                    "title": "No active services yet",
                    "message": "Seed categories, onboard technicians and create services to activate recommendations.",
                }
            )
        return alerts


class AdminTechnicianActionAPIView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, pk: int, action: str):
        technician = TechnicianProfile.objects.select_related("user").filter(pk=pk).first()
        if not technician:
            return Response({"detail": "Technician not found."}, status=status.HTTP_404_NOT_FOUND)

        if action == "verify":
            technician.is_verified = True
            technician.save(update_fields=["is_verified", "updated_at"])
        elif action == "unverify":
            technician.is_verified = False
            technician.save(update_fields=["is_verified", "updated_at"])
        elif action == "suspend":
            technician.user.is_active = False
            technician.user.save(update_fields=["is_active"])
        elif action == "activate":
            technician.user.is_active = True
            technician.user.save(update_fields=["is_active"])
        else:
            return Response({"detail": "Unsupported technician action."}, status=status.HTTP_400_BAD_REQUEST)

        log_audit_event(
            event_type=AuditEvent.EventType.ADMIN_ACTION,
            actor=request.user,
            source="adminpanel.technician_action",
            entity_type="technician",
            entity_id=technician.id,
            status="success",
            message="Administrator executed technician moderation action",
            metadata={"action": action, "target_user_id": technician.user_id},
        )

        annotated = (
            TechnicianProfile.objects.select_related("user")
            .prefetch_related("zones")
            .annotate(
                service_count=Count("services", distinct=True),
                avg_rating=Avg("ratings__score", filter=Q(ratings__target_role=Rating.TargetRole.TECHNICIAN)),
            )
            .get(pk=technician.pk)
        )
        return Response(AdminSummaryAPIView()._technician_payload(annotated))
