from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from access.models import CourseAccess
from accounts.models import User
from courses.models import Course
from payments.models import Payment
from resources.models import Resource
from viewing.models import ViewActivity

from .conftest import register_via_api, PASSWORD, auth_client, login_student, minted_client

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(admin, student, other_student):
    """A small, known dataset; assertions below are derived from exactly what is created here."""
    pending = User.objects.create_user("pend@example.com", PASSWORD, full_name="P", status="pending")
    User.objects.create_user("rej@example.com", PASSWORD, full_name="R", status="rejected")
    User.objects.create_user("sus@example.com", PASSWORD, full_name="S", status="suspended")
    c1 = Course.objects.create(title="Maths", slug="maths", status="published", created_by=admin)
    c2 = Course.objects.create(title="Art", slug="art", status="published", access_mode="payment_required", price_amount="50.00", created_by=admin)
    Course.objects.create(title="Draft", slug="draft", status="draft", created_by=admin)
    r1 = Resource.objects.create(course=c1, title="Algebra", storage_key="k1", original_filename="a.pdf", file_size=1, page_count=4, sha256="a", status="published")
    Resource.objects.create(course=c1, title="Hidden", storage_key="k2", original_filename="b.pdf", file_size=1, page_count=10, sha256="b", status="draft")
    CourseAccess.objects.create(student=student, course=c1, status="active", source="admin_approval", granted_at=timezone.now())
    CourseAccess.objects.create(student=other_student, course=c1, status="pending")
    CourseAccess.objects.create(student=student, course=c2, status="active", source="payment", granted_at=timezone.now())
    Payment.objects.create(student=student, course=c2, amount="50.00", currency="USD", status="paid", paid_at=timezone.now())
    Payment.objects.create(student=other_student, course=c2, amount="50.00", currency="USD", status="pending")
    Payment.objects.create(student=other_student, course=c2, amount="50.00", currency="USD", status="refunded")
    for minutes_ago, page in ((30, 1), (20, 2), (10, 2)):  # page 2 viewed twice, at different times
        view = ViewActivity.objects.create(student=student, course=c1, resource=r1, page_number=page, watermark_id="w", duration_seconds=60)
        ViewActivity.objects.filter(pk=view.pk).update(viewed_at=timezone.now() - timedelta(minutes=minutes_ago))
    return dict(c1=c1, c2=c2, r1=r1, pending=pending)


class TestAdminDashboard:
    def test_numbers_match_database(self, admin_client, world):
        data = admin_client.get("/api/admin/reports/dashboard/").json()["data"]
        assert data["users"]["students"] == User.objects.filter(role="student").count() == 5
        assert data["users"]["pending_registrations"] == 1
        assert data["users"]["active"] == 2 and data["users"]["suspended"] == 1 and data["users"]["rejected"] == 1
        assert data["courses"] == {"total": 3, "published": 2, "draft": 1, "archived": 0}
        assert data["resources"]["total"] == 2 and data["resources"]["published"] == 1 and data["resources"]["draft"] == 1
        assert data["access"]["active"] == 2 and data["access"]["pending_approvals"] == 1
        assert data["payments"]["by_status"] == {"pending": 1, "paid": 1, "failed": 0, "cancelled": 0, "refunded": 1}
        assert data["payments"]["revenue"] == [{"currency": "USD", "total": "50.00", "count": 1}]
        assert data["activity_last_30_days"]["page_views"] == 3
        assert data["activity_last_30_days"]["reading_minutes"] == 3.0
        assert data["recent_activity"] and len(data["recent_activity"]) <= 10

    def test_changes_with_data(self, admin_client, world, student):
        before = admin_client.get("/api/admin/reports/dashboard/").json()["data"]["users"]["total"]
        User.objects.create_user("new@example.com", PASSWORD, full_name="N")
        assert admin_client.get("/api/admin/reports/dashboard/").json()["data"]["users"]["total"] == before + 1

    def test_empty_database_is_zeroes_not_errors(self, admin_client):
        data = admin_client.get("/api/admin/reports/dashboard/").json()["data"]
        assert data["courses"]["total"] == 0 and data["payments"]["revenue"] == []
        assert data["activity_last_30_days"]["page_views"] == 0

    def test_admin_only(self, student_client, world):
        assert student_client.get("/api/admin/reports/dashboard/").status_code == 403
        assert APIClient().get("/api/admin/reports/dashboard/").status_code == 401


