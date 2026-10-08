"""Notification workflow: events, ownership, e-mail policy, SMTP failure, idempotency, envelope."""
import json
from unittest import mock

import pytest
from django.core import mail
from rest_framework.test import APIClient

from access.models import CourseAccess
from accounts.models import User
from courses.models import Course
from notifications import services as notifications
from notifications.models import Notification
from payments.models import Payment

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


def decide(admin_client, student, course, decision):
    return post(admin_client, f"/api/admin/students/{student.id}/decision/", {"decision": decision, "course": str(course.id)})


def types(user):
    # sorted: notifications created in the same clock tick share a created_at, so order is not asserted
    return sorted(Notification.objects.filter(user=user).values_list("type", flat=True))


def checkout(client, course):
    from access.models import CourseAccess
    from .conftest import approve_payment

    me = User.objects.get(pk=client.get("/api/accounts/me/").json()["data"]["id"])
    if not CourseAccess.objects.filter(student=me, course=course).exists():
        approve_payment(me, course)  # the admin's payment approval, which checkout now requires
    with mock.patch("payments.services.stripe.checkout.Session.create", return_value={"id": f"cs_{course.slug}", "url": "https://x.test"}):
        res = post(client, "/api/student/payment/create-checkout/", {"course": str(course.id)})
    return Payment.objects.get(pk=res.json()["data"]["id"])


# ------------------------------------------------------------------ student events

class TestStudentEvents:
    def test_payment_request_names_course_amount_and_currency(self, admin_client, a, paid):
        decide(admin_client, a, paid, "payment_required")
        note = Notification.objects.get(user=a, type="payment_requested")
        assert 'Paid' in note.message and "499.00" in note.message and "INR" in note.message and "Payment" in note.title
        assert note.data["course"] == str(paid.id) and note.data["amount"] == "499.00" and note.data["currency"] == "INR"
        assert note.data["action"] == "pay" and note.data["access"]

    def test_decisions_notify_the_student(self, admin_client, a, free, paid):
        decide(admin_client, a, free, "immediate")
        assert types(a) == ["access_granted"]
        other = Course.objects.create(title="Review", slug="review", status="published", access_mode="manual_approval")
        decide(admin_client, a, other, "manual")
        decide(admin_client, a, paid, "payment_required")
        assert types(a) == ["access_granted", "access_pending", "payment_requested"]

    def test_rejection_and_revocation_notify_the_student(self, admin_client, ca, a, free):
        post(ca, "/api/student/access/", {"course": str(free.id)})
        record = CourseAccess.objects.get(student=a, course=free)
        admin_client.patch(f"/api/admin/students/access/{record.id}/", {"action": "reject"}, format="json")
        assert types(a) == ["access_rejected"]
        record.status = "pending"
        record.save()
        admin_client.patch(f"/api/admin/students/access/{record.id}/", {"action": "approve"}, format="json")
        admin_client.patch(f"/api/admin/students/access/{record.id}/", {"action": "revoke"}, format="json")
        assert types(a) == ["access_granted", "access_rejected", "access_revoked"]

    def test_registration_decisions_notify_the_student(self, admin_client, db):
        p1 = User.objects.create_user("p1@example.com", PASSWORD, full_name="P1", status="pending")
        p2 = User.objects.create_user("p2@example.com", PASSWORD, full_name="P2", status="pending")
        admin_client.post(f"/api/admin/students/approval-requests/{p1.id}/approve/")
        admin_client.post(f"/api/admin/students/approval-requests/{p2.id}/reject/", {"reason": "No"}, format="json")
        assert types(p1) == ["registration_approved"] and types(p2) == ["registration_rejected"]

    def test_verified_payment_notifies_student_and_activates_access(self, a, ca, admin_client, paid):
        decide(admin_client, a, paid, "payment_required")
        payment = checkout(ca, paid)
        _, event_id = send_event("checkout.session.completed", session_obj(payment, amount_total=49900, currency="inr"))
        note = Notification.objects.get(user=a, type="payment_successful")
        assert "Paid" in note.message and "active" in note.message and note.data["event"] == event_id
        assert CourseAccess.objects.get(student=a, course=paid).status == "active"

    def test_failed_and_expired_payments_notify_the_student(self, a, ca, paid, admin_client):
        decide(admin_client, a, paid, "payment_required")
        payment = checkout(ca, paid)
        send_event("payment_intent.payment_failed", {"id": "pi_1", "object": "payment_intent", "metadata": {"payment_id": str(payment.id)}})
        note = Notification.objects.get(user=a, type="payment_failed")
        assert "Paid" in note.message and note.data["payment"] == str(payment.id)
        assert CourseAccess.objects.get(student=a, course=paid).status == "pending"  # no access without payment

    def test_new_material_notifies_only_students_who_can_open_the_course(self, admin_client, a, b, free):
        CourseAccess.objects.create(student=a, course=free, status="active")
        CourseAccess.objects.create(student=b, course=free, status="pending")
        rid = upload(admin_client, free, data=make_pdf_bytes(pages=1)).json()["data"]["id"]
        admin_client.post(f"/api/admin/course/resources/{rid}/validate/")
        assert types(a) == []  # nothing before it is published
        admin_client.post(f"/api/admin/course/resources/{rid}/publish/")
        assert types(a) == ["resource_available"] and types(b) == []
        assert "Free" in Notification.objects.get(user=a).message

    def test_course_published_still_reaches_active_students(self, admin_client, a, admin):
        draft = Course.objects.create(title="New", slug="new", status="draft", created_by=admin)
        admin_client.post(f"/api/admin/course/{draft.id}/publish/")
        assert "course_published" in types(a)


