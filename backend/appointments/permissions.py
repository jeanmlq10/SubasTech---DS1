from rest_framework.permissions import BasePermission

from accounts.models import User


class IsAppointmentParticipantOrAdmin(BasePermission):
    """Allow access to the appointment's client, its technician's user, SubasTech
    administrators, and Django staff/superusers; deny otherwise.

    Object-level only: this class deliberately does not filter querysets and
    does not check HTTP method. The view layer is still responsible for
    role-based queryset scoping (mirroring ``disputes.views.DisputeViewSet``
    and ``leads.views.TechnicianLeadViewSet``) and for restricting which
    lifecycle action each role may invoke.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (
                user.is_staff
                or user.is_superuser
                or getattr(user, "role", "") == User.Role.ADMIN
                or obj.client_id == user.id
                or obj.technician.user_id == user.id
            )
        )
