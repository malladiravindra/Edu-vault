from rest_framework import serializers
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from core.pagination import EnvelopePagination
from core.responses import success
from core.utils import query_value
from courses.models import Course

from . import services


class ReportQuerySerializer(serializers.Serializer):
    days = serializers.IntegerField(min_value=1, max_value=365, default=30)


def _days(request):
    query = ReportQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    return query.validated_data["days"]


class _ReportView(APIView):
    permission_classes = [IsAdminRole]
    builder = None

    def get(self, request):
        return success(getattr(services, self.builder)(_days(request)))


class AdminDashboardView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        return success(services.admin_dashboard())


class OverviewReportView(_ReportView):
    builder = "overview_report"


class UsersReportView(_ReportView):
    builder = "users_report"


class AccessReportView(_ReportView):
    builder = "access_report"


class PaymentsReportView(_ReportView):
    builder = "payments_report"


class ActivityReportView(_ReportView):
    builder = "activity_report"


class CoursesReportView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        qs = Course.objects.all()
        if query_value(request, "status"):
            qs = qs.filter(status=query_value(request, "status"))
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(services.course_rows(page))
