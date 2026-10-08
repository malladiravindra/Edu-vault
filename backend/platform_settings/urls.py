from django.urls import include, path

from . import views

# Mounted at /api/admin/settings/
urlpatterns = [
    path("", views.AdminSettingsView.as_view(), name="admin-settings"),
    path("test-email/", views.AdminTestEmailView.as_view(), name="admin-settings-test-email"),
]

# --- What this app contributes to the two portals. Paths are relative to /api/student/ and /api/admin/ and are
# --- combined in portal/student_urls.py and portal/admin_urls.py; the final public URLs are the ones in the comments above.
admin_portal_urlpatterns = [
    path("settings/", include(urlpatterns)),
]
