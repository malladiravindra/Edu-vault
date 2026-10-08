from rest_framework.views import APIView

from accounts.models import name_slug
from accounts.permissions import IsApprovedStudent, IsStudentRole
from accounts.serializers import StudentSettingsSerializer
from core.exceptions import ServiceError
from core.responses import success

from . import services


class StudentDashboardView(APIView):
    """The signed-in student's own dashboard. Only an approved, active student gets one; the student is the JWT user."""

    permission_classes = [IsApprovedStudent]

    def get(self, request):
        return success(services.student_dashboard(request.user))


class StudentNamedDashboardView(StudentDashboardView):
    """GET /api/student/<name>/dashboard/ - the same dashboard under the student's own name (frontend routing).

    The name is NOT an identity: the JWT is. It is only compared with the authenticated student's own name, nothing is
    looked up by it, so a valid token with someone else's name (or any unknown name) gets a 403 and no data."""

    def get(self, request, student_name):
        if name_slug(student_name) != name_slug(request.user.dashboard_name):
            raise ServiceError("STUDENT_MISMATCH", "This dashboard belongs to another student.", 403)
        return super().get(request)


class StudentSettingsView(APIView):
    """The student's own persisted preferences."""

    permission_classes = [IsStudentRole]

    def get(self, request):
        return success({"email_notifications": request.user.email_notifications})

    def patch(self, request):
        data = StudentSettingsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.update_student_settings(user=request.user, **data.validated_data)
        return success({"email_notifications": request.user.email_notifications})
