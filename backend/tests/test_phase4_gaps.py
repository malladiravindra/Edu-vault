"""Gaps confirmed open after Phase 3: admin notifications, course PUT/unpublish, grant guard, checkout reuse,
webhook throttle, registration detail, single-use 2FA challenge."""
import json
from unittest import mock

import pytest
from rest_framework.test import APIClient

from access.models import CourseAccess
from accounts.models import User
from audit.models import AuditEvent
from courses.models import Course
from notifications.models import Notification
from payments.models import Payment
from payments.views import StripeWebhookView

from .conftest import register_via_api, PASSWORD, approve_payment, admin_otp_from_outbox
from .test_payments import send_event, session_obj
from .test_resources import make_pdf_bytes, upload

pytestmark = pytest.mark.django_db


def post(client, url, data=None):
    return client.post(url, data or {}, format="json")


def code(res):
    return res.json().get("error", {}).get("code")


@pytest.fixture(autouse=True)
def stripe_keys(settings):
    settings.STRIPE_SECRET_KEY = "sk_test_dummy_for_pytest"
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test_secret_for_pytest"


@pytest.fixture
def course(admin):
    return Course.objects.create(title="Bio", slug="bio", status="published", access_mode="manual_approval", created_by=admin)


@pytest.fixture
def paid(admin, student):
    course = Course.objects.create(
        title="Paid", slug="paid", status="published", access_mode="payment_required",
        price_amount="25.00", currency="USD", created_by=admin,
    )
    approve_payment(student, course)  # checkout requires the admin's payment approval
    return course


@pytest.fixture
def approved(student):
    student.status = "active"
    student.save()
    return student


def admin_feed(client):
    return client.get("/api/admin/notifications/").json()["data"]


# ------------------------------------------------------------------ admin notifications

class TestAdminNotifications:
    def test_new_pending_registration_notifies_admins_only(self, admin_client, admin):
        res = register_via_api(APIClient(), "new@example.com", first_name="Newbie")
        assert res.status_code == 201
        feed = [n for n in admin_feed(admin_client) if n["type"] == "new_registration"]
        assert len(feed) == 1 and "Newbie" in feed[0]["message"]
        assert not Notification.objects.filter(user__role="student", type="new_registration").exists()

    def test_auto_approved_registration_does_not_notify(self, admin_client, settings):
        settings.REGISTRATION_REQUIRES_APPROVAL = False
        register_via_api(APIClient(), "auto@example.com", password=PASSWORD)
        assert not [n for n in admin_feed(admin_client) if n["type"] == "new_registration"]

    def test_access_request_notifies_admins(self, admin_client, student_client, approved, course):
        assert post(student_client, "/api/student/access/", {"course": str(course.id)}).status_code == 201
        feed = [n for n in admin_feed(admin_client) if n["type"] == "access_requested"]
        assert len(feed) == 1 and "Bio" in feed[0]["message"] and feed[0]["data"]["course"] == str(course.id)

    def test_immediate_course_does_not_notify(self, admin_client, student_client, approved, admin):
        free = Course.objects.create(title="Free", slug="free", status="published", access_mode="immediate", created_by=admin)
        post(student_client, "/api/student/access/", {"course": str(free.id)})
        assert not [n for n in admin_feed(admin_client) if n["type"] == "access_requested"]

    def test_verified_payment_notifies_admins(self, admin_client, student_client, approved, paid):
        with mock.patch("payments.services.stripe.checkout.Session.create", return_value={"id": "cs_n1", "url": "https://x.test"}):
            pid = post(student_client, "/api/student/payment/create-checkout/", {"course": str(paid.id)}).json()["data"]["id"]
        payment = Payment.objects.get(pk=pid)
        send_event("checkout.session.completed", session_obj(payment, amount_total=2500))
        feed = [n for n in admin_feed(admin_client) if n["type"] == "payment_received"]
        assert len(feed) == 1 and "Paid" in feed[0]["message"]
        assert Notification.objects.filter(user=approved, type="payment_successful").exists()

    def test_unsigned_webhook_creates_nothing(self, admin_client):
        send_event("checkout.session.completed", {"id": "cs_none"}, signed=False)
        assert not [n for n in admin_feed(admin_client) if n["type"] == "payment_received"]

    def test_each_admin_has_a_private_feed(self, admin_client, admin):
        other = User.objects.create_superuser("admin2@example.com", PASSWORD, full_name="Admin Two")
        register_via_api(APIClient(), "n@example.com", password=PASSWORD)
        mine = Notification.objects.get(user=admin, type="new_registration")
        theirs = Notification.objects.get(user=other, type="new_registration")
        assert mine.id != theirs.id
        assert admin_client.post(f"/api/admin/notifications/{theirs.id}/read/").status_code == 404
        assert admin_client.post(f"/api/admin/notifications/{mine.id}/read/").status_code == 200

    def test_students_cannot_read_the_admin_feed(self, student_client):
        assert student_client.get("/api/admin/notifications/").status_code == 403

    def test_suspended_or_student_accounts_are_not_recipients(self, admin_client, admin, student):
        suspended = User.objects.create_superuser("old-admin@example.com", PASSWORD, full_name="Old")
        suspended.status = "suspended"
        suspended.save()
        register_via_api(APIClient(), "n2@example.com", password=PASSWORD)
        recipients = set(Notification.objects.filter(type="new_registration").values_list("user_id", flat=True))
        assert recipients == {admin.id}


