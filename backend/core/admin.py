from django.contrib import admin


class ReadOnlyModelAdmin(admin.ModelAdmin):
    """Browse-only: state that must change through the API services (audited, validated) cannot be edited here."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
