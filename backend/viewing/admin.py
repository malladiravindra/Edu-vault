from django.contrib import admin

from core.admin import ReadOnlyModelAdmin

from .models import ViewActivity


@admin.register(ViewActivity)
class ViewActivityAdmin(ReadOnlyModelAdmin):
    list_display = ("student", "course", "resource", "page_number", "duration_seconds", "viewed_at")
    search_fields = ("student__email", "course__title", "resource__title")