class TestReports:
    def test_overview(self, admin_client, world):
        res = admin_client.get("/api/admin/reports/overview/?days=7")
        assert res.status_code == 200 and res.json()["data"]["activity"]["days"] == 7

    def test_users(self, admin_client, world):
        data = admin_client.get("/api/admin/reports/users/").json()["data"]
        assert data["awaiting_review"] == 1 and data["oldest_pending_since"] is not None
        assert sum(d["registrations"] for d in data["registrations_per_day"]) == 5

    def test_courses_report_per_course(self, admin_client, world):
        body = admin_client.get("/api/admin/reports/courses/").json()
        rows = {r["title"]: r for r in body["data"]}
        assert body["meta"]["count"] == 3
        assert rows["Maths"]["active_students"] == 1 and rows["Maths"]["pending_requests"] == 1
        assert rows["Maths"]["published_resources"] == 1 and rows["Maths"]["page_views"] == 3
        assert rows["Maths"]["viewing_students"] == 1 and rows["Maths"]["reading_minutes"] == 3.0
        assert rows["Art"]["revenue"] == [{"currency": "USD", "total": "50.00"}]
        assert rows["Draft"]["active_students"] == 0 and rows["Draft"]["revenue"] == []
        assert admin_client.get("/api/admin/reports/courses/?status=DRAFT").json()["meta"]["count"] == 1

    def test_courses_report_is_not_n_plus_one(self, admin_client, world, admin, django_assert_max_num_queries):
        for i in range(15):
            Course.objects.create(title=f"C{i}", slug=f"c{i}", status="published", created_by=admin)
        with django_assert_max_num_queries(14):
            admin_client.get("/api/admin/reports/courses/?page_size=20")

    def test_access(self, admin_client, world):
        data = admin_client.get("/api/admin/reports/access/").json()["data"]
        assert data["by_source"] == {"admin_approval": 1, "payment": 1}
        assert data["summary"]["pending_approvals"] == 1 and data["oldest_pending_request"] is not None
        assert sum(d["grants"] for d in data["granted_per_day"]) == 2

    def test_expiring_soon(self, admin_client, world, student):
        CourseAccess.objects.filter(student=student, course=world["c1"]).update(expires_at=timezone.now() + timedelta(days=3))
        assert admin_client.get("/api/admin/reports/access/").json()["data"]["expiring_within_7_days"] == 1

    def test_payments(self, admin_client, world):
        data = admin_client.get("/api/admin/reports/payments/").json()["data"]
        assert data["revenue_in_period"] == [{"currency": "USD", "total": "50.00", "count": 1}]
        assert data["top_courses"][0]["title"] == "Art" and data["top_courses"][0]["revenue"] == "50.00"
        assert data["average_payment"] == [{"currency": "USD", "average": "50.00"}]
        assert data["summary"]["refunded"][0]["total"] == "50.00"

    def test_payments_period_excludes_old(self, admin_client, world):
        Payment.objects.filter(status="paid").update(paid_at=timezone.now() - timedelta(days=60))
        data = admin_client.get("/api/admin/reports/payments/?days=30").json()["data"]
        assert data["revenue_in_period"] == []

    def test_activity(self, admin_client, world):
        data = admin_client.get("/api/admin/reports/activity/").json()["data"]
        assert data["summary"]["page_views"] == 3 and data["summary"]["active_students"] == 1
        assert data["top_resources"][0] == {"resource": str(world["r1"].id), "title": "Algebra", "course": "Maths", "views": 3, "students": 1}
        assert data["views_per_day"][0]["views"] == 3

    def test_days_validation(self, admin_client):
        for bad in ("0", "366", "abc"):
            assert admin_client.get(f"/api/admin/reports/overview/?days={bad}").status_code == 400

    def test_all_reports_are_admin_only(self, student_client):
        for name in ("overview", "users", "courses", "access", "payments", "activity"):
            assert student_client.get(f"/api/admin/reports/{name}/").status_code == 403
            assert APIClient().get(f"/api/admin/reports/{name}/").status_code == 401

    def test_reports_are_read_only(self, admin_client):
        assert admin_client.post("/api/admin/reports/overview/", {}, format="json").status_code == 405