# ------------------------------------------------------------------ course PUT / unpublish

class TestCourseLifecycle:
    def test_put_replaces_all_editable_fields(self, admin_client, paid):
        url = f"/api/admin/course/{paid.id}/"
        res = admin_client.put(url, {"title": "Renamed"}, format="json")
        assert res.status_code == 200, res.content
        paid.refresh_from_db()
        assert paid.title == "Renamed" and paid.access_mode == "manual_approval" and paid.price_amount is None
        assert paid.description == "" and paid.access_duration_days is None
        assert paid.status == "published"  # status is never changed by PUT

    def test_put_validates_like_patch(self, admin_client, course):
        res = admin_client.put(
            f"/api/admin/course/{course.id}/", {"title": "T", "access_mode": "payment_required"}, format="json"
        )
        assert res.status_code == 400 and "price_amount" in res.json()["error"]["details"]["fields"]

    def test_put_cannot_set_status(self, admin_client, course):
        admin_client.put(f"/api/admin/course/{course.id}/", {"title": "T", "status": "archived"}, format="json")
        course.refresh_from_db()
        assert course.status == "published"

    def test_put_requires_title_and_admin(self, admin_client, student_client, course):
        assert admin_client.put(f"/api/admin/course/{course.id}/", {}, format="json").status_code == 400
        assert student_client.put(f"/api/admin/course/{course.id}/", {"title": "x"}, format="json").status_code == 403
        assert APIClient().put(f"/api/admin/course/{course.id}/", {"title": "x"}, format="json").status_code == 401

    def test_patch_still_partial(self, admin_client, paid):
        admin_client.patch(f"/api/admin/course/{paid.id}/", {"title": "Only title"}, format="json")
        paid.refresh_from_db()
        assert paid.title == "Only title" and str(paid.price_amount) == "25.00"

    def test_unpublish_hides_the_course_and_blocks_the_viewer(self, admin_client, student_client, approved, course):
        rid = upload(admin_client, course, data=make_pdf_bytes(pages=1)).json()["data"]["id"]
        admin_client.post(f"/api/admin/course/resources/{rid}/validate/")
        admin_client.post(f"/api/admin/course/resources/{rid}/publish/")
        CourseAccess.objects.create(student=approved, course=course, status="active")
        page = f"/api/student/viewing/resources/{rid}/pages/1/"
        assert student_client.get(page).status_code == 200

        res = post(admin_client, f"/api/admin/course/{course.id}/unpublish/")
        assert res.status_code == 200 and res.json()["data"]["status"] == "draft"
        assert student_client.get(page).status_code == 404
        assert student_client.get(f"/api/student/course/{course.id}/").status_code == 404
        assert AuditEvent.objects.filter(action="course.unpublished").exists()

        post(admin_client, f"/api/admin/course/{course.id}/publish/")
        assert student_client.get(page).status_code == 200  # the access record was kept

    def test_unpublish_only_from_published(self, admin_client, course):
        post(admin_client, f"/api/admin/course/{course.id}/unpublish/")
        res = post(admin_client, f"/api/admin/course/{course.id}/unpublish/")
        assert res.status_code == 409 and code(res) == "INVALID_STATE"
        archived = Course.objects.create(title="A", slug="a", status="archived")
        assert post(admin_client, f"/api/admin/course/{archived.id}/unpublish/").status_code == 409

    def test_unpublish_is_admin_only(self, student_client, course):
        assert post(student_client, f"/api/admin/course/{course.id}/unpublish/").status_code == 403
        assert post(APIClient(), f"/api/admin/course/{course.id}/unpublish/").status_code == 401

    def test_archived_course_cannot_be_viewed(self, admin_client, student_client, approved, course):
        rid = upload(admin_client, course, data=make_pdf_bytes(pages=1)).json()["data"]["id"]
        admin_client.post(f"/api/admin/course/resources/{rid}/validate/")
        admin_client.post(f"/api/admin/course/resources/{rid}/publish/")
        CourseAccess.objects.create(student=approved, course=course, status="active")
        post(admin_client, f"/api/admin/course/{course.id}/archive/")
        assert student_client.get(f"/api/student/viewing/resources/{rid}/pages/1/").status_code == 404


