import uuid

from django.conf import settings
from django.db import models


class Actions:
    """Audit action codes. Free-form on purpose so new apps can add codes without migrations."""

    REGISTER = "auth.register"
    REGISTRATION_OTP_SENT = "auth.register.otp_sent"
    REGISTRATION_EMAIL_VERIFIED = "auth.register.email_verified"
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILED = "auth.login.failed"
    LOGIN_LOCKED = "auth.login.locked"
    LOGOUT = "auth.logout"
    PASSWORD_CHANGED = "auth.password.changed"
    PASSWORD_RESET_REQUESTED = "auth.password.reset_requested"
    PASSWORD_RESET_COMPLETED = "auth.password.reset_completed"
    PASSWORD_RESET_VERIFIED = "auth.password.reset_verified"
    OTP_FAILED = "auth.otp.failed"
    TWO_FACTOR_FAILED = "auth.2fa.failed"
    ADMIN_OTP_SENT = "auth.admin_otp.sent"
    ADMIN_OTP_VERIFIED = "auth.admin_otp.verified"
    ADMIN_OTP_EXPIRED = "auth.admin_otp.expired"
    ADMIN_OTP_RATE_LIMITED = "auth.admin_otp.rate_limited"
    REGISTRATION_APPROVED = "user.approved"
    REGISTRATION_REJECTED = "user.rejected"
    USER_SUSPENDED = "user.suspended"
    USER_REACTIVATED = "user.reactivated"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    PROFILE_UPDATED = "user.profile_updated"
    COURSE_CREATED = "course.created"
    COURSE_UPDATED = "course.updated"
    COURSE_DELETED = "course.deleted"
    COURSE_PUBLISHED = "course.published"
    COURSE_ARCHIVED = "course.archived"
    COURSE_UNPUBLISHED = "course.unpublished"
    RESOURCE_UPLOADED = "resource.uploaded"
    RESOURCE_UPDATED = "resource.updated"
    RESOURCE_VALIDATED = "resource.validated"
    RESOURCE_PUBLISHED = "resource.published"
    RESOURCE_ARCHIVED = "resource.archived"
    RESOURCE_REPLACED = "resource.replaced"
    RESOURCE_DELETED = "resource.deleted"
    PAYMENT_CREATED = "payment.created"
    PAYMENT_COMPLETED = "payment.completed"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_CANCELLED = "payment.cancelled"
    PAYMENT_REFUNDED = "payment.refunded"
    PAYMENT_MISMATCH = "payment.mismatch"
    STRIPE_WEBHOOK_PROCESSED = "stripe.webhook.processed"
    SETTINGS_CHANGED = "settings.changed"
    SETTINGS_TEST_EMAIL = "settings.test_email"
    ACCESS_REQUESTED = "access.requested"
    ACCESS_GRANTED = "access.granted"
    ACCESS_REJECTED = "access.rejected"
    ACCESS_REVOKED = "access.revoked"
    REFRESH_REUSE_DETECTED = "auth.refresh.reuse_detected"
    ACCESS_PAYMENT_REQUIRED = "access.payment_required"
    ACCESS_KEPT_PENDING = "access.kept_pending"


class ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionError("Audit events are immutable.")

    def delete(self):
        raise PermissionError("Audit events are immutable.")

    def bulk_update(self, *args, **kwargs):
        raise PermissionError("Audit events are immutable.")


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    actor_email = models.CharField(max_length=254, blank=True)
    action = models.CharField(max_length=64, db_index=True)
    target_type = models.CharField(max_length=64, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    objects = ImmutableQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["actor", "-created_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionError("Audit events are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Audit events are immutable.")
