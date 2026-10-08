"""Student + admin workflow: my courses, payment requests, profile/settings, decisions, PDF replace."""
import json
from unittest import mock

import pytest
from django.core import mail
from rest_framework.test import APIClient

from access.models import CourseAccess
from accounts.models import User
from audit.models import AuditEvent
from courses.models import Course
from notifications.models import Notification
from payments.models import Payment
from resources.models import Resource
from resources.storage import get_private_storage

from .conftest import PASSWORD, auth_client, login_student
from .test_payments import send_event, session_obj
from .test_resources import make_pdf_bytes, upload

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def stripe_keys(settings):
    settings.STRIPE_SECRET_KEY = "sk_test_dummy_for_pytest"
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test_secret_for_pytest"


def post(client, url, data=None):
    return client.post(url, data or {}, format="json")


def code(res):
    return res.json().get("error", {}).get("code")


def signed_in(email):
    c = APIClient()
    auth_client(c, login_student(c, email).json()["data"]["tokens"])
    return c


@pytest.fixture
def a(db):
    return User.objects.create_user("a@example.com", PASSWORD, full_name="Student A", status="active")


@pytest.fixture
def b(db):
    return User.objects.create_user("b@example.com", PASSWORD, full_name="Student B", status="active")


@pytest.fixture
def ca(a):
    return signed_in(a.email)


@pytest.fixture
def cb(b):
    return signed_in(b.email)


@pytest.fixture
def free(admin):
    return Course.objects.create(title="Free", slug="free", status="published", access_mode="manual_approval", created_by=admin)


@pytest.fixture
def paid(admin):
    return Course.objects.create(
        title="Paid", slug="paid", status="published", access_mode="payment_required",
        price_amount="499.00", currency="INR", created_by=admin,
    )


def publish_pdf(admin_client, course, pages=2):
    rid = upload(admin_client, course, data=make_pdf_bytes(pages=pages)).json()["data"]["id"]
    admin_client.post(f"/api/admin/course/resources/{rid}/validate/")
    admin_client.post(f"/api/admin/course/resources/{rid}/publish/")
    return rid


def decide(admin_client, student, course, decision):
    return post(admin_client, f"/api/admin/students/{student.id}/decision/", {"decision": decision, "course": str(course.id)})


# ------------------------------------------------------------------ student: my courses + course content

class TestMyCourses:
    def test_only_courses_with_my_access_record(self, ca, cb, a, b, free, paid):
        CourseAccess.objects.create(student=a, course=free, status="active")
        mine = ca.get("/api/student/courses/").json()
        assert [c["title"] for c in mine["data"]] == ["Free"] and mine["data"][0]["access"]["state"] == "granted"
        assert cb.get("/api/student/courses/").json()["data"] == []
        assert len(ca.get("/api/student/course/").json()["data"]) == 2  # the catalogue still lists everything published

    def test_states_and_filter(self, ca, a, free, paid, admin):
        pending = Course.objects.create(title="Pend", slug="pend", status="published", access_mode="manual_approval")
        CourseAccess.objects.create(student=a, course=free, status="active")
        CourseAccess.objects.create(student=a, course=pending, status="pending")
        CourseAccess.objects.create(student=a, course=paid, status="pending", payment_required=True)
        states = {c["title"]: c["access"]["state"] for c in ca.get("/api/student/courses/").json()["data"]}
        assert states == {"Free": "granted", "Pend": "pending", "Paid": "payment_required"}
        only = ca.get("/api/student/courses/?state=payment_required").json()["data"]
        assert [c["title"] for c in only] == ["Paid"]

    def test_unpublished_courses_and_foreign_params_are_ignored(self, ca, a, b, free):
        draft = Course.objects.create(title="Draft", slug="draft", status="draft")
        CourseAccess.objects.create(student=a, course=draft, status="active")
        CourseAccess.objects.create(student=b, course=free, status="active")
        data = ca.get(f"/api/student/courses/?student={b.id}").json()["data"]
        assert data == []

    def test_roles(self, ca, admin_client):
        assert APIClient().get("/api/student/courses/").status_code == 401
        assert admin_client.get("/api/student/courses/").status_code == 403

    def test_course_detail_includes_pdfs_only_with_access(self, ca, cb, a, b, free, admin_client):
        rid = publish_pdf(admin_client, free)
        CourseAccess.objects.create(student=a, course=free, status="active")
        mine = ca.get(f"/api/student/course/{free.id}/").json()["data"]
        theirs = cb.get(f"/api/student/course/{free.id}/").json()["data"]
        assert [r["id"] for r in mine["resources"]] == [rid] and mine["access"]["allowed"] is True
        assert theirs["resources"] == [] and theirs["access"]["allowed"] is False
        assert "storage_key" not in json.dumps(mine) and "sha256" not in json.dumps(mine)

    def test_student_a_cannot_open_student_bs_course_content(self, ca, cb, a, b, free, admin_client):
        rid = publish_pdf(admin_client, free)
        CourseAccess.objects.create(student=b, course=free, status="active")
        assert cb.get(f"/api/student/viewing/resources/{rid}/pages/1/").status_code == 200
        assert ca.get(f"/api/student/viewing/resources/{rid}/pages/1/").status_code == 403
        assert ca.get(f"/api/student/viewing/courses/{free.id}/resources/").status_code == 403

    def test_there_is_no_download_endpoint(self, ca, a, free, admin_client):
        rid = publish_pdf(admin_client, free)
        CourseAccess.objects.create(student=a, course=free, status="active")
        for url in (f"/api/student/course/{free.id}/resources/{rid}/download/", f"/api/student/viewing/resources/{rid}/download/"):
            assert ca.get(url).status_code == 404
        page = ca.get(f"/api/student/viewing/resources/{rid}/pages/1/")
        assert page["Content-Type"].startswith("application/json") and "no-store" in page["Cache-Control"]


