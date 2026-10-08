from django.contrib import admin
from rest_framework_simplejwt.token_blacklist import models as token_models

from .models import AdminUser, StudentUser, User

# The JWT bookkeeping tables hold full refresh tokens: never show them in the admin.
for _model in (token_models.BlacklistedToken, token_models.OutstandingToken):
    try:
        admin.site.unregister(_model)
    except admin.sites.NotRegistered:
        pass

# There is deliberately NO admin for User itself: the two proxies below are the only way to browse accounts, so a
# combined list of every user (/admin/accounts/user/) does not exist.


class _RoleUserAdmin(admin.ModelAdmin):
    """Names and phone are editable. Role, status, flags, 2FA and password are read-only or hidden: they change through
    the API (suspension, for example, also ends the user's sessions)."""

    role = None  # set by the subclasses
    ordering = ("-created_at",)
    exclude = ("password", "totp_secret", "groups", "user_permissions")
    readonly_fields = (
        "email", "role", "status", "is_staff", "is_superuser", "two_factor_enabled", "reviewed_by", "reviewed_at",
        "rejection_reason", "last_login", "created_at", "updated_at",
    )

    def get_queryset(self, request):
        # Belt and braces: the proxy manager already filters, this keeps the section correct if that ever changes.
        return super().get_queryset(request).filter(role=self.role)

    def has_add_permission(self, request):
        return False  # accounts are created through registration / createsuperuser

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AdminUser)
class AdminUserAdmin(_RoleUserAdmin):
    role = User.Role.ADMIN
    list_display = ("email", "full_name", "role", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("email", "full_name", "phone_number")


@admin.register(StudentUser)
class StudentUserAdmin(_RoleUserAdmin):
    role = User.Role.STUDENT
    list_display = ("email", "full_name", "role", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("email", "full_name", "phone_number")
