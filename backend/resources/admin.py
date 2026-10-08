from django.contrib import admin

from core.admin import ReadOnlyModelAdmin

from .models import Resource


@admin.register(Resource)
class ResourceAdmin(ReadOnlyModelAdmin):
    list_display = ("title", "course", "status", "page_count", "file_size", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "course__title")
    exclude = ("storage_key",)  # private object key: never displayed