class TestStudentDashboard:
    def test_full_dashboard(self, student_client, student, world):
        data = student_client.get("/api/student/dashboard/").json()["data"]
        assert data["profile"]["email"] == student.email
        assert data["registration"]["status"] == "active"
        titles = {c["title"]: c for c in data["active_courses"]}
        assert set(titles) == {"Maths", "Art"}
        maths = titles["Maths"]
        assert maths["total_pages"] == 4 and maths["pages_viewed"] == 2 and maths["progress_percent"] == 50.0
        assert titles["Art"]["total_pages"] == 0 and titles["Art"]["progress_percent"] == 0.0
        stats = data["learning_stats"]
        assert stats["pages_viewed"] == 3 and stats["distinct_pages"] == 2 and stats["reading_minutes"] == 3.0
        assert stats["resources_opened"] == 1 and stats["active_courses"] == 2 and stats["last_viewed_at"]
        assert len(data["recent_activity"]) == 3 and data["recent_activity"][0]["course_title"] == "Maths"

    def test_pending_requests_and_other_student_isolated(self, other_student, world):
        c = APIClient()
        auth_client(c, login_student(c, other_student.email).json()["data"]["tokens"])
        data = c.get("/api/student/dashboard/").json()["data"]
        assert [p["title"] for p in data["pending_requests"]] == ["Maths"]
        assert data["active_courses"] == [] and data["learning_stats"]["pages_viewed"] == 0
        assert data["recent_activity"] == []

    def test_notifications_section(self, student_client, student, world):
        from notifications.models import Notification

        Notification.objects.create(user=student, type="security", title="T", message="M")
        data = student_client.get("/api/student/dashboard/").json()["data"]["notifications"]
        assert data["unread_count"] == 1 and data["latest"][0]["title"] == "T"

    def test_expired_and_unpublished_courses_not_active(self, student_client, student, world):
        CourseAccess.objects.filter(student=student, course=world["c1"]).update(expires_at=timezone.now() - timedelta(days=1))
        Course.objects.filter(pk=world["c2"].pk).update(status="archived")
        assert student_client.get("/api/student/dashboard/").json()["data"]["active_courses"] == []

    def test_pending_student_sees_registration_status(self, world):
        from accounts.models import User

        assert login_student(APIClient(), "pend@example.com").status_code == 403  # cannot sign in while pending
        c = minted_client(User.objects.get(email="pend@example.com"))
        res = c.get("/api/student/dashboard/")  # even a minted token gets nothing while pending
        assert res.status_code == 403 and res.json()["error"]["code"] == "REGISTRATION_PENDING"

    def test_rejected_student_sees_reason(self, admin_client, db):
        c = APIClient()
        res = register_via_api(c, "late@example.com", password=PASSWORD)
        admin_client.post(f"/api/admin/students/approval-requests/{res.json()['data']['student']['id']}/reject/", {"reason": "Missing docs"}, format="json")
        denied = login_student(APIClient(), "late@example.com")
        assert denied.status_code == 403 and denied.json()["error"]["code"] == "REGISTRATION_REJECTED"
        assert denied.json()["error"]["details"]["reason"] == "Missing docs"
        from accounts.models import User

        c = minted_client(User.objects.get(email="late@example.com"))
        res = c.get("/api/student/dashboard/")
        assert res.status_code == 403 and res.json()["error"]["code"] == "REGISTRATION_REJECTED"

    def test_admin_and_anonymous_blocked(self, admin_client):
        assert admin_client.get("/api/student/dashboard/").status_code == 403
        assert APIClient().get("/api/student/dashboard/").status_code == 401

    def test_query_count_is_bounded(self, student_client, student, world, admin, django_assert_max_num_queries):
        for i in range(6):
            c = Course.objects.create(title=f"X{i}", slug=f"x{i}", status="published", created_by=admin)
            CourseAccess.objects.create(student=student, course=c, status="active")
        with django_assert_max_num_queries(22):
            student_client.get("/api/student/dashboard/")
