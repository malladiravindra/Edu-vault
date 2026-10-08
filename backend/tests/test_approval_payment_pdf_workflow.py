"""Manual / immediate / payment course workflows end to end, with the PDF gate (protected viewer pages) checked at every step."""
from unittest import mock

import pytest
from rest_framework.test import APIClient

from access.models import CourseAccess
from access.services import evaluate_access
from audit.models import AuditEvent
from courses.models import Course
from notifications.models import Notification
from payments.models import Payment, StripeEvent

from .test_payments import send_event, session_obj
from .test_phase6_workflow import a, b, ca, cb, decide, post, publish_pdf, signed_in  # noqa: F401  (fixtures)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def stripe_keys(settings):
    settings.STRIPE_SECRET_KEY = "sk_test_dummy_for_pytest"
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test_secret_for_pytest"


def make(admin, mode, **extra):
    return Course.objects.create(title=f"C-{mode}", slug=f"c-{mode}", status="published", access_mode=mode, created_by=admin, **extra)


@pytest.fixture
def manual(admin):
    return make(admin, "manual_approval")


@pytest.fixture
def immediate(admin):
    return make(admin, "immediate")


@pytest.fixture
def paid(admin):
    return make(admin, "payment_required", price_amount="999.00", currency="INR")


def page(c, rid):
    return c.get(f"/api/student/viewing/resources/{rid}/pages/1/")


def checkout(c, course, **extra):
    with mock.patch("payments.services.stripe.checkout.Session.create", return_value={"id": f"cs_{course.slug}", "url": "https://x.test"}) as m:
        res = post(c, "/api/student/payment/create-checkout/", {"course": str(course.id), **extra})
    return res, m


class TestManual:
    def test_request_pending_admin_approves_then_pdf(self, admin_client, ca, a, manual, admin):
        rid = publish_pdf(admin_client, manual)
        res = post(ca, "/api/student/access/", {"course": str(manual.id)})
        assert res.status_code == 201 and res.json()["data"]["status"] == "pending"
        assert page(ca, rid).status_code == 403  # before approval
        assert AuditEvent.objects.filter(action="access.requested", actor=a).exists()
        record = CourseAccess.objects.get(student=a, course=manual)
        assert APIClient().patch(f"/api/admin/students/access/{record.id}/", {"action": "approve"}, format="json").status_code == 401
        assert ca.patch(f"/api/admin/students/access/{record.id}/", {"action": "approve"}, format="json").status_code == 403
        assert admin_client.patch(f"/api/admin/students/access/{record.id}/", {"action": "approve"}, format="json").status_code == 200
        record.refresh_from_db()
        assert record.status == "active" and record.payment_required is False
        assert page(ca, rid).status_code == 200  # after approval
        assert AuditEvent.objects.filter(action="access.granted", actor=admin).exists()
        assert Notification.objects.filter(user=a, type="access_granted").exists()

    def test_rejection_denies_and_notifies(self, admin_client, ca, a, manual):
        rid = publish_pdf(admin_client, manual)
        record = CourseAccess.objects.get(pk=post(ca, "/api/student/access/", {"course": str(manual.id)}).json()["data"]["id"])
        admin_client.patch(f"/api/admin/students/access/{record.id}/", {"action": "reject"}, format="json")
        assert page(ca, rid).status_code == 403
        assert Notification.objects.filter(user=a, type="access_rejected").exists()
        assert AuditEvent.objects.filter(action="access.rejected").exists()

    def test_decision_endpoint_roles(self, admin_client, ca, a, manual):
        url = f"/api/admin/students/{a.id}/decision/"
        body = {"decision": "immediate", "course": str(manual.id)}
        assert APIClient().post(url, body, format="json").status_code == 401
        assert ca.post(url, body, format="json").status_code == 403
        assert admin_client.post(url, body, format="json").status_code == 200


class TestImmediate:
    def test_request_activates_without_admin(self, admin_client, ca, a, immediate):
        rid = publish_pdf(admin_client, immediate)
        res = post(ca, "/api/student/access/", {"course": str(immediate.id)})
        assert res.status_code == 201 and res.json()["data"]["status"] == "active"
        record = CourseAccess.objects.get(student=a, course=immediate)
        assert record.source == "immediate" and record.decided_by_id is None  # no fake admin approval
        assert evaluate_access(a, immediate).allowed is True
        assert page(ca, rid).status_code == 200


