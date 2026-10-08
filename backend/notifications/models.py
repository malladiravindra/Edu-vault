import uuid

from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        REGISTRATION_APPROVED = "registration_approved", "Registration approved"
        REGISTRATION_REJECTED = "registration_rejected", "Registration rejected"
        ACCESS_GRANTED = "access_granted", "Access granted"
        ACCESS_REVOKED = "access_revoked", "Access revoked"
        PAYMENT_SUCCESSFUL = "payment_successful", "Payment successful"
        COURSE_PUBLISHED = "course_published", "Course published"
        SECURITY = "security", "Security"
        NEW_REGISTRATION = "new_registration", "New registration"
        ACCESS_REQUESTED = "access_requested", "Access requested"
        PAYMENT_RECEIVED = "payment_received", "Payment received"
        PAYMENT_REQUESTED = "payment_requested", "Payment requested"
        ACCESS_REJECTED = "access_rejected", "Access rejected"
        ACCESS_PENDING = "access_pending", "Access under review"
        PAYMENT_FAILED = "payment_failed", "Payment unsuccessful"
        RESOURCE_AVAILABLE = "resource_available", "Resource available"
        PAYMENT_ATTENTION = "payment_attention", "Payment needs attention"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=32, choices=Type.choices)
    title = models.CharField(max_length=200)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "read_at"]),
        ]

    @property
    def is_read(self):
        return self.read_at is not None