# ------------------------------------------------------------------ admin events

class TestAdminEvents:
    def feed(self, client):
        return [n["type"] for n in client.get("/api/admin/notifications/").json()["data"]]

    def test_registration_request_and_payment(self, admin_client, a, ca, free, paid):
        post(APIClient(), "/api/accounts/register/send-otp/", {"email": "new@example.com"})
        from .conftest import register_via_api

        register_via_api(APIClient(), "new@example.com")
        post(ca, "/api/student/access/", {"course": str(free.id)})
        decide(admin_client, a, paid, "payment_required")
        payment = checkout(ca, paid)
        send_event("checkout.session.completed", session_obj(payment, amount_total=49900, currency="inr"))
        assert {"new_registration", "access_requested", "payment_received"} <= set(self.feed(admin_client))

    def test_a_payment_mismatch_needs_admin_attention(self, admin_client, a, ca, paid):
        payment = checkout(ca, paid)
        send_event("checkout.session.completed", session_obj(payment, amount_total=100, currency="inr"))
        item = next(n for n in admin_client.get("/api/admin/notifications/").json()["data"] if n["type"] == "payment_attention")
        assert "Paid" in item["message"] and "NOT activated" in item["message"] and item["data"]["payment"] == str(payment.id)
        assert not CourseAccess.objects.filter(student=a, status="active").exists()

    def test_a_refund_needs_admin_attention_and_the_student_hears_about_access(self, admin_client, a, ca, paid):
        payment = checkout(ca, paid)
        send_event("checkout.session.completed", session_obj(payment, amount_total=49900, currency="inr"))
        send_event("charge.refunded", {"id": "ch_1", "object": "charge", "refunded": True, "payment_intent": "pi_test_1", "metadata": {"payment_id": str(payment.id)}})
        assert "payment_attention" in self.feed(admin_client)
        assert "access_revoked" in types(a)

    def test_students_never_receive_admin_events(self, admin_client, a, ca, paid):
        decide(admin_client, a, paid, "payment_required")
        payment = checkout(ca, paid)
        send_event("checkout.session.completed", session_obj(payment, amount_total=100, currency="inr"))
        assert not set(types(a)) & {"payment_received", "payment_attention", "new_registration", "access_requested"}


# ------------------------------------------------------------------ API ownership + envelope

