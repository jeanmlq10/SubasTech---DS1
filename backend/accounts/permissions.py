from rest_framework.permissions import BasePermission

from .models import User


class IsPlatformAdmin(BasePermission):
    """Allow Django staff/superusers and SubasTech administrator role users."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_staff or user.is_superuser or getattr(user, "role", "") == User.Role.ADMIN)
        )


class IsPlatformArbiter(BasePermission):
    """Allow arbiters, administrators and Django staff/superusers."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (
                user.is_staff
                or user.is_superuser
                or getattr(user, "role", "") in {User.Role.ARBITER, User.Role.ADMIN}
            )
        )


class IsPlatformAdminOrReadOnly(BasePermission):
    """Allow public reads but restrict writes to platform administrators."""

    def has_permission(self, request, view):
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return True
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_staff or user.is_superuser or getattr(user, "role", "") == User.Role.ADMIN)
        )
