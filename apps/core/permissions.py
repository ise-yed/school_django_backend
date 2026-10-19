from rest_framework.permissions import BasePermission, SAFE_METHODS
from apps.accounts.models import User


class IsSuperUser(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_superuser or request.user.role == User.Role.SUPERUSER)
        )


class IsSchoolAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.school_id is not None
            and request.user.role == User.Role.SCHOOL_ADMIN
        )


class IsTeacherOrSchoolAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.school_id is not None
            and request.user.role in (User.Role.SCHOOL_ADMIN, User.Role.TEACHER)
        )


class IsParentReadOnly(BasePermission):
    """ولی فقط دسترسی مشاهده (Read-only) دارد."""
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.school_id is not None
            and request.user.role == User.Role.PARENT
            and request.method in SAFE_METHODS
        )