class TestPayment:
    def test_full_sequence(self, admin_client, ca, a, paid, django_capture_on_commit_callbacks):
        rid = publish_pdf(admin_client, paid)
        assert page(ca, rid).status_code == 403  # nothing yet
        # the student asks; that is only a request, and checkout is refused until an admin approves it
        assert post(ca, "/api/student/access/", {"course": str(paid.id)}).status_code == 201
        assert evaluate_access(a, paid).state == "pending"
        res, create = checkout(ca, paid)
        assert res.status_code == 403 and res.json()["error"]["code"] == "PAYMENT_NOT_APPROVED"
        assert create.call_count == 0 and Payment.objects.count() == 0
        # admin approves for payment: access is NOT active
        with django_capture_on_commit_callbacks(execute=True):
            assert decide(admin_client, a, paid, "payment_required").status_code == 200
        record = CourseAccess.objects.get(student=a, course=paid)
        assert record.status == "pending" and record.payment_required is True
        assert evaluate_access(a, paid).state == "payment_required"
        assert page(ca, rid).status_code == 403
        assert AuditEvent.objects.filter(action="access.payment_required", target_id=str(record.id)).exists()
        assert Notification.objects.filter(user=a, type="payment_requested").exists()
        # the student's payment screen: price comes from the database
        req = ca.get("/api/student/payment-requests/").json()["data"][0]
        assert str(req["amount"]).startswith("999") and req["currency"] == "INR"
        # checkout: payment pending, still no access
        res, create = checkout(ca, paid)
        assert res.status_code == 201
        payment = Payment.objects.get(pk=res.json()["data"]["id"])
        assert payment.status == "pending" and create.call_args.kwargs["line_items"][0]["price_data"]["unit_amount"] == 99900
        assert page(ca, rid).status_code == 403
        # verified webhook: payment paid, access active, PDF opens
        with django_capture_on_commit_callbacks(execute=True):
            send_event("checkout.session.completed", session_obj(payment, amount_total=99900, currency="inr"))
        payment.refresh_from_db()
        record.refresh_from_db()
        assert payment.status == "paid" and record.status == "active" and record.payment_required is False and record.source == "payment"
        assert page(ca, rid).status_code == 200
        assert Notification.objects.filter(user=a, type="payment_successful").exists()
        actions = set(AuditEvent.objects.values_list("action", flat=True))
        assert {"payment.created", "payment.completed", "access.granted"} <= actions

    @pytest.mark.parametrize("event,payment_status,final", [
        ("checkout.session.async_payment_failed", "unpaid", "failed"),
        ("checkout.session.expired", "unpaid", "cancelled"),
    ])
    def test_failed_or_cancelled_payment_keeps_pdf_denied(self, event, payment_status, final, admin_client, ca, a, paid):
        rid = publish_pdf(admin_client, paid)
        decide(admin_client, a, paid, "payment_required")
        payment = Payment.objects.get(pk=checkout(ca, paid)[0].json()["data"]["id"])
        send_event(event, session_obj(payment, payment_status=payment_status, amount_total=99900, currency="inr"))
        assert Payment.objects.get(pk=payment.pk).status == final
        assert CourseAccess.objects.get(student=a, course=paid).status == "pending"
        assert evaluate_access(a, paid).state == "payment_required" and page(ca, rid).status_code == 403

    def test_unpaid_completed_session_waits(self, admin_client, ca, a, paid):
        rid = publish_pdf(admin_client, paid)
        decide(admin_client, a, paid, "payment_required")
        payment = Payment.objects.get(pk=checkout(ca, paid)[0].json()["data"]["id"])
        send_event("checkout.session.completed", session_obj(payment, payment_status="unpaid", amount_total=99900, currency="inr"))
        assert Payment.objects.get(pk=payment.pk).status == "pending" and page(ca, rid).status_code == 403

    def test_webhook_replay_changes_nothing(self, admin_client, ca, a, paid):
        publish_pdf(admin_client, paid)
        decide(admin_client, a, paid, "payment_required")
        payment = Payment.objects.get(pk=checkout(ca, paid)[0].json()["data"]["id"])
        obj = session_obj(payment, amount_total=99900, currency="inr")
        send_event("checkout.session.completed", obj, event_id="evt_replay")
        counts = (Payment.objects.count(), CourseAccess.objects.count(), AuditEvent.objects.count(), Notification.objects.count())
        assert send_event("checkout.session.completed", obj, event_id="evt_replay")[0].json()["data"]["result"] == "duplicate"
        assert (Payment.objects.count(), CourseAccess.objects.count(), AuditEvent.objects.count(), Notification.objects.count()) == counts
        assert StripeEvent.objects.filter(event_id="evt_replay").count() == 1


