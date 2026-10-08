from django.contrib import admin

from core.admin import ReadOnlyModelAdmin

from .models import Payment, StripeEvent


@admin.register(Payment)
class PaymentAdmin(ReadOnlyModelAdmin):
    """Money state is changed only by the verified Stripe webhook, never by hand."""

    list_display = ("id", "student", "course", "amount", "currency", "status", "paid_at", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("student__email", "course__title")


@admin.register(StripeEvent)
class StripeEventAdmin(ReadOnlyModelAdmin):
    list_display = ("event_id", "event_type", "payment", "received_at")
    list_filter = ("event_type",)
    search_fields = ("event_id",)
