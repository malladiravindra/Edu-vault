from django.contrib import admin

from core.admin import ReadOnlyModelAdmin

from .models import CourseAccess


@admin.register(CourseAccess)
class CourseAccessAdmin(ReadOnlyModelAdmin):
    list_display = ("student", "course", "status", "source", "payment_required", "expires_at", "requested_at")
    list_filter = ("status", "source", "payment_required")
    search_fields = ("student__email", "course__title")
