from rest_framework import status
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.permissions import IsApprovedStudent
from core.pagination import paginate
from core.responses import success
from resources.models import Resource

from . import services
from .models import ViewActivity
from .permissions import HasCourseAccess
from .serializers import (
    ActivitySerializer,
    LearningHistorySerializer,
    ViewerResourceSerializer,
)


class _ViewerView(APIView):
    permission_classes = [IsApprovedStudent, HasCourseAccess]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "viewer"


class ViewerCourseResourcesView(_ViewerView):
    def get(self, request, course_id):
        qs = Resource.objects.filter(course=request.course, status=Resource.Status.PUBLISHED).order_by("created_at")
        return paginate(request, qs, ViewerResourceSerializer)


class ViewerResourceView(_ViewerView):
    def get(self, request, resource_id):
        return success(ViewerResourceSerializer(request.resource).data)


class ViewerPageView(_ViewerView):
    """Returns a server-rendered, watermarked page image (base64 JPEG). The original PDF is never sent."""

    def get(self, request, resource_id, page_number):
        data = services.render_protected_page(
            student=request.user, course=request.course, resource=request.resource, page_number=page_number
        )
        response = success(data)
        response["Cache-Control"] = "no-store, private"
        response["Pragma"] = "no-cache"
        return response


class ViewerActivityView(_ViewerView):
    def post(self, request, resource_id):
        data = ActivitySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        activity = services.record_duration(
            student=request.user,
            resource=request.resource,
            view_id=data.validated_data["view_id"],
            seconds=data.validated_data["duration_seconds"],
        )
        return success({"view_id": str(activity.id), "duration_seconds": activity.duration_seconds}, status=status.HTTP_200_OK)


class LearningHistoryView(APIView):
    permission_classes = [IsApprovedStudent]

    def get(self, request):
        qs = ViewActivity.objects.filter(student=request.user).select_related("course", "resource")
        for field in ("course", "resource"):
            if request.query_params.get(field):
                qs = qs.filter(**{field: request.query_params[field]})
        return paginate(request, qs, LearningHistorySerializer)
