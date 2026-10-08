from django.urls import include, path

from . import views

# Mounted at /api/admin/course/resources/  (PDF resources are managed by admins only; students read them through /api/viewing/)
urlpatterns = [
    path("", views.AdminResourceListCreateView.as_view(), name="admin-resource-list"),
    path("<uuid:resource_id>/", views.AdminResourceDetailView.as_view(), name="admin-resource-detail"),
    path(
        "<uuid:resource_id>/replace/",
        views.AdminResourceReplaceView.as_view(),
        name="admin-resource-replace",
    ),
    path(
        "<uuid:resource_id>/validate/",
        views.AdminResourceValidateView.as_view(),
        name="admin-resource-validate",
    ),
    path(
        "<uuid:resource_id>/publish/",
        views.AdminResourcePublishView.as_view(),
        name="admin-resource-publish",
    ),
    path(
        "<uuid:resource_id>/archive/",
        views.AdminResourceArchiveView.as_view(),
        name="admin-resource-archive",
    ),
]

# --- What this app contributes to the two portals. Paths are relative to /api/student/ and /api/admin/ and are
# --- combined in portal/student_urls.py and portal/admin_urls.py; the final public URLs are the ones in the comments above.
admin_portal_urlpatterns = [
    path("course/resources/", include(urlpatterns)),
]