# ------------------------------------------------------------------ no access records for unpublished courses

class TestGrantGuard:
    @pytest.fixture
    def draft(self, admin):
        return Course.objects.create(title="Draft", slug="draft", status="draft", created_by=admin)

    def test_grant_on_draft_or_archived_is_refused(self, admin_client, approved, draft):
        archived = Course.objects.create(title="Arch", slug="arch", status="archived")
        for target in (draft, archived):
            res = post(admin_client, "/api/admin/students/access/grant/", {"course": str(target.id), "student": str(approved.id)})
            assert res.status_code == 409 and code(res) == "COURSE_UNAVAILABLE"
        assert not CourseAccess.objects.exists()

    def test_approving_a_pending_request_on_an_unpublished_course_is_refused(self, admin_client, approved, course):
        record = CourseAccess.objects.create(student=approved, course=course, status="pending")
        Course.objects.filter(pk=course.pk).update(status="draft")
        res = admin_client.patch(f"/api/admin/students/access/{record.id}/", {"action": "approve"}, format="json")
        assert res.status_code == 409
        record.refresh_from_db()
        assert record.status == "pending"

    def test_decision_on_draft_is_refused(self, admin_client, approved, draft):
        res = post(admin_client, f"/api/admin/students/{approved.id}/decision/", {"decision": "immediate", "course": str(draft.id)})
        assert res.status_code == 400

    def test_published_course_grant_still_works(self, admin_client, approved, course):
        res = post(admin_client, "/api/admin/students/access/grant/", {"course": str(course.id), "student": str(approved.id)})
        assert res.status_code == 201

    def test_paid_webhook_still_grants_after_unpublish(self, admin_client, student_client, approved, paid):
        with mock.patch("payments.services.stripe.checkout.Session.create", return_value={"id": "cs_g1", "url": "https://x.test"}):
            pid = post(student_client, "/api/student/payment/create-checkout/", {"course": str(paid.id)}).json()["data"]["id"]
        post(admin_client, f"/api/admin/course/{paid.id}/unpublish/")
        send_event("checkout.session.completed", session_obj(Payment.objects.get(pk=pid), amount_total=2500))
        assert CourseAccess.objects.get(student=approved, course=paid).status == "active"  # money was taken: honour it


# ------------------------------------------------------------------ checkout reuse