class TestNotificationApi:
    @pytest.fixture
    def notes(self, a, b, admin):
        make = lambda u, t: Notification.objects.create(user=u, type="security", title=t, message="m")  # noqa: E731
        return make(a, "for A"), make(b, "for B"), make(admin, "for admin")

    def test_list_only_my_own(self, ca, cb, notes):
        mine = ca.get("/api/student/notifications/").json()
        assert [n["title"] for n in mine["data"]] == ["for A"] and mine["meta"]["count"] == 1 and mine["meta"]["unread_count"] == 1
        assert "for B" not in json.dumps(mine)
        assert [n["title"] for n in cb.get("/api/student/notifications/").json()["data"]] == ["for B"]

    def test_retrieve_own_and_not_others(self, ca, notes):
        a_note, b_note, _ = notes
        res = ca.get(f"/api/student/notifications/{a_note.id}/")
        assert res.status_code == 200 and res.json()["data"]["id"] == str(a_note.id)
        miss = ca.get(f"/api/student/notifications/{b_note.id}/")
        assert miss.status_code == 404 and miss.json()["error"]["code"] == "NOT_FOUND"
        assert "for B" not in miss.content.decode() and "b@example.com" not in miss.content.decode()

    def test_mark_read_own_and_not_others(self, ca, notes):
        a_note, b_note, _ = notes
        assert ca.post(f"/api/student/notifications/{a_note.id}/read/").json()["data"]["is_read"] is True
        a_note.refresh_from_db()
        assert a_note.read_at is not None
        assert ca.post(f"/api/student/notifications/{b_note.id}/read/").status_code == 404
        b_note.refresh_from_db()
        assert b_note.read_at is None

    def test_read_all_only_touches_my_own(self, ca, notes):
        a_note, b_note, admin_note = notes
        assert ca.post("/api/student/notifications/read-all/").json()["data"]["updated"] == 1
        b_note.refresh_from_db()
        admin_note.refresh_from_db()
        assert b_note.read_at is None and admin_note.read_at is None

    def test_cannot_delete_someone_elses(self, ca, notes):
        _, b_note, _ = notes
        assert ca.delete(f"/api/student/notifications/{b_note.id}/").status_code == 404
        assert Notification.objects.filter(pk=b_note.pk).exists()

    def test_roles_and_authentication(self, ca, admin_client, notes):
        a_note, _, admin_note = notes
        assert APIClient().get("/api/student/notifications/").status_code == 401
        assert APIClient().get("/api/admin/notifications/").status_code == 401
        assert ca.get("/api/admin/notifications/").status_code == 403
        assert admin_client.get("/api/student/notifications/").status_code == 403
        assert admin_client.get(f"/api/admin/notifications/{admin_note.id}/").status_code == 200
        assert admin_client.get(f"/api/admin/notifications/{a_note.id}/").status_code == 404  # not even an admin reads a student's

    def test_response_envelope(self, ca, notes):
        a_note = notes[0]
        ok = ca.get("/api/student/notifications/").json()
        assert set(ok) == {"success", "data", "meta"} and ok["success"] is True
        bad = ca.get(f"/api/student/notifications/{notes[1].id}/").json()
        assert set(bad) == {"success", "error"} and set(bad["error"]) == {"code", "message", "details"}
        assert set(ca.get(f"/api/student/notifications/{a_note.id}/").json()["data"]) >= {"id", "type", "title", "message", "data", "is_read", "created_at"}



# ------------------------------------------------------------------ e-mail policy and failure

