from django.shortcuts import get_object_or_404
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from core.pagination import paginate
from core.responses import success

from .models import AuditEvent
from .serializers import AuditEventSerializer


class AuditEventListView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        qs = AuditEvent.objects.all()
        params = request.query_params
        for field in ("action", "actor", "target_type", "target_id"):
            if params.get(field):
                qs = qs.filter(**{field: params[field]})
        if params.get("from"):
            qs = qs.filter(created_at__gte=params["from"])
        if params.get("to"):
            qs = qs.filter(created_at__lte=params["to"])
        return paginate(request, qs, AuditEventSerializer)


class AuditEventDetailView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request, event_id):
        return success(AuditEventSerializer(get_object_or_404(AuditEvent, pk=event_id)).data)
