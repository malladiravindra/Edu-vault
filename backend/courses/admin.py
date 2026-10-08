from django.contrib import admin

from .models import Course


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "access_mode", "price_amount", "currency", "published_at")
    list_filter = ("status", "access_mode")
    search_fields = ("title", "slug")
    readonly_fields = ("status", "created_by", "published_at", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False  # the API refuses to delete a course that is in use; archive instead
