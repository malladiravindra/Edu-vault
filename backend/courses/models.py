import uuid

from django.conf import settings
from django.db import models


class Course(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class AccessMode(models.TextChoices):
        IMMEDIATE = "immediate", "Immediate access"
        MANUAL_APPROVAL = "manual_approval", "Manual approval"
        PAYMENT_REQUIRED = "payment_required", "Payment required"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    access_mode = models.CharField(max_length=24, choices=AccessMode.choices, default=AccessMode.MANUAL_APPROVAL)
    price_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="USD")
    access_duration_days = models.PositiveIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "access_mode"])]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(access_mode="payment_required")
                | (models.Q(price_amount__isnull=False) & models.Q(price_amount__gt=0)),
                name="course_paid_requires_positive_price",
            ),
            models.CheckConstraint(
                condition=models.Q(access_duration_days__isnull=True) | models.Q(access_duration_days__gt=0),
                name="course_duration_positive",
            ),
        ]

    def __str__(self):
        return self.title
