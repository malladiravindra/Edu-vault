from django.contrib import admin

from core.admin import ReadOnlyModelAdmin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(ReadOnlyModelAdmin):
    """The audit log is append-only; the admin site can only read it."""

    list_display = ("created_at", "action", "actor_email", "target_type", "target_id")
    list_filter = ("action", "target_type")
    search_fields = ("actor_email", "action", "target_id")
