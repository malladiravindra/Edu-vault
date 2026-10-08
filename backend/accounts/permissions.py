from rest_framework import exceptions
from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """Server-side admin check; role and status come from the database user, never from the client or the token."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == "admin" and user.status == "active")


class IsStudentRole(BasePermission):
    """Any student account, including those still awaiting approval."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == "student")


class IsApprovedStudent(BasePermission):
    """Student whose registration has been approved and whose account is active."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.role == "student"):
            return False
        if user.status == "pending":
            raise exceptions.PermissionDenied("Your registration is awaiting admin approval.", code="registration_pending")
        if user.status == "rejected":
            raise exceptions.PermissionDenied("Your registration was not approved.", code="registration_rejected")
        return user.is_approved
