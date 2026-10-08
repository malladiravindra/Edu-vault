"""List endpoints must not issue more queries as the number of rows grows (N+1 regression guard)."""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from access.models import CourseAccess
from accounts.models import User
from courses.models import Course
from notifications.models import Notification
from payments.models import Payment
from resources.models import Resource
from viewing.models import ViewActivity

from .conftest import PASSWORD, auth_client, login_student

pytestmark = pytest.mark.django_db


def seed(admin, student, n, offset):
    """Create n rows in every list-backed table."""
    for i in range(n):
        k = offset + i
        course = Course.objects.create(title=f"C{k}", slug=f"c{k}", status="published", access_mode="payment_required", price_amount="5.00", created_by=admin)
        CourseAccess.objects.create(student=student, course=course, status="active", source="payment")
        resource = Resource.objects.create(course=course, title=f"R{k}", storage_key=f"key{k}", original_filename="a.pdf", file_size=1, page_count=3, sha256="a", status="published")
        ViewActivity.objects.create(student=student, course=course, resource=resource, page_number=1, watermark_id="w")
        Payment.objects.create(student=student, course=course, amount="5.00", currency="USD", status="paid")
        Notification.objects.create(user=student, type="security", title="t", message="m")
        User.objects.create_user(f"u{k}@example.com", PASSWORD, full_name=f"U{k}")


STUDENT_LISTS = ["/api/student/course/", "/api/student/access/", "/api/student/payments/", "/api/student/learning-history/", "/api/student/notifications/", "/api/student/dashboard/"]
ADMIN_LISTS = [
    "/api/admin/students/", "/api/admin/students/approval-requests/", "/api/admin/course/", "/api/admin/students/access/", "/api/admin/course/resources/",
    "/api/admin/students/payments/", "/api/admin/audit-logs/", "/api/admin/reports/dashboard/", "/api/admin/reports/courses/",
    "/api/admin/reports/overview/", "/api/admin/reports/activity/",
]


def count_queries(client, url):
    with CaptureQueriesContext(connection) as ctx:
        res = client.get(url + ("&" if "?" in url else "?") + "page_size=100")
    assert res.status_code == 200, (url, res.status_code)
    return len(ctx)


@pytest.mark.parametrize("url", STUDENT_LISTS)
def test_student_list_query_count_is_constant(url, admin, student):
    c = APIClient()
    auth_client(c, login_student(c).json()["data"]["tokens"])
    seed(admin, student, 2, 0)
    small = count_queries(c, url)
    seed(admin, student, 12, 100)
    large = count_queries(c, url)
    assert large == small, f"{url}: {small} queries for 2 rows but {large} for 14 rows (N+1)"


@pytest.mark.parametrize("url", ADMIN_LISTS)
def test_admin_list_query_count_is_constant(url, admin_client, admin, student):
    seed(admin, student, 2, 0)
    small = count_queries(admin_client, url)
    seed(admin, student, 12, 100)
    large = count_queries(admin_client, url)
    assert large == small, f"{url}: {small} queries for 2 rows but {large} for 14 rows (N+1)"
