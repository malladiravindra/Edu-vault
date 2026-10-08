from django.urls import path

from . import views

# Routes of the student portal that belong to no single domain app.
# Final public URLs: /api/student/dashboard/ and /api/student/settings/
student_portal_urlpatterns = [
    path("dashboard/", views.StudentDashboardView.as_view(), name="student-dashboard"),
    path("settings/", views.StudentSettingsView.as_view(), name="student-settings"),
]
# Composed LAST in student_urls.py so no named route can ever shadow a fixed student route: /api/student/<name>/dashboard/
student_named_dashboard_urlpatterns = [
    path("<str:student_name>/dashboard/", views.StudentNamedDashboardView.as_view(), name="student-named-dashboard"),
]