class TestCheckoutReuse:
    def checkout(self, client, course):
        return post(client, "/api/student/payment/create-checkout/", {"course": str(course.id)})

    def test_open_session_is_reused(self, student_client, approved, paid):
        with mock.patch("payments.services.stripe.checkout.Session.create", return_value={"id": "cs_r1", "url": "https://x.test/1"}) as create, \
                mock.patch("payments.services.stripe.checkout.Session.retrieve", return_value={"status": "open", "url": "https://x.test/1"}):
            first = self.checkout(student_client, paid).json()["data"]
            second = self.checkout(student_client, paid).json()["data"]
        assert first["id"] == second["id"] and second["checkout_url"] == "https://x.test/1"
        assert create.call_count == 1 and Payment.objects.count() == 1

    def test_expired_session_gets_a_new_payment(self, student_client, approved, paid):
        sessions = iter([{"id": "cs_r2", "url": "https://x.test/2"}, {"id": "cs_r3", "url": "https://x.test/3"}])
        with mock.patch("payments.services.stripe.checkout.Session.create", side_effect=lambda **kw: next(sessions)), \
                mock.patch("payments.services.stripe.checkout.Session.retrieve", return_value={"status": "expired", "url": None}):
            a = self.checkout(student_client, paid).json()["data"]
            b = self.checkout(student_client, paid).json()["data"]
        assert a["id"] != b["id"] and Payment.objects.count() == 2

    def test_price_change_is_never_served_from_an_old_session(self, student_client, approved, paid):
        sessions = iter([{"id": "cs_r4", "url": "https://x.test/4"}, {"id": "cs_r5", "url": "https://x.test/5"}])
        with mock.patch("payments.services.stripe.checkout.Session.create", side_effect=lambda **kw: next(sessions)), \
                mock.patch("payments.services.stripe.checkout.Session.retrieve", return_value={"status": "open", "url": "https://x.test/4"}):
            a = self.checkout(student_client, paid).json()["data"]
            Course.objects.filter(pk=paid.pk).update(price_amount="30.00")
            b = self.checkout(student_client, paid).json()["data"]
        assert a["id"] != b["id"] and b["amount"] == "30.00"

    def test_provider_error_while_checking_falls_back_to_a_new_session(self, student_client, approved, paid):
        import stripe

        sessions = iter([{"id": "cs_r6", "url": "https://x.test/6"}, {"id": "cs_r7", "url": "https://x.test/7"}])
        with mock.patch("payments.services.stripe.checkout.Session.create", side_effect=lambda **kw: next(sessions)), \
                mock.patch("payments.services.stripe.checkout.Session.retrieve", side_effect=stripe.APIConnectionError("down")):
            a = self.checkout(student_client, paid).json()["data"]
            b = self.checkout(student_client, paid).json()["data"]
        assert a["id"] != b["id"]

    def test_another_students_session_is_never_reused(self, student_client, approved, other_student, paid):
        other_student.status = "active"
        other_student.save()
        Payment.objects.create(student=other_student, course=paid, amount="25.00", currency="USD", stripe_checkout_session_id="cs_theirs")
        with mock.patch("payments.services.stripe.checkout.Session.create", return_value={"id": "cs_mine", "url": "https://x.test/m"}), \
                mock.patch("payments.services.stripe.checkout.Session.retrieve", return_value={"status": "open", "url": "https://x.test/theirs"}):
            res = self.checkout(student_client, paid).json()["data"]
        assert res["checkout_url"] == "https://x.test/m"


# ------------------------------------------------------------------ webhook throttle / amount / currency

class TestWebhookThrottle:
    def test_webhook_has_its_own_scope_not_the_anonymous_default(self):
        from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle

        assert StripeWebhookView.throttle_scope == "webhook"
        assert StripeWebhookView.throttle_classes == [ScopedRateThrottle]
        assert AnonRateThrottle not in StripeWebhookView.throttle_classes

    def test_signature_is_still_mandatory(self, db):
        assert send_event("checkout.session.completed", {"id": "x"}, signed=False)[0].status_code == 400

    def test_amount_and_currency_mismatch_do_not_activate(self, student_client, approved, paid):
        with mock.patch("payments.services.stripe.checkout.Session.create", return_value={"id": "cs_m1", "url": "https://x.test"}):
            pid = post(student_client, "/api/student/payment/create-checkout/", {"course": str(paid.id)}).json()["data"]["id"]
        payment = Payment.objects.get(pk=pid)
        send_event("checkout.session.completed", session_obj(payment, amount_total=100))
        send_event("checkout.session.completed", session_obj(payment, amount_total=2500, currency="eur"))
        payment.refresh_from_db()
        assert payment.status == "pending" and not CourseAccess.objects.filter(student=approved, status="active").exists()

    def test_duplicate_event_is_idempotent_and_notifies_once(self, admin_client, student_client, approved, paid):
        with mock.patch("payments.services.stripe.checkout.Session.create", return_value={"id": "cs_d1", "url": "https://x.test"}):
            pid = post(student_client, "/api/student/payment/create-checkout/", {"course": str(paid.id)}).json()["data"]["id"]
        payment = Payment.objects.get(pk=pid)
        _, eid = send_event("checkout.session.completed", session_obj(payment, amount_total=2500))
        send_event("checkout.session.completed", session_obj(payment, amount_total=2500), event_id=eid)
        assert CourseAccess.objects.filter(student=approved, course=paid).count() == 1
        assert len([n for n in admin_feed(admin_client) if n["type"] == "payment_received"]) == 1


