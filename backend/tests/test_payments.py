import hashlib
import hmac
import itertools
import json
import time
from unittest import mock

import pytest
import stripe
from rest_framework.test import APIClient

from access.models import CourseAccess
from accounts.models import User
from audit.models import AuditEvent
from courses.models import Course
from payments.models import Payment, StripeEvent

from .conftest import register_via_api, PASSWORD, auth_client, login_student, approve_payment, minted_client

pytestmark = pytest.mark.django_db

WEBHOOK_SECRET = "whsec_test_secret_for_pytest"
_counter = itertools.count(1)


@pytest.fixture(autouse=True)
def stripe_settings(settings):
    settings.STRIPE_SECRET_KEY = "sk_test_dummy_for_pytest"
    settings.STRIPE_WEBHOOK_SECRET = WEBHOOK_SECRET


@pytest.fixture
def paid_course(admin):
    return Course.objects.create(
        title="Paid Course", slug="paid", status="published", access_mode="payment_required",
        price_amount="49.00", currency="USD", created_by=admin,
    )


@pytest.fixture
def stripe_create():
    def fake(**kwargs):
        n = next(_counter)
        return {"id": f"cs_test_{n}", "url": f"https://checkout.stripe.test/pay/cs_test_{n}"}

    with mock.patch("payments.services.stripe.checkout.Session.create", side_effect=fake) as patched:
        yield patched


def checkout(client, course):
    return client.post("/api/student/payment/create-checkout/", {"course": str(course.id)}, format="json")


