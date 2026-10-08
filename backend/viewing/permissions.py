from django.http import Http404
from rest_framework import exceptions
from rest_framework.permissions import BasePermission

from access.services import evaluate_access
from courses.models import Course
from resources.models import Resource


class HasCourseAccess(BasePermission):
    """
    Resolves the course (and resource) from the URL and requires the authenticated student to hold
    active access. Unpublished resources/courses are reported as missing. The resolved objects are
    attached to the request for the view.
    """

    def has_permission(self, request, view):
        resource_id = view.kwargs.get("resource_id")
        if resource_id is not None:
            resource = (
                Resource.objects.select_related("course")
                .filter(pk=resource_id, status=Resource.Status.PUBLISHED, course__status=Course.Status.PUBLISHED)
                .first()
            )
            if resource is None:
                raise Http404
            course = resource.course
            request.resource = resource
        else:
            course = Course.objects.filter(pk=view.kwargs["course_id"], status=Course.Status.PUBLISHED).first()
            if course is None:
                raise Http404
        decision = evaluate_access(request.user, course)
        if not decision.allowed:
            raise exceptions.PermissionDenied(
                f"You do not have active access to this course ({decision.state}).",
                code=f"access_{decision.state}",
            )
        request.course = course
        return True