# ------------------------------------------------------------------ registration detail

class TestRegistrationDetail:
    def test_detail_lists_only_that_students_access_and_payments(self, admin_client, approved, other_student, course, paid):
        CourseAccess.objects.create(student=approved, course=course, status="pending")
        CourseAccess.objects.create(student=other_student, course=paid, status="active")
        Payment.objects.create(student=approved, course=paid, amount="25.00", currency="USD")
        Payment.objects.create(student=other_student, course=paid, amount="25.00", currency="USD")
        data = admin_client.get(f"/api/admin/students/approval-requests/{approved.id}/").json()["data"]
        assert data["email"] == approved.email and data["status"] == "active"
        assert sorted(a["course"] for a in data["accesses"]) == sorted([str(course.id), str(paid.id)])  # `paid` carries the student's payment approval
        assert {a["course"]: a["state"] for a in data["accesses"]}[str(course.id)] == "pending"
        assert len(data["payments"]) == 1 and data["payments"][0]["course"] == str(paid.id)
        assert "password" not in json.dumps(data)

    def test_detail_of_a_new_registration_is_empty_not_missing(self, admin_client, student):
        data = admin_client.get(f"/api/admin/students/approval-requests/{student.id}/").json()["data"]
        assert data["accesses"] == [] and data["payments"] == []

    def test_detail_stays_admin_only(self, student_client, other_student):
        assert student_client.get(f"/api/admin/students/approval-requests/{other_student.id}/").status_code == 403


# ------------------------------------------------------------------ single-use 2FA challenge

class TestChallengeSingleUse:
    def challenge(self, admin):
        return post(APIClient(), "/api/admin/login/", {"email": admin.email, "password": PASSWORD}).json()["data"]["challenge_token"]

    def test_a_used_challenge_cannot_be_replayed(self, admin_client, admin):
        challenge = self.challenge(admin)
        otp = admin_otp_from_outbox(admin.email)
        ok = post(APIClient(), "/api/admin/login/2fa/verify/", {"challenge_token": challenge, "otp": otp})
        again = post(APIClient(), "/api/admin/login/2fa/verify/", {"challenge_token": challenge, "otp": otp})
        assert ok.status_code == 200
        assert again.status_code == 401 and code(again) == "INVALID_CHALLENGE"

    def test_failed_attempts_do_not_burn_the_challenge(self, admin_client, admin):
        challenge = self.challenge(admin)
        otp = admin_otp_from_outbox(admin.email)
        assert post(APIClient(), "/api/admin/login/2fa/verify/", {"challenge_token": challenge, "otp": "000000" if otp != "000000" else "000001"}).status_code == 401
        good = post(APIClient(), "/api/admin/login/2fa/verify/", {"challenge_token": challenge, "otp": otp})
        assert good.status_code == 200

    def test_a_used_challenge_cannot_be_replayed_with_another_code(self, admin_client, admin):
        challenge = self.challenge(admin)
        post(APIClient(), "/api/admin/login/2fa/verify/", {"challenge_token": challenge, "otp": admin_otp_from_outbox(admin.email)})
        res = post(APIClient(), "/api/admin/login/2fa/verify/", {"challenge_token": challenge, "otp": "123456"})
        assert res.status_code == 401 and code(res) == "INVALID_CHALLENGE"

    def test_each_login_gets_a_fresh_challenge(self, admin):
        assert self.challenge(admin) != self.challenge(admin)
