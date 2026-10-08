from django.urls import include, path

from . import views

# Mounted at /api/student/viewing/  (protected, server-rendered, watermarked pages)
urlpatterns = [
    path(
        "courses/<uuid:course_id>/resources/",
        views.ViewerCourseResourcesView.as_view(),
        name="viewer-course-resources",
    ),
    path("resources/<uuid:resource_id>/", views.ViewerResourceView.as_view(), name="viewer-resource"),
    path(
        "resources/<uuid:resource_id>/pages/<int:page_number>/",
        views.ViewerPageView.as_view(),
        name="viewer-page",
    ),
    path("resources/<uuid:resource_id>/activity/", views.ViewerActivityView.as_view(), name="viewer-activity"),
]

# Mounted at /api/student/learning-history/
student_urlpatterns = [
    path("", views.LearningHistoryView.as_view(), name="my-learning-history"),
]

# --- What this app contributes to the two portals. Paths are relative to /api/student/ and /api/admin/ and are
# --- combined in portal/student_urls.py and portal/admin_urls.py; the final public URLs are the ones in the comments above.
student_portal_urlpatterns = [
    path("viewing/", include(urlpatterns)),
    path("learning-history/", include(student_urlpatterns)),
]