class TestStudentCannotBypassPayment:
    def test_client_supplied_state_is_ignored(self, admin_client, ca, a, b, paid):
        rid = publish_pdf(admin_client, paid)
        decide(admin_client, a, paid, "payment_required")
        bogus = {"student_id": str(a.id), "payment_status": "succeeded", "access_status": "active", "status": "active",
                 "price": 1, "amount": 1, "price_amount": "1.00", "currency": "USD", "payment_required": False}
        post(ca, "/api/student/access/", {"course": str(paid.id), **bogus})
        res, create = checkout(ca, paid, **bogus)
        assert res.status_code == 201
        payment = Payment.objects.get()
        assert str(payment.amount) == "999.00" and payment.currency == "INR" and payment.student_id == a.id  # server values
        assert create.call_args.kwargs["line_items"][0]["price_data"]["unit_amount"] == 99900
        assert CourseAccess.objects.filter(student=a, course=paid, status="active").count() == 0
        assert page(ca, rid).status_code == 403

    def test_cannot_mark_payment_paid_or_change_access(self, admin_client, ca, a, paid):
        rid = publish_pdf(admin_client, paid)
        decide(admin_client, a, paid, "payment_required")
        payment = Payment.objects.get(pk=checkout(ca, paid)[0].json()["data"]["id"])
        record = CourseAccess.objects.get(student=a, course=paid)
        for method, url in (("patch", f"/api/student/payments/{payment.id}/"), ("put", f"/api/student/payments/{payment.id}/"),
                            ("patch", f"/api/student/access/{record.id}/"), ("delete", f"/api/student/access/{record.id}/"),
                            ("patch", f"/api/admin/students/payments/{payment.id}/"),
                            ("patch", f"/api/admin/students/access/{record.id}/"), ("post", f"/api/admin/students/{a.id}/decision/")):
            res = getattr(ca, method)(url, {"status": "paid", "action": "approve", "decision": "immediate", "course": str(paid.id)}, format="json")
            assert res.status_code in (403, 404, 405), (method, url)
        assert send_event("checkout.session.completed", session_obj(payment, amount_total=99900, currency="inr"), signed=False)[0].status_code == 400
        assert ca.post("/api/payment/stripe/webhook/", {"type": "checkout.session.completed"}, format="json").status_code in (400, 401, 403)
        assert Payment.objects.get().status == "pending" and CourseAccess.objects.get().status == "pending" and page(ca, rid).status_code == 403

    def test_another_students_payment_and_course_ids_do_not_help(self, admin_client, ca, cb, a, b, paid, manual):
        rid = publish_pdf(admin_client, paid)
        decide(admin_client, a, paid, "payment_required")
        payment = Payment.objects.get(pk=checkout(ca, paid)[0].json()["data"]["id"])
        send_event("checkout.session.completed", session_obj(payment, amount_total=99900, currency="inr"))
        assert page(ca, rid).status_code == 200
        assert page(cb, rid).status_code == 403  # B never paid
        assert cb.get(f"/api/student/payments/{payment.id}/").status_code == 404
        assert cb.get(f"/api/student/course/{paid.id}/").json()["data"]["resources"] == []

    def test_repeated_checkout_reuses_one_open_payment(self, admin_client, ca, a, paid):
        decide(admin_client, a, paid, "payment_required")
        first = checkout(ca, paid)[0].json()["data"]["id"]
        open_session = {"status": "open", "url": "https://x.test"}
        with mock.patch("payments.services.stripe.checkout.Session.retrieve", return_value=open_session):
            second = checkout(ca, paid)[0].json()["data"]["id"]
        assert first == second and Payment.objects.count() == 1

    def test_no_second_checkout_once_paid(self, admin_client, ca, a, paid):
        decide(admin_client, a, paid, "payment_required")
        payment = Payment.objects.get(pk=checkout(ca, paid)[0].json()["data"]["id"])
        send_event("checkout.session.completed", session_obj(payment, amount_total=99900, currency="inr"))
        res, _ = checkout(ca, paid)
        assert res.status_code == 409 and res.json()["error"]["code"] == "ALREADY_HAS_ACCESS"


