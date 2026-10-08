from django.urls import include, path

from . import views

# Mounted at /api/admin/reports/
urlpatterns = [
    path("dashboard/", views.AdminDashboardView.as_view(), name="admin-dashboard"),
    path("overview/", views.OverviewReportView.as_view(), name="report-overview"),
    path("users/", views.UsersReportView.as_view(), name="report-users"),
    path("courses/", views.CoursesReportView.as_view(), name="report-courses"),
    path("access/", views.AccessReportView.as_view(), name="report-access"),
    path("payments/", views.PaymentsReportView.as_view(), name="report-payments"),
    path("activity/", views.ActivityReportView.as_view(), name="report-activity"),
]

# --- What this app contributes to the two portals. Paths are relative to /api/student/ and /api/admin/ and are
# --- combined in portal/student_urls.py and portal/admin_urls.py; the final public URLs are the ones in the comments above.
admin_portal_urlpatterns = [
    path("reports/", include(urlpatterns)),
]
