from django.urls import include, path

from . import views

# Mounted at /api/admin/audit-logs/
urlpatterns = [
    path("", views.AuditEventListView.as_view(), name="audit-list"),
    path("<uuid:event_id>/", views.AuditEventDetailView.as_view(), name="audit-detail"),
]

# --- What this app contributes to the two portals. Paths are relative to /api/student/ and /api/admin/ and are
# --- combined in portal/student_urls.py and portal/admin_urls.py; the final public URLs are the ones in the comments above.
admin_portal_urlpatterns = [
    path("audit-logs/", include(urlpatterns)),
]
