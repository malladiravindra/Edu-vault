from django.urls import include, path

from . import views

# Mounted at /api/student/access/
urlpatterns = [
    path("", views.AccessListCreateView.as_view(), name="access-list"),
    path("<uuid:access_id>/", views.AccessDetailView.as_view(), name="access-detail"),
]

# Mounted at /api/admin/students/access/  (course-access records)
admin_urlpatterns = [
    path("", views.AdminAccessListView.as_view(), name="admin-access-list"),
    path("grant/", views.AdminAccessGrantView.as_view(), name="admin-access-grant"),
    path("<uuid:access_id>/", views.AdminAccessDetailView.as_view(), name="admin-access-detail"),
]

# --- What this app contributes to the two portals. Paths are relative to /api/student/ and /api/admin/ and are
# --- combined in portal/student_urls.py and portal/admin_urls.py; the final public URLs are the ones in the comments above.
student_portal_urlpatterns = [
    path("access/", include(urlpatterns)),
]
admin_portal_urlpatterns = [
    path("students/access/", include(admin_urlpatterns)),
    path("students/<uuid:user_id>/decision/", views.AdminStudentDecisionView.as_view(), name="admin-student-decision"),
]
