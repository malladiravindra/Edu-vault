import uuid

from django.conf import settings
from django.db import models


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments")
    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT, related_name="payments")
    # Amount and currency are copied from the course on the server when checkout is created.
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    stripe_checkout_session_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_event_id = models.CharField(max_length=255, blank=True)  # last event that changed the status
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student", "-created_at"]),
            models.Index(fields=["course", "status"]),
            models.Index(fields=["status", "-created_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="payment_amount_positive"),
        ]


class StripeEvent(models.Model):
    """Every Stripe event id we have processed. The unique id is what makes webhooks idempotent."""

    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)
    payment = models.ForeignKey(Payment, null=True, blank=True, on_delete=models.SET_NULL, related_name="events")
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]