# ------------------------------------------------------------------ admin decision -> student payment request

class TestPaymentRequests:
    def test_manual_immediate_and_payment_have_distinct_meanings(self, admin_client, ca, a, free, paid):
        manual = decide(admin_client, a, free, "manual").json()["data"]
        assert manual["status"] == "pending" and manual["payment_required"] is False and manual["state"] == "pending"
        assert ca.get(f"/api/student/viewing/courses/{free.id}/resources/").status_code == 403

        immediate = decide(admin_client, a, free, "immediate").json()["data"]
        assert immediate["status"] == "active" and immediate["payment_required"] is False
        assert ca.get(f"/api/student/viewing/courses/{free.id}/resources/").status_code == 200

        required = decide(admin_client, a, paid, "payment_required").json()["data"]
        assert required["status"] == "pending" and required["payment_required"] is True and required["state"] == "payment_required"
        assert ca.get(f"/api/student/viewing/courses/{paid.id}/resources/").status_code == 403

    def test_student_sees_the_request_with_course_amount_currency(self, admin_client, ca, cb, a, b, paid):
        decide(admin_client, a, paid, "payment_required")
        items = ca.get("/api/student/payment-requests/").json()["data"]
        assert len(items) == 1
        item = items[0]
        assert item["course"] == {"id": str(paid.id), "title": "Paid"}
        assert item["amount"] == "499.00" and item["currency"] == "INR" and item["status"] == "pending" and item["created_at"]
        assert cb.get("/api/student/payment-requests/").json()["data"] == []  # nobody else sees it

    def test_dashboard_shows_it_and_only_for_that_student(self, admin_client, ca, cb, a, b, paid):
        decide(admin_client, a, paid, "payment_required")
        mine = ca.get("/api/student/dashboard/").json()["data"]
        other = cb.get("/api/student/dashboard/").json()["data"]
        assert [r["course"]["title"] for r in mine["payment_requests"]] == ["Paid"]
        assert mine["learning_stats"]["payment_required_courses"] == 1 and mine["pending_requests"] == []
        assert other["payment_requests"] == [] and other["learning_stats"]["payment_required_courses"] == 0

    def test_student_is_notified(self, admin_client, a, paid):
        decide(admin_client, a, paid, "payment_required")
        note = Notification.objects.get(user=a, type="payment_requested")
        assert "Paid" in note.message and note.data["course"] == str(paid.id)

    def test_pay_through_checkout_and_verified_webhook_only(self, admin_client, ca, a, paid):
        decide(admin_client, a, paid, "payment_required")
        with mock.patch("payments.services.stripe.checkout.Session.create", return_value={"id": "cs_w1", "url": "https://x.test"}):
            res = post(ca, "/api/student/payment/create-checkout/", {"course": str(paid.id)})
        assert res.status_code == 201
        assert ca.get("/api/student/payment-requests/").json()["meta"]["count"] == 1  # opening checkout changes nothing
        assert CourseAccess.objects.get(student=a, course=paid).status == "pending"
        payment = Payment.objects.get(pk=res.json()["data"]["id"])

        assert send_event("checkout.session.completed", session_obj(payment, amount_total=49900, currency="inr"), signed=False)[0].status_code == 400
        assert CourseAccess.objects.get(student=a, course=paid).status == "pending"

        send_event("checkout.session.completed", session_obj(payment, amount_total=49900, currency="inr"))
        record = CourseAccess.objects.get(student=a, course=paid)
        assert record.status == "active" and record.payment_required is False and record.source == "payment"
        assert ca.get("/api/student/payment-requests/").json()["data"] == []

    def test_payment_required_only_for_a_priced_published_course(self, admin_client, a, free):
        assert decide(admin_client, a, free, "payment_required").status_code == 409

    def test_admin_can_filter_payment_requests_and_dashboard_counts_them(self, admin_client, a, b, paid, free):
        decide(admin_client, a, paid, "payment_required")
        decide(admin_client, b, free, "manual")
        rows = admin_client.get("/api/admin/students/access/?payment_required=true").json()["data"]
        assert [r["student"] for r in rows] == [str(a.id)]
        access = admin_client.get("/api/admin/reports/dashboard/").json()["data"]["access"]
        assert access["payment_requests_pending"] == 1 and access["pending_approvals"] == 1

    def test_requests_need_an_approved_student(self, admin_client, student):
        c = signed_in(student.email)  # tokens issued while the student was still active
        student.status = "pending"
        student.save()
        assert c.get("/api/student/payment-requests/").status_code == 403
        assert APIClient().get("/api/student/payment-requests/").status_code == 401
        assert admin_client.get("/api/student/payment-requests/").status_code == 403

    def test_the_decision_screen_shows_the_student_state(self, admin_client, a, paid):
        decide(admin_client, a, paid, "payment_required")
        detail = admin_client.get(f"/api/admin/students/approval-requests/{a.id}/").json()["data"]
        assert detail["accesses"][0]["state"] == "payment_required" and detail["accesses"][0]["payment_required"] is True


