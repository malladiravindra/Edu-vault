from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdminRole, IsApprovedStudent
from core.pagination import paginate
from core.responses import success
from core.utils import get_client_ip, query_value
from courses.models import Course

from . import services
from .models import CourseAccess
from .serializers import (
    AccessDecisionSerializer,
    AccessGrantSerializer,
    AccessRequestSerializer,
    CourseAccessSerializer,
    StudentDecisionSerializer,
)


def _base_queryset():
    return CourseAccess.objects.select_related("student", "course")


# ---------------------------------------------------------------- student

class AccessListCreateView(APIView):
    """GET: the student's own access records. POST: request access to a published course."""

    permission_classes = [IsApprovedStudent]

    def get(self, request):
        return paginate(request, _base_queryset().filter(student=request.user), CourseAccessSerializer)

    def post(self, request):
        data = AccessRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        course = get_object_or_404(Course, pk=data.validated_data["course"], status=Course.Status.PUBLISHED)
        record = services.request_course_access(student=request.user, course=course, ip=get_client_ip(request))
        return success(
            CourseAccessSerializer(_base_queryset().get(pk=record.pk)).data, status=status.HTTP_201_CREATED
        )


class AccessDetailView(APIView):
    permission_classes = [IsApprovedStudent]

    def get(self, request, access_id):
        # Other students' records are indistinguishable from missing ones (IDOR protection).
        record = get_object_or_404(_base_queryset().filter(student=request.user), pk=access_id)
        return success(CourseAccessSerializer(record).data)


# ---------------------------------------------------------------- admin

class AdminAccessListView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        qs = _base_queryset()
        for field in ("student", "course"):
            if request.query_params.get(field):
                qs = qs.filter(**{field: request.query_params[field]})
        if query_value(request, "status"):
            qs = qs.filter(status=query_value(request, "status"))
        if query_value(request, "payment_required") in ("1", "true", "yes"):
            qs = qs.filter(payment_required=True)
        return paginate(request, qs, CourseAccessSerializer)


class AdminAccessGrantView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request):
        data = AccessGrantSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        record = services.admin_grant_access(actor=request.user, ip=get_client_ip(request), **data.validated_data)
        return success(
            CourseAccessSerializer(_base_queryset().get(pk=record.pk)).data, status=status.HTTP_201_CREATED
        )


class AdminAccessDetailView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request, access_id):
        return success(CourseAccessSerializer(get_object_or_404(_base_queryset(), pk=access_id)).data)

    def patch(self, request, access_id):
        record = get_object_or_404(_base_queryset(), pk=access_id)
        data = AccessDecisionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        record = services.decide_access(
            actor=request.user, record=record, ip=get_client_ip(request), **data.validated_data
        )
        return success(CourseAccessSerializer(_base_queryset().get(pk=record.pk)).data)


class AdminStudentDecisionView(APIView):
    """Registration decision for one student and course: immediate access, payment required, or keep pending."""

    permission_classes = [IsAdminRole]

    def post(self, request, user_id):
        student = get_object_or_404(User, pk=user_id, role=User.Role.STUDENT)
        data = StudentDecisionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        record = services.decide_registration(
            actor=request.user, student=student, ip=get_client_ip(request), **data.validated_data
        )
        return success(CourseAccessSerializer(_base_queryset().get(pk=record.pk)).data)
