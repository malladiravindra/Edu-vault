from django.urls import include, path

from . import views

# Mounted at /api/student/course/  (published catalogue for approved students)
urlpatterns = [
    path("", views.CourseListView.as_view(), name="course-list"),
    path("<uuid:course_id>/", views.CourseDetailView.as_view(), name="course-detail"),
]

# Mounted at /api/admin/course/
admin_urlpatterns = [
    path("", views.AdminCourseListCreateView.as_view(), name="admin-course-list"),
    path("<uuid:course_id>/", views.AdminCourseDetailView.as_view(), name="admin-course-detail"),
    path("<uuid:course_id>/publish/", views.AdminCoursePublishView.as_view(), name="admin-course-publish"),
    path("<uuid:course_id>/unpublish/", views.AdminCourseUnpublishView.as_view(), name="admin-course-unpublish"),
    path("<uuid:course_id>/archive/", views.AdminCourseArchiveView.as_view(), name="admin-course-archive"),
]

# --- What this app contributes to the two portals. Paths are relative to /api/student/ and /api/admin/ and are
# --- combined in portal/student_urls.py and portal/admin_urls.py; the final public URLs are the ones in the comments above.
student_portal_urlpatterns = [
    path("course/", include(urlpatterns)),
    path("courses/", views.MyCourseListView.as_view(), name="my-courses"),
]
admin_portal_urlpatterns = [
    path("course/", include(admin_urlpatterns)),
]
