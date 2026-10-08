import uuid

from django.conf import settings
from django.db import models


class CourseAccess(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending approval"
        ACTIVE = "active", "Active"
        REJECTED = "rejected", "Rejected"
        REVOKED = "revoked", "Revoked"

    class Source(models.TextChoices):
        IMMEDIATE = "immediate", "Immediate"
        ADMIN_APPROVAL = "admin_approval", "Granted or approved by admin"
        PAYMENT = "payment", "Payment"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="course_accesses")
    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT, related_name="accesses")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    source = models.CharField(max_length=16, choices=Source.choices, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    # Admin decision: this student must pay for the course before access is granted (cleared on grant).
    payment_required = models.BooleanField(default=False)
    note = models.CharField(max_length=500, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    granted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at"]
        constraints = [
            models.UniqueConstraint(fields=["student", "course"], name="unique_student_course_access"),
        ]
        indexes = [models.Index(fields=["course", "status"]), models.Index(fields=["status", "expires_at"])]