# ------------------------------------------------------------------ profile + settings

class TestProfile:
    def test_update_names_and_phone(self, ca, a):
        res = ca.patch("/api/student/profile/", {"first_name": "Anna", "middle_name": "B", "last_name": "Cole", "phone_number": "+91 98765-43210"}, format="json")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["full_name"] == "Anna B Cole" and data["phone_number"] == "+919876543210"
        a.refresh_from_db()
        assert (a.first_name, a.middle_name, a.last_name) == ("Anna", "B", "Cole")
        assert AuditEvent.objects.filter(action="user.profile_updated").exists()

    def test_partial_update_keeps_other_parts(self, ca, a):
        ca.patch("/api/student/profile/", {"first_name": "Anna", "last_name": "Cole"}, format="json")
        ca.patch("/api/student/profile/", {"phone_number": "9876543210"}, format="json")
        a.refresh_from_db()
        assert a.full_name == "Anna Cole" and a.phone_number == "9876543210"

    def test_full_name_alone_still_works(self, ca, a):
        assert ca.patch("/api/student/profile/", {"full_name": "Display Name"}, format="json").json()["data"]["full_name"] == "Display Name"

    @pytest.mark.parametrize("body", [{}, {"first_name": ""}, {"first_name": "J0hn"}, {"phone_number": "abc"}, {"last_name": "x" * 101}])
    def test_validation(self, ca, body):
        assert ca.patch("/api/student/profile/", body, format="json").status_code == 400

    def test_protected_fields_cannot_be_changed(self, ca, a):
        ca.patch("/api/student/profile/", {"phone_number": "9876543210", "role": "admin", "status": "pending", "is_staff": True, "is_superuser": True, "email": "x@example.com", "password": "hacked-Passw0rd!"}, format="json")
        a.refresh_from_db()
        assert (a.role, a.status, a.is_staff, a.is_superuser, a.email) == ("student", "active", False, False, "a@example.com")
        assert a.check_password(PASSWORD)

    def test_students_only_touch_their_own_profile(self, ca, cb, a, b):
        ca.patch("/api/student/profile/", {"first_name": "Mine"}, format="json")
        b.refresh_from_db()
        assert b.first_name == "" and cb.get("/api/student/profile/").json()["data"]["email"] == b.email
        assert ca.patch(f"/api/student/profile/{b.id}/", {"first_name": "X"}, format="json").status_code == 404

    def test_admin_profile(self, admin_client, admin, student_client):
        res = admin_client.patch("/api/admin/profile/", {"first_name": "Root", "last_name": "Admin", "phone_number": "9876543210", "role": "student", "two_factor_enabled": True, "is_superuser": False}, format="json")
        assert res.status_code == 200 and res.json()["data"]["full_name"] == "Root Admin"
        admin.refresh_from_db()
        assert admin.role == "admin" and not admin.two_factor_enabled and admin.is_superuser  # mass assignment is ignored
        assert admin_client.get("/api/admin/profile/").json()["data"]["email"] == admin.email
        assert student_client.get("/api/admin/profile/").status_code == 403
        assert student_client.patch("/api/admin/profile/", {"first_name": "x"}, format="json").status_code == 403
        assert APIClient().get("/api/admin/profile/").status_code == 401

    def test_admin_cannot_use_the_student_profile(self, admin_client):
        assert admin_client.get("/api/student/profile/").status_code == 403


