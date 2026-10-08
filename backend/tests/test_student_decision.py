from unittest import mock

import pytest

from access.models import CourseAccess
from audit.models import AuditEvent
from courses.models import Course

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def stripe_settings(settings):
    settings.STRIPE_SECRET_KEY = "sk_test_dummy_for_pytest"


@pytest.fixture
def approved(student):
    student.status = "active"
    student.save()
    return student


@pytest.fixture
def free_course(admin):
    return Course.objects.create(
        title="Free", slug="free", status="published", access_mode="manual_approval", created_by=admin
    )


@pytest.fixture
def paid_course(admin):
    return Course.objects.create(
        title="Paid", slug="paid", status="published", access_mode="payment_required",
        price_amount="25.00", currency="USD", created_by=admin,
    )


def decide(client, student, course, decision, **extra):
    return client.post(
        f"/api/admin/students/{student.id}/decision/",
        {"decision": decision, "course": str(course.id), **extra},
        format="json",
    )


class TestDecision:
    def test_immediate_grants_access(self, admin_client, approved, free_course):
        res = decide(admin_client, approved, free_course, "immediate")
        assert res.status_code == 200 and res.json()["data"]["state"] == "granted"
        assert CourseAccess.objects.get(student=approved, course=free_course).status == "active"

    def test_keep_pending(self, admin_client, approved, free_course):
        res = decide(admin_client, approved, free_course, "pending", note="reviewing")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["state"] == "pending" and data["payment_required"] is False
        assert AuditEvent.objects.filter(action="access.kept_pending").exists()

    def test_payment_required_lets_a_revoked_student_pay_again(self, admin_client, student_client, approved, paid_course):
        record = CourseAccess.objects.create(student=approved, course=paid_course, status="revoked")
        assert student_client.get(f"/api/student/course/{paid_course.id}/").json()["data"]["access"]["state"] == "revoked"
        res = decide(admin_client, approved, paid_course, "payment_required")
        assert res.status_code == 200 and res.json()["data"]["state"] == "payment_required"
        record.refresh_from_db()
        assert record.status == "pending" and record.payment_required is True
        assert AuditEvent.objects.filter(action="access.payment_required").exists()
        with mock.patch(
            "payments.services.stripe.checkout.Session.create", return_value={"id": "cs_dec_1", "url": "https://x.test"}
        ):
            checkout = student_client.post(
                "/api/student/payment/create-checkout/", {"course": str(paid_course.id)}, format="json"
            )
        assert checkout.status_code == 201

    def test_payment_required_rejected_for_free_course(self, admin_client, approved, free_course):
        res = decide(admin_client, approved, free_course, "payment_required")
        assert res.status_code == 409 and res.json()["error"]["code"] == "COURSE_NOT_PAID"
        assert not CourseAccess.objects.exists()

    def test_cannot_downgrade_live_access(self, admin_client, approved, free_course):
        decide(admin_client, approved, free_course, "immediate")
        res = decide(admin_client, approved, free_course, "pending")
        assert res.status_code == 409 and res.json()["error"]["code"] == "ALREADY_HAS_ACCESS"

    def test_grant_clears_payment_requirement(self, admin_client, approved, paid_course):
        decide(admin_client, approved, paid_course, "payment_required")
        decide(admin_client, approved, paid_course, "immediate")
        assert CourseAccess.objects.get(student=approved, course=paid_course).payment_required is False

    def test_unapproved_student_rejected(self, admin_client, student, free_course):
        student.status = "pending"
        student.save()
        assert decide(admin_client, student, free_course, "immediate").status_code == 400

    def test_invalid_decision_and_unknown_student(self, admin_client, approved, free_course):
        assert decide(admin_client, approved, free_course, "bogus").status_code == 400

    def test_requires_admin(self, student_client, approved, free_course):
        assert decide(student_client, approved, free_course, "immediate").status_code == 403


@pytest.mark.parametrize(
    "old",
    [
        "/api/accounts/admin/login/", "/api/admin/courses/", "/api/admin/users/", "/api/admin/registrations/",
        "/api/admin/resources/", "/api/admin/access/", "/api/admin/payments/", "/api/admin/dashboard/",
        "/api/course/", "/api/viewing/resources/x/", "/api/payment/create-checkout/", "/api/notifications/",
    ],
)
def test_old_urls_are_gone(client, old):
    assert client.get(old).status_code == 404