class TestDownloadMatrix:
    """The brief's table, using the project's states (the viewer is the only way to read the PDF)."""

    @pytest.mark.parametrize("mode,fields,expected", [
        ("manual_approval", {"status": "pending"}, 403),
        ("manual_approval", {"status": "active"}, 200),
        ("immediate", {"status": "active"}, 200),
        ("payment_required", {"status": "pending"}, 403),
        ("payment_required", {"status": "pending", "payment_required": True}, 403),
        ("payment_required", {"status": "active"}, 200),
        ("manual_approval", {"status": "active", "expires": "past"}, 403),
        ("payment_required", {"status": "revoked"}, 403),
    ])
    def test_matrix(self, mode, fields, expected, admin_client, ca, a, admin):
        from datetime import timedelta
        from django.utils import timezone
        extra = {"price_amount": "10.00"} if mode == "payment_required" else {}
        course = make(admin, mode, **extra)
        rid = publish_pdf(admin_client, course)
        fields = dict(fields)
        if fields.pop("expires", None):
            fields["expires_at"] = timezone.now() - timedelta(minutes=1)
        CourseAccess.objects.create(student=a, course=course, **fields)
        assert page(ca, rid).status_code == expected

    def test_suspended_student_with_active_access_is_denied(self, admin_client, ca, a, manual):
        rid = publish_pdf(admin_client, manual)
        CourseAccess.objects.create(student=a, course=manual, status="active")
        a.status = "suspended"
        a.save()
        assert page(ca, rid).status_code in (401, 403)

    def test_a_pending_payment_row_alone_never_grants_access(self, admin_client, ca, a, paid):
        rid = publish_pdf(admin_client, paid)
        Payment.objects.create(student=a, course=paid, amount="999.00", currency="INR", status="pending")
        assert page(ca, rid).status_code == 403


class TestMandatoryAdminPaymentApproval:
    def test_checkout_is_refused_until_the_admin_approves(self, admin_client, ca, a, paid):
        for stage in ("no record", "pending request"):
            if stage == "pending request":
                assert post(ca, "/api/student/access/", {"course": str(paid.id)}).status_code == 201
            res, create = checkout(ca, paid, approval_status="approved", access_status="payment_required", payment_required=True)
            assert res.status_code == 403 and res.json()["error"]["code"] == "PAYMENT_NOT_APPROVED", stage
            assert create.call_count == 0 and Payment.objects.count() == 0  # no Stripe session, no Payment row
        record = CourseAccess.objects.get(student=a, course=paid)
        assert record.status == "pending" and record.payment_required is False  # client fields changed nothing
        assert decide(admin_client, a, paid, "payment_required").status_code == 200
        res, create = checkout(ca, paid)
        assert res.status_code == 201 and create.call_count == 1 and Payment.objects.get().status == "pending"

    @pytest.mark.parametrize("state", [
        {"status": "rejected"}, {"status": "revoked"}, {"status": "pending", "payment_required": False},
    ])
    def test_rejected_revoked_and_unapproved_records_cannot_check_out(self, state, ca, a, paid):
        CourseAccess.objects.create(student=a, course=paid, **state)
        res, create = checkout(ca, paid)
        assert res.status_code == 403 and create.call_count == 0 and Payment.objects.count() == 0

    def test_a_rejection_after_approval_withdraws_the_right_to_pay(self, admin_client, ca, a, paid):
        decide(admin_client, a, paid, "payment_required")
        record = CourseAccess.objects.get(student=a, course=paid)
        admin_client.patch(f"/api/admin/students/access/{record.id}/", {"action": "reject"}, format="json")
        assert checkout(ca, paid)[0].status_code == 403

    def test_anonymous_and_admin_cannot_start_checkout(self, admin_client, paid):
        assert checkout(APIClient(), paid)[0].status_code == 401
        assert checkout(admin_client, paid)[0].status_code == 403

    def test_student_cannot_use_the_approval_endpoints(self, ca, a, paid):
        record = CourseAccess.objects.create(student=a, course=paid, status="pending")
        assert ca.post(f"/api/admin/students/{a.id}/decision/", {"decision": "payment_required", "course": str(paid.id)}, format="json").status_code == 403
        assert ca.patch(f"/api/admin/students/access/{record.id}/", {"action": "approve"}, format="json").status_code == 403
        assert checkout(ca, paid)[0].status_code == 403

    def test_manual_and_immediate_workflows_are_unchanged(self, admin_client, ca, a, manual, immediate):
        rid_m, rid_i = publish_pdf(admin_client, manual), publish_pdf(admin_client, immediate)
        assert post(ca, "/api/student/access/", {"course": str(manual.id)}).json()["data"]["status"] == "pending"
        assert page(ca, rid_m).status_code == 403
        assert post(ca, "/api/student/access/", {"course": str(immediate.id)}).json()["data"]["status"] == "active"
        assert page(ca, rid_i).status_code == 200
        res, _ = checkout(ca, manual)  # not a payment course: no checkout, as before
        assert res.status_code == 400 and res.json()["error"]["code"] == "PAYMENT_NOT_REQUIRED"

    def test_raw_download_is_still_404(self, admin_client, ca, a, paid):
        rid = publish_pdf(admin_client, paid)
        CourseAccess.objects.create(student=a, course=paid, status="active")
        assert ca.get(f"/api/student/viewing/resources/{rid}/download/").status_code == 404
        assert ca.get(f"/api/student/course/{paid.id}/resources/{rid}/download/").status_code == 404
