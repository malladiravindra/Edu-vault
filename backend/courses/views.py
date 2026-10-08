from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from access.services import access_states_for
from accounts.permissions import IsAdminRole, IsApprovedStudent
from core.pagination import EnvelopePagination, paginate
from core.responses import success
from core.utils import get_client_ip, query_value

from . import services
from resources.models import Resource
from viewing.serializers import ViewerResourceSerializer

from .models import Course
from .serializers import AdminCourseSerializer, CourseSerializer, CourseWriteSerializer


def _filtered(request, qs, *, with_status):
    if request.query_params.get("q"):
        qs = qs.filter(title__icontains=request.query_params["q"])
    fields = ("category", "access_mode") + (("status",) if with_status else ())
    for field in fields:
        if query_value(request, field):
            qs = qs.filter(**{f"{field}__iexact": query_value(request, field)})
    return qs


# ---------------------------------------------------------------- student catalogue

class CourseListView(APIView):
    permission_classes = [IsApprovedStudent]

    def get(self, request):
        qs = _filtered(request, Course.objects.filter(status=Course.Status.PUBLISHED), with_status=False)
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs, request)
        context = {"access_states": access_states_for(request.user, page)}
        return paginator.get_paginated_response(CourseSerializer(page, many=True, context=context).data)


class MyCourseListView(APIView):
    """Only the courses the signed-in student has an access record for (any state), with that state."""

    permission_classes = [IsApprovedStudent]

    def get(self, request):
        from access.models import CourseAccess

        course_ids = CourseAccess.objects.filter(student=request.user).values("course")
        qs = _filtered(request, Course.objects.filter(pk__in=course_ids, status=Course.Status.PUBLISHED), with_status=False)
        states = access_states_for(request.user, qs)
        wanted = query_value(request, "state")
        if wanted:
            qs = qs.filter(pk__in=[pk for pk, s in states.items() if s["state"] == wanted])
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs, request)
        context = {"access_states": {pk: states[pk] for pk in (c.pk for c in page)}}
        return paginator.get_paginated_response(CourseSerializer(page, many=True, context=context).data)


class CourseDetailView(APIView):
    permission_classes = [IsApprovedStudent]

    def get(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id, status=Course.Status.PUBLISHED)
        states = access_states_for(request.user, [course])
        data = CourseSerializer(course, context={"access_states": states}).data
        # Course content (the list of PDFs) is only included when the central access check allows it.
        data["resources"] = (
            ViewerResourceSerializer(
                Resource.objects.filter(course=course, status=Resource.Status.PUBLISHED).order_by("created_at"), many=True
            ).data
            if states[course.pk]["allowed"]
            else []
        )
        return success(data)


# ---------------------------------------------------------------- admin management

_PUT_DEFAULTS = {
    "description": "", "category": "", "access_mode": Course.AccessMode.MANUAL_APPROVAL, "price_amount": None,
    "currency": "USD", "access_duration_days": None,
}


class AdminCourseListCreateView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        return paginate(request, _filtered(request, Course.objects.all(), with_status=True), AdminCourseSerializer)

    def post(self, request):
        data = CourseWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        course = services.create_course(actor=request.user, data=data.validated_data, ip=get_client_ip(request))
        return success(AdminCourseSerializer(course).data, status=status.HTTP_201_CREATED)


class AdminCourseDetailView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request, course_id):
        return success(AdminCourseSerializer(get_object_or_404(Course, pk=course_id)).data)

    def patch(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id)
        data = CourseWriteSerializer(course, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        course = services.update_course(
            actor=request.user, course=course, data=data.validated_data, ip=get_client_ip(request)
        )
        return success(AdminCourseSerializer(course).data)

    def put(self, request, course_id):
        """Full replacement of the editable fields: anything omitted returns to its default."""
        course = get_object_or_404(Course, pk=course_id)
        payload = {**_PUT_DEFAULTS, **request.data}
        data = CourseWriteSerializer(course, data=payload)
        data.is_valid(raise_exception=True)
        course = services.update_course(
            actor=request.user, course=course, data=data.validated_data, ip=get_client_ip(request)
        )
        return success(AdminCourseSerializer(course).data)

    def delete(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id)
        services.delete_course(actor=request.user, course=course, ip=get_client_ip(request))
        return success({"detail": "Course deleted."})


class AdminCoursePublishView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id)
        course = services.publish_course(actor=request.user, course=course, ip=get_client_ip(request))
        return success(AdminCourseSerializer(course).data)


class AdminCourseUnpublishView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id)
        course = services.unpublish_course(actor=request.user, course=course, ip=get_client_ip(request))
        return success(AdminCourseSerializer(course).data)


class AdminCourseArchiveView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id)
        course = services.archive_course(actor=request.user, course=course, ip=get_client_ip(request))
        return success(AdminCourseSerializer(course).data)
