from django.urls import include, path

from accounts.permissions import IsAdminRole, IsStudentRole

from . import views


def _routes(prefix, permission):
    """Same views for both portals; each portal admits only its own role. Always scoped to the signed-in user."""

    def as_view(view):
        return view.as_view(permission_classes=[permission])

    return [
        path("", as_view(views.NotificationListView), name=f"{prefix}notification-list"),
        path("read-all/", as_view(views.NotificationReadAllView), name=f"{prefix}notification-read-all"),
        path("<uuid:notification_id>/", as_view(views.NotificationDetailView), name=f"{prefix}notification-detail"),
        path("<uuid:notification_id>/read/", as_view(views.NotificationReadView), name=f"{prefix}notification-read"),
    ]


# Mounted at /api/student/notifications/
urlpatterns = _routes("", IsStudentRole)

# Mounted at /api/admin/notifications/
admin_urlpatterns = _routes("admin-", IsAdminRole)

# --- What this app contributes to the two portals. Paths are relative to /api/student/ and /api/admin/ and are
# --- combined in portal/student_urls.py and portal/admin_urls.py; the final public URLs are the ones in the comments above.
student_portal_urlpatterns = [
    path("notifications/", include(urlpatterns)),
]
admin_portal_urlpatterns = [
    path("notifications/", include(admin_urlpatterns)),
]
