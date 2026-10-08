"""Django's built-in admin site (/admin/): e-mail + password, then a normal Django session.

This is deliberately independent of the EduVault admin API (/api/admin/, password + e-mailed code + JWT): no OTP, no
TOTP, no challenge token and no JWT is involved here, and a Django session is never accepted by the API.

The sign-in reuses the API's credential check (`services.authenticate_credentials`: per-email/IP lockout, audit
events, timing equalisation). Django's own LoginView then creates the session (the key is cycled on login, so session
fixation is prevented) and only follows same-host `next` URLs. `has_permission` re-checks the account on every
request, so a suspended/rejected/pending admin, or one who lost `is_staff` or the admin role, is locked out at once.
"""
from django import forms
from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.shortcuts import redirect
from django.urls import path, reverse

from audit.models import Actions
from audit.services import create_audit_event
from core.exceptions import ServiceError
from core.utils import get_client_ip

from . import services
from .models import User


def can_use_admin_site(user):
    """An active, approved EduVault administrator with Django staff access.

    is_staff alone is not enough (a student flagged is_staff is refused) and neither is role=admin alone.
    """
    return bool(
        user is not None
        and getattr(user, "is_authenticated", False)
        and user.is_active
        and user.is_staff
        and user.role == User.Role.ADMIN
        and user.status == User.Status.ACTIVE
    )


class AdminPasswordForm(AdminAuthenticationForm):
    """The username field is the account's e-mail address."""

    def clean(self):
        email = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if email is not None and password:
            ip = get_client_ip(self.request)
            try:
                self.user_cache = services.authenticate_credentials(
                    email=email, password=password, role=User.Role.ADMIN, ip=ip
                )
            except ServiceError as exc:
                if exc.code == "ACCOUNT_LOCKED":
                    raise forms.ValidationError(exc.message, code="locked")
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
            create_audit_event(
                Actions.LOGIN_SUCCESS, actor=self.user_cache, ip=ip, metadata={"role": "admin", "via": "django_admin"}
            )
        return self.cleaned_data

    def confirm_login_allowed(self, user):
        if not can_use_admin_site(user):
            raise self.get_invalid_login_error()


class EduVaultAdminSite(admin.AdminSite):
    login_form = AdminPasswordForm

    def has_permission(self, request):
        return can_use_admin_site(request.user)

    def get_urls(self):
        return [
            # User-facing paths for the two user sections (explicit path()s, mounted under /admin/).
            path("accounts/users/admin/", self._section("admin:accounts_adminuser_changelist")),
            path("accounts/users/students/", self._section("admin:accounts_studentuser_changelist")),
            *super().get_urls(),
        ]

    def _section(self, url_name):
        """Redirect to a proxy model's changelist. Wrapped in admin_view, so it demands the same admin session as
        every other admin page (anyone else is sent to the admin login first)."""

        def view(request):
            query = request.META.get("QUERY_STRING")
            return redirect(reverse(url_name, current_app=self.name) + (f"?{query}" if query else ""))

        return self.admin_view(view)
