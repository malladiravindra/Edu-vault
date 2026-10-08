from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import EnvelopePagination
from core.responses import success

from . import services
from .models import Notification
from .serializers import NotificationSerializer


def _own(user):
    """Every notification query is scoped to the authenticated user (IDOR protection)."""
    return Notification.objects.filter(user=user)


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = _own(request.user)
        unread_only = request.query_params.get("unread", "").lower() in ("1", "true", "yes")
        if unread_only:
            qs = qs.filter(read_at__isnull=True)
        if request.query_params.get("type"):
            qs = qs.filter(type=request.query_params["type"].lower())
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs, request)
        response = paginator.get_paginated_response(NotificationSerializer(page, many=True).data)
        response.data["meta"]["unread_count"] = _own(request.user).filter(read_at__isnull=True).count()
        return response


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        notification = get_object_or_404(_own(request.user), pk=notification_id)
        return success(NotificationSerializer(services.mark_read(user=request.user, notification=notification)).data)


class NotificationReadAllView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return success({"updated": services.mark_all_read(user=request.user)})


class NotificationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, notification_id):
        return success(NotificationSerializer(get_object_or_404(_own(request.user), pk=notification_id)).data)

    def delete(self, request, notification_id):
        get_object_or_404(_own(request.user), pk=notification_id).delete()
        return success({"detail": "Notification deleted."})
