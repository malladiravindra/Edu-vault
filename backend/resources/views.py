from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from core.pagination import paginate
from core.responses import success
from core.utils import get_client_ip, query_value

from . import services
from .models import Resource
from .serializers import (
    AdminResourceSerializer,
    ResourceReplaceSerializer,
    ResourceUpdateSerializer,
    ResourceUploadSerializer,
)


def _queryset():
    return Resource.objects.select_related("course")


def _get(resource_id):
    return get_object_or_404(_queryset(), pk=resource_id)


class AdminResourceListCreateView(APIView):
    permission_classes = [IsAdminRole]
    parser_classes = [MultiPartParser]

    def get(self, request):
        qs = _queryset()
        if request.query_params.get("course"):
            qs = qs.filter(course=request.query_params["course"])
        if query_value(request, "status"):
            qs = qs.filter(status=query_value(request, "status"))
        if request.query_params.get("q"):
            qs = qs.filter(title__icontains=request.query_params["q"])
        return paginate(request, qs, AdminResourceSerializer)

    def post(self, request):
        data = ResourceUploadSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        resource = services.upload_resource(
            actor=request.user,
            course=data.validated_data["course"],
            title=data.validated_data["title"],
            description=data.validated_data["description"],
            uploaded=data.validated_data["file"],
            ip=get_client_ip(request),
        )
        return success(AdminResourceSerializer(_get(resource.pk)).data, status=status.HTTP_201_CREATED)


class AdminResourceDetailView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request, resource_id):
        return success(AdminResourceSerializer(_get(resource_id)).data)

    def patch(self, request, resource_id):
        resource = _get(resource_id)
        data = ResourceUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        resource = services.update_resource(
            actor=request.user, resource=resource, data=data.validated_data, ip=get_client_ip(request)
        )
        return success(AdminResourceSerializer(resource).data)

    def delete(self, request, resource_id):
        services.delete_resource(actor=request.user, resource=_get(resource_id), ip=get_client_ip(request))
        return success({"detail": "Resource deleted."})


class AdminResourceReplaceView(APIView):
    """POST multipart `file`: replace the PDF; the resource returns to draft until validated and published again."""

    permission_classes = [IsAdminRole]
    parser_classes = [MultiPartParser]

    def post(self, request, resource_id):
        data = ResourceReplaceSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        resource = services.replace_resource_file(
            actor=request.user, resource=_get(resource_id), uploaded=data.validated_data["file"], ip=get_client_ip(request)
        )
        return success(AdminResourceSerializer(_get(resource.pk)).data)


class _AdminResourceActionView(APIView):
    permission_classes = [IsAdminRole]
    action = None

    def post(self, request, resource_id):
        resource = getattr(services, self.action)(
            actor=request.user, resource=_get(resource_id), ip=get_client_ip(request)
        )
        return success(AdminResourceSerializer(_get(resource.pk)).data)


class AdminResourceValidateView(_AdminResourceActionView):
    action = "validate_resource"


class AdminResourcePublishView(_AdminResourceActionView):
    action = "publish_resource"


class AdminResourceArchiveView(_AdminResourceActionView):
    action = "archive_resource"