def sign(payload, secret=WEBHOOK_SECRET, timestamp=None):
    ts = int(timestamp or time.time())
    digest = hmac.new(secret.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def send_event(event_type, obj, event_id=None, secret=WEBHOOK_SECRET, signed=True):
    event = {
        "id": event_id or f"evt_{next(_counter)}", "object": "event", "type": event_type,
        "data": {"object": obj},
    }
    payload = json.dumps(event)
    headers = {"HTTP_STRIPE_SIGNATURE": sign(payload, secret)} if signed else {}
    res = APIClient().post("/api/payment/stripe/webhook/", data=payload, content_type="application/json", **headers)
    return res, event["id"]


def session_obj(payment, **over):
    obj = {
        "id": payment.stripe_checkout_session_id, "object": "checkout.session", "payment_status": "paid",
        "amount_total": 4900, "currency": "usd", "payment_intent": "pi_test_1",
        "client_reference_id": str(payment.id), "metadata": {"payment_id": str(payment.id)},
    }
    obj.update(over)
    return obj


@pytest.fixture
def pending(student_client, student, paid_course, stripe_create):
    approve_payment(student, paid_course)
    res = checkout(student_client, paid_course)
    return Payment.objects.get(pk=res.json()["data"]["id"])


class TestCreateCheckout:
    def test_creates_pending_payment_with_server_side_price(self, student_client, student, paid_course, stripe_create):
        approve_payment(student, paid_course)
        res = student_client.post(
            "/api/student/payment/create-checkout/",
            {"course": str(paid_course.id), "amount": "0.01", "currency": "EUR", "student": "x", "status": "paid"},
            format="json",
        )
        body = res.json()["data"]
        assert res.status_code == 201 and body["status"] == "pending" and body["checkout_url"].startswith("https://")
        payment = Payment.objects.get()
        assert payment.student == student and str(payment.amount) == "49.00" and payment.currency == "USD"
        assert payment.stripe_checkout_session_id.startswith("cs_test_")
        kwargs = stripe_create.call_args.kwargs
        assert kwargs["line_items"][0]["price_data"]["unit_amount"] == 4900
        assert kwargs["metadata"]["payment_id"] == str(payment.id)
        assert kwargs["idempotency_key"] == f"checkout-{payment.id}"
        assert AuditEvent.objects.filter(action="payment.created").exists()

    def test_does_not_grant_access(self, student_client, student, paid_course, stripe_create):
        approve_payment(student, paid_course)
        checkout(student_client, paid_course)
        assert CourseAccess.objects.filter(status="active").count() == 0

    def test_not_a_paid_course(self, student_client, admin, stripe_create):
        c = Course.objects.create(title="Free", slug="free", status="published", access_mode="immediate", created_by=admin)
        res = checkout(student_client, c)
        assert res.status_code == 400 and res.json()["error"]["code"] == "PAYMENT_NOT_REQUIRED"

    def test_unpublished_or_unknown_course(self, student_client, paid_course, stripe_create):
        Course.objects.filter(pk=paid_course.pk).update(status="draft")
        assert checkout(student_client, paid_course).status_code == 404
        assert student_client.post("/api/student/payment/create-checkout/", {"course": "nope"}, format="json").status_code == 400

    def test_already_has_access(self, student_client, student, paid_course, stripe_create, admin):
        from access.services import grant_course_access

        grant_course_access(student=student, course=paid_course, source="payment")
        assert checkout(student_client, paid_course).status_code == 409

    def test_revoked_cannot_repurchase(self, student_client, student, paid_course, stripe_create):
        CourseAccess.objects.create(student=student, course=paid_course, status="revoked")
        res = checkout(student_client, paid_course)
        assert res.status_code == 403 and res.json()["error"]["code"] == "ACCESS_REVOKED"

    def test_auth_required(self, paid_course, admin_client, stripe_create):
        assert checkout(APIClient(), paid_course).status_code == 401
        assert checkout(admin_client, paid_course).status_code == 403

    def test_pending_registration_cannot_pay(self, db, paid_course, stripe_create):
        c = APIClient()
        res = register_via_api(c, "n@example.com", password=PASSWORD)
        assert login_student(APIClient(), "n@example.com").status_code == 403  # pending: no sign-in at all
        user = User.objects.get(email="n@example.com")
        assert checkout(minted_client(user), paid_course).status_code == 403

    def test_provider_error_marks_failed(self, student_client, student, paid_course):
        approve_payment(student, paid_course)
        with mock.patch("payments.services.stripe.checkout.Session.create", side_effect=stripe.StripeError("boom")):
            res = checkout(student_client, paid_course)
        assert res.status_code == 502 and "boom" not in res.content.decode()
        assert Payment.objects.get().status == "failed"

    def test_not_configured(self, student_client, student, paid_course, settings):
        approve_payment(student, paid_course)
        settings.STRIPE_SECRET_KEY = ""
        assert checkout(student_client, paid_course).status_code == 503


class TestWebhookSecurity:
    def test_unsigned_event_rejected(self, pending):
        res, _ = send_event("checkout.session.completed", session_obj(pending), signed=False)
        assert res.status_code == 400 and res.json()["error"]["code"] == "INVALID_SIGNATURE"
        assert CourseAccess.objects.filter(status="active").count() == 0 and StripeEvent.objects.count() == 0

    def test_wrong_secret_rejected(self, pending):
        res, _ = send_event("checkout.session.completed", session_obj(pending), secret="whsec_attacker")
        assert res.status_code == 400
        assert Payment.objects.get().status == "pending"

    def test_stale_timestamp_rejected(self, pending):
        payload = json.dumps({"id": "evt_old", "type": "checkout.session.completed", "data": {"object": session_obj(pending)}})
        res = APIClient().post(
            "/api/payment/stripe/webhook/", data=payload, content_type="application/json",
            HTTP_STRIPE_SIGNATURE=sign(payload, timestamp=time.time() - 3600),
        )
        assert res.status_code == 400

    def test_tampered_body_rejected(self, pending):
        payload = json.dumps({"id": "evt_t", "type": "checkout.session.completed", "data": {"object": session_obj(pending)}})
        header = sign(payload)
        res = APIClient().post(
            "/api/payment/stripe/webhook/", data=payload.replace("4900", "1"), content_type="application/json",
            HTTP_STRIPE_SIGNATURE=header,
        )
        assert res.status_code == 400

    def test_garbage_payload(self, db):
        res = APIClient().post(
            "/api/payment/stripe/webhook/", data="not json", content_type="application/json", HTTP_STRIPE_SIGNATURE="t=1,v1=x"
        )
        assert res.status_code == 400

    def test_webhook_not_configured(self, pending, settings):
        settings.STRIPE_WEBHOOK_SECRET = ""
        res, _ = send_event("checkout.session.completed", session_obj(pending))
        assert res.status_code == 503

    def test_student_token_cannot_fake_payment(self, student_client, pending):
        """The success redirect / an authenticated client must never activate access."""
        res = student_client.post("/api/payment/stripe/webhook/", {"payment": str(pending.id), "status": "paid"}, format="json")
        assert res.status_code == 400
        assert student_client.get(f"/api/student/payments/{pending.id}/").json()["data"]["status"] == "pending"
        assert CourseAccess.objects.filter(status="active").count() == 0


class TestWebhookProcessing:
    def test_paid_activates_access(self, pending, student, paid_course):
        res, event_id = send_event("checkout.session.completed", session_obj(pending))
        assert res.status_code == 200 and res.json()["data"]["result"] == "processed"
        pending.refresh_from_db()
        assert pending.status == "paid" and pending.paid_at and pending.stripe_event_id == event_id
        assert pending.stripe_payment_intent_id == "pi_test_1"
        access = CourseAccess.objects.get(student=student, course=paid_course)
        assert access.status == "active" and access.source == "payment"
        assert StripeEvent.objects.get(event_id=event_id).payment == pending
        actions = set(AuditEvent.objects.values_list("action", flat=True))
        assert {"payment.completed", "access.granted", "stripe.webhook.processed"} <= actions

    def test_duplicate_event_is_idempotent(self, pending):
        _, event_id = send_event("checkout.session.completed", session_obj(pending), event_id="evt_dup")
        paid_at = Payment.objects.get().paid_at
        res, _ = send_event("checkout.session.completed", session_obj(pending), event_id="evt_dup")
        assert res.status_code == 200 and res.json()["data"]["result"] == "duplicate"
        assert StripeEvent.objects.filter(event_id="evt_dup").count() == 1
        assert AuditEvent.objects.filter(action="payment.completed").count() == 1
        assert CourseAccess.objects.count() == 1 and Payment.objects.get().paid_at == paid_at

    def test_new_event_for_settled_payment_is_noop(self, pending):
        send_event("checkout.session.completed", session_obj(pending))
        send_event("checkout.session.async_payment_succeeded", session_obj(pending))
        assert AuditEvent.objects.filter(action="payment.completed").count() == 1
        assert CourseAccess.objects.count() == 1

    def test_amount_mismatch_not_activated(self, pending):
        send_event("checkout.session.completed", session_obj(pending, amount_total=100))
        assert Payment.objects.get().status == "pending" and CourseAccess.objects.filter(status="active").count() == 0
        assert AuditEvent.objects.filter(action="payment.mismatch").exists()

    def test_currency_mismatch_not_activated(self, pending):
        send_event("checkout.session.completed", session_obj(pending, currency="eur"))
        assert Payment.objects.get().status == "pending" and CourseAccess.objects.filter(status="active").count() == 0

    def test_unpaid_session_waits_for_async_confirmation(self, pending):
        send_event("checkout.session.completed", session_obj(pending, payment_status="unpaid"))
        assert Payment.objects.get().status == "pending" and CourseAccess.objects.filter(status="active").count() == 0
        send_event("checkout.session.async_payment_succeeded", session_obj(pending))
        assert Payment.objects.get().status == "paid" and CourseAccess.objects.count() == 1

    def test_failed_then_paid(self, pending):
        send_event("checkout.session.async_payment_failed", session_obj(pending))
        assert Payment.objects.get().status == "failed" and CourseAccess.objects.filter(status="active").count() == 0
        send_event("checkout.session.completed", session_obj(pending))
        assert Payment.objects.get().status == "paid" and CourseAccess.objects.count() == 1

    def test_payment_intent_failed_found_by_metadata(self, pending):
        intent = {"id": "pi_x", "object": "payment_intent", "metadata": {"payment_id": str(pending.id)}}
        send_event("payment_intent.payment_failed", intent)
        assert Payment.objects.get().status == "failed"
        assert AuditEvent.objects.filter(action="payment.failed").exists()

    def test_expired_session_cancels(self, pending):
        send_event("checkout.session.expired", session_obj(pending, payment_status="unpaid"))
        assert Payment.objects.get().status == "cancelled" and CourseAccess.objects.filter(status="active").count() == 0

    def test_failure_does_not_downgrade_paid(self, pending):
        send_event("checkout.session.completed", session_obj(pending))
        send_event("checkout.session.expired", session_obj(pending))
        assert Payment.objects.get().status == "paid"

    def test_full_refund_revokes_access(self, pending, student, paid_course):
        send_event("checkout.session.completed", session_obj(pending))
        charge = {"id": "ch_1", "object": "charge", "payment_intent": "pi_test_1", "refunded": True}
        send_event("charge.refunded", charge)
        assert Payment.objects.get().status == "refunded"
        assert CourseAccess.objects.get(student=student, course=paid_course).status == "revoked"
        assert AuditEvent.objects.filter(action="payment.refunded").exists()

    def test_partial_refund_keeps_access(self, pending, student, paid_course):
        send_event("checkout.session.completed", session_obj(pending))
        send_event("charge.refunded", {"id": "ch_2", "object": "charge", "payment_intent": "pi_test_1", "refunded": False})
        assert Payment.objects.get().status == "paid"
        assert CourseAccess.objects.get(student=student, course=paid_course).status == "active"

    def test_unknown_event_and_unknown_payment_are_acknowledged(self, db):
        res, event_id = send_event("customer.created", {"id": "cus_1"})
        assert res.status_code == 200 and StripeEvent.objects.filter(event_id=event_id).exists()
        res2, _ = send_event("checkout.session.completed", {"id": "cs_unknown", "payment_status": "paid", "metadata": {"payment_id": "garbage"}})
        assert res2.status_code == 200

    def test_failure_rolls_back_everything_so_stripe_can_retry(self, pending):
        with mock.patch("payments.services.grant_course_access", side_effect=RuntimeError("db down")):
            res, event_id = send_event("checkout.session.completed", session_obj(pending), event_id="evt_retry")
        assert res.status_code == 500 and "db down" not in res.content.decode()
        assert Payment.objects.get().status == "pending"
        assert not StripeEvent.objects.filter(event_id="evt_retry").exists()
        retry, _ = send_event("checkout.session.completed", session_obj(pending), event_id="evt_retry")
        assert retry.json()["data"]["result"] == "processed" and Payment.objects.get().status == "paid"

    def test_zero_decimal_currency_conversion(self):
        from payments.services import to_minor_units

        assert to_minor_units("49.00", "usd") == 4900 and to_minor_units("500", "JPY") == 500
        assert to_minor_units("19.99", "USD") == 1999


class TestPaymentReads:
    def test_student_reads_own_only(self, student_client, other_student, paid_course, pending):
        theirs = Payment.objects.create(student=other_student, course=paid_course, amount="49.00", currency="USD")
        assert student_client.get(f"/api/student/payments/{pending.id}/").status_code == 200
        assert student_client.get(f"/api/student/payments/{theirs.id}/").status_code == 404
        mine = student_client.get("/api/student/payments/").json()
        assert mine["meta"]["count"] == 1
        assert "stripe_checkout_session_id" not in mine["data"][0]

    def test_admin_list_filter_detail(self, admin_client, pending):
        assert admin_client.get("/api/admin/students/payments/?status=PENDING").json()["meta"]["count"] == 1
        assert admin_client.get("/api/admin/students/payments/?status=paid").json()["meta"]["count"] == 0
        detail = admin_client.get(f"/api/admin/students/payments/{pending.id}/").json()["data"]
        assert detail["stripe_checkout_session_id"] == pending.stripe_checkout_session_id

    def test_student_cannot_use_admin_payment_apis(self, student_client, pending):
        assert student_client.get("/api/admin/students/payments/").status_code == 403
        assert student_client.get(f"/api/admin/students/payments/{pending.id}/").status_code == 403

    def test_db_constraint_positive_amount(self, student, paid_course):
        from django.db import IntegrityError, transaction

        with pytest.raises(IntegrityError), transaction.atomic():
            Payment.objects.create(student=student, course=paid_course, amount=0, currency="USD")


class TestUserDeletionKeepsFinancialRecords:
    def test_cannot_delete_student_with_payments(self, admin_client, student, paid_course):
        Payment.objects.create(student=student, course=paid_course, amount="49.00", currency="USD", status="paid")
        res = admin_client.delete(f"/api/admin/students/{student.id}/")
        assert res.status_code == 409 and res.json()["error"]["code"] == "USER_IN_USE"
        from accounts.models import User

        assert User.objects.filter(pk=student.pk).exists() and Payment.objects.count() == 1

    def test_can_delete_student_without_payments(self, admin_client, student):
        assert admin_client.delete(f"/api/admin/students/{student.id}/").status_code == 200