class TestEmailBehaviour:
    def test_optional_email_can_be_switched_off_but_in_app_stays(self, a, ca, admin_client, free, django_capture_on_commit_callbacks):
        ca.patch("/api/student/settings/", {"email_notifications": False}, format="json")
        with django_capture_on_commit_callbacks(execute=True):
            decide(admin_client, a, free, "immediate")
        assert types(a) == ["access_granted"] and not mail.outbox

    def test_optional_email_is_sent_when_enabled(self, a, admin_client, free, django_capture_on_commit_callbacks):
        with django_capture_on_commit_callbacks(execute=True):
            decide(admin_client, a, free, "immediate")
        assert [m.to for m in mail.outbox] == [[a.email]]

    @pytest.mark.parametrize("kind", ["security", "payment_requested", "payment_failed", "access_rejected"])
    def test_mandatory_types_ignore_the_preference(self, a, kind, django_capture_on_commit_callbacks):
        a.email_notifications = False
        a.save()
        with django_capture_on_commit_callbacks(execute=True):
            notifications.send_notification(a, kind, detail="d", course="C", amount="1.00", currency="INR")
        assert len(mail.outbox) == 1 and Notification.objects.filter(user=a, type=kind).count() == 1

    def test_in_app_notification_survives_a_failing_mail_server(self, a, admin_client, paid, settings, django_capture_on_commit_callbacks):
        settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
        with mock.patch("django.core.mail.backends.smtp.EmailBackend.send_messages", side_effect=OSError("smtp down")):
            with django_capture_on_commit_callbacks(execute=True):
                res = decide(admin_client, a, paid, "payment_required")
        assert res.status_code == 200 and "smtp" not in res.content.decode()
        assert types(a) == ["payment_requested"]  # created, kept, never faked as delivered
        assert not mail.outbox

    def test_global_email_switch_still_stops_all_e_mail(self, a, admin_client, paid, django_capture_on_commit_callbacks):
        admin_client.patch("/api/admin/settings/", {"email_notifications_enabled": False}, format="json")
        with django_capture_on_commit_callbacks(execute=True):
            decide(admin_client, a, paid, "payment_required")
        assert types(a) == ["payment_requested"] and not mail.outbox


# ------------------------------------------------------------------ duplicate prevention

class TestNoDuplicates:
    def test_repeated_verified_webhook_notifies_once(self, a, ca, admin_client, paid):
        decide(admin_client, a, paid, "payment_required")
        payment = checkout(ca, paid)
        obj = session_obj(payment, amount_total=49900, currency="inr")
        _, event_id = send_event("checkout.session.completed", obj)
        for _ in range(3):
            send_event("checkout.session.completed", obj, event_id=event_id)
        assert types(a).count("payment_successful") == 1
        assert Notification.objects.filter(type="payment_received").count() == 1
        assert CourseAccess.objects.filter(student=a, course=paid).count() == 1

    def test_a_new_event_for_an_already_paid_payment_notifies_nothing_more(self, a, ca, admin_client, paid):
        payment = checkout(ca, paid)
        obj = session_obj(payment, amount_total=49900, currency="inr")
        send_event("checkout.session.completed", obj)
        send_event("checkout.session.async_payment_succeeded", obj)  # different event id, same payment
        assert types(a).count("payment_successful") == 1 and Notification.objects.filter(type="payment_received").count() == 1

    def test_a_late_failure_after_payment_does_not_notify(self, a, ca, paid):
        payment = checkout(ca, paid)
        send_event("checkout.session.completed", session_obj(payment, amount_total=49900, currency="inr"))
        send_event("payment_intent.payment_failed", {"id": "pi_1", "object": "payment_intent", "metadata": {"payment_id": str(payment.id)}})
        assert "payment_failed" not in types(a)

    def test_the_same_failure_twice_notifies_once(self, a, ca, paid):
        payment = checkout(ca, paid)
        obj = {"id": "pi_9", "object": "payment_intent", "metadata": {"payment_id": str(payment.id)}}
        send_event("payment_intent.payment_failed", obj)
        send_event("payment_intent.payment_failed", obj)
        assert types(a).count("payment_failed") == 1

    def test_repeating_the_same_admin_decision_is_not_a_new_event(self, admin_client, a, paid, free):
        for _ in range(3):
            decide(admin_client, a, paid, "payment_required")
        for _ in range(2):
            decide(admin_client, a, free, "manual")
        assert types(a).count("payment_requested") == 1 and types(a).count("access_pending") == 1

    def test_changing_the_decision_is_a_new_event(self, admin_client, a, paid):
        decide(admin_client, a, paid, "payment_required")
        decide(admin_client, a, paid, "manual")
        decide(admin_client, a, paid, "payment_required")
        assert types(a) == ["access_pending", "payment_requested", "payment_requested"]

    def test_notifications_are_not_an_audit_trail(self, admin_client, a, paid):
        from audit.models import AuditEvent

        decide(admin_client, a, paid, "payment_required")
        assert AuditEvent.objects.filter(action="access.payment_required").count() == 1
        for event in AuditEvent.objects.all():
            assert "message" not in json.dumps(event.metadata)