class TestStudentSettings:
    def test_defaults_and_persistence(self, ca, a):
        assert ca.get("/api/student/settings/").json()["data"] == {"email_notifications": True}
        assert ca.patch("/api/student/settings/", {"email_notifications": False}, format="json").json()["data"] == {"email_notifications": False}
        a.refresh_from_db()
        assert a.email_notifications is False
        assert signed_in(a.email).get("/api/student/settings/").json()["data"]["email_notifications"] is False

    @pytest.mark.parametrize("body", [{}, {"email_notifications": "maybe"}])
    def test_validation(self, ca, body):
        assert ca.patch("/api/student/settings/", body, format="json").status_code == 400

    def test_preference_controls_only_optional_email(self, admin_client, ca, a, free, paid, django_capture_on_commit_callbacks):
        ca.patch("/api/student/settings/", {"email_notifications": False}, format="json")
        with django_capture_on_commit_callbacks(execute=True):
            decide(admin_client, a, free, "immediate")  # access granted = optional e-mail
        assert Notification.objects.filter(user=a, type="access_granted").exists() and not mail.outbox
        with django_capture_on_commit_callbacks(execute=True):
            decide(admin_client, a, paid, "payment_required")  # payment request = mandatory e-mail
        assert Notification.objects.filter(user=a, type="payment_requested").exists() and len(mail.outbox) == 1
        with django_capture_on_commit_callbacks(execute=True):
            post(ca, "/api/accounts/password-change/", {"current_password": PASSWORD, "new_password": "An0ther-Str0ng-Pass!"})
        assert len(mail.outbox) == 2  # the security notice is always e-mailed

    def test_settings_are_private_and_student_only(self, ca, cb, a, b, admin_client):
        ca.patch("/api/student/settings/", {"email_notifications": False}, format="json")
        assert cb.get("/api/student/settings/").json()["data"]["email_notifications"] is True
        assert APIClient().get("/api/student/settings/").status_code == 401
        assert admin_client.get("/api/student/settings/").status_code == 403


# ------------------------------------------------------------------ admin: replace PDF, admin-only walls

