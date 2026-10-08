from django.contrib import admin

from core.admin import ReadOnlyModelAdmin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(ReadOnlyModelAdmin):
    list_display = ("user", "type", "title", "read_at", "created_at")
    list_filter = ("type",)
    search_fields = ("user__email", "title")