class TestReplacePdf:
    def url(self, rid):
        return f"/api/admin/course/resources/{rid}/replace/"

    def upload_new(self, client, rid, data=None, name="new.pdf", ctype="application/pdf"):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return client.post(self.url(rid), {"file": SimpleUploadedFile(name, make_pdf_bytes(pages=5) if data is None else data, ctype)}, format="multipart")

    def test_replace_resets_to_draft_and_swaps_the_file(self, admin_client, ca, a, free, django_capture_on_commit_callbacks):
        rid = publish_pdf(admin_client, free, pages=2)
        CourseAccess.objects.create(student=a, course=free, status="active")
        before = Resource.objects.get(pk=rid)
        old_key, old_sha = before.storage_key, before.sha256
        storage = get_private_storage()
        assert storage.exists(old_key)
        with django_capture_on_commit_callbacks(execute=True):
            res = self.upload_new(admin_client, rid)
        assert res.status_code == 200
        body = res.json()["data"]
        assert body["status"] == "draft" and body["page_count"] == 5 and body["original_filename"] == "new.pdf"
        assert "storage_key" not in body
        after = Resource.objects.get(pk=rid)
        assert after.storage_key != old_key and after.sha256 != old_sha and after.published_at is None
        assert not storage.exists(old_key) and storage.exists(after.storage_key)
        assert ca.get(f"/api/student/viewing/resources/{rid}/pages/1/").status_code == 404  # hidden until republished
        admin_client.post(f"/api/admin/course/resources/{rid}/validate/")
        admin_client.post(f"/api/admin/course/resources/{rid}/publish/")
        assert ca.get(f"/api/student/viewing/resources/{rid}/pages/5/").status_code == 200
        assert AuditEvent.objects.filter(action="resource.replaced").exists()

    def test_invalid_files_are_rejected_and_nothing_changes(self, admin_client, free):
        rid = publish_pdf(admin_client, free)
        key = Resource.objects.get(pk=rid).storage_key
        for data, name, ctype in ((b"not a pdf", "x.pdf", "application/pdf"), (make_pdf_bytes(), "x.txt", "text/plain"), (b"", "e.pdf", "application/pdf")):
            assert self.upload_new(admin_client, rid, data, name, ctype).status_code in (400, 413)
        after = Resource.objects.get(pk=rid)
        assert after.storage_key == key and after.status == "published"

    def test_archived_resource_cannot_be_replaced(self, admin_client, free):
        rid = publish_pdf(admin_client, free)
        admin_client.post(f"/api/admin/course/resources/{rid}/archive/")
        assert self.upload_new(admin_client, rid).status_code == 409

    def test_admin_only(self, admin_client, student_client, free):
        rid = publish_pdf(admin_client, free)
        assert self.upload_new(student_client, rid).status_code == 403
        assert self.upload_new(APIClient(), rid).status_code == 401
        assert self.upload_new(admin_client, "00000000-0000-0000-0000-000000000000").status_code == 404


class TestAdminWalls:
    @pytest.mark.parametrize(
        "method,url",
        [
            ("get", "/api/admin/reports/dashboard/"), ("post", "/api/admin/course/"), ("get", "/api/admin/students/"),
            ("get", "/api/admin/students/approval-requests/"), ("get", "/api/admin/settings/"), ("get", "/api/admin/profile/"),
            ("get", "/api/admin/students/payments/"), ("get", "/api/admin/notifications/"),
        ],
    )
    def test_student_cannot_use_admin_apis(self, method, url, student_client):
        assert getattr(student_client, method)(url, **({"data": {}, "format": "json"} if method == "post" else {})).status_code == 403

    def test_admin_settings_never_contain_secrets(self, admin_client, settings):
        settings.STRIPE_SECRET_KEY = "sk_test_should_never_leak"
        settings.EMAIL_HOST_PASSWORD = "smtp-password-should-never-leak"
        body = admin_client.get("/api/admin/settings/").content.decode()
        for secret in ("sk_test_should_never_leak", "smtp-password-should-never-leak", settings.SECRET_KEY, settings.STRIPE_WEBHOOK_SECRET):
            assert secret not in body

    def test_dashboard_numbers_come_from_the_database(self, admin_client, a, b, free, paid):
        CourseAccess.objects.create(student=a, course=free, status="active")
        data = admin_client.get("/api/admin/reports/dashboard/").json()["data"]
        assert data["users"]["students"] == 2 and data["users"]["active"] == 2
        assert data["courses"]["published"] == 2 and data["access"]["active"] == 1
