"""Phase 3 security hardening: sessions, refresh tokens, lockout, admin TOTP policy, authorization."""
import json
import time
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from access.models import CourseAccess
from accounts import services
from accounts.models import User
from audit.models import AuditEvent
from courses.models import Course
from notifications.models import Notification
from payments.models import Payment
from resources.models import Resource

from .conftest import PASSWORD, admin_otp_from_outbox, auth_client
from .test_payments import send_event
from .test_resources import make_pdf_bytes, upload

pytestmark = pytest.mark.django_db

LOGIN = "/api/accounts/login/"
ADMIN_LOGIN = "/api/admin/login/"


def post(client, url, data=None, **extra):
    return client.post(url, data or {}, format="json", **extra)


def code(res):
    return res.json().get("error", {}).get("code")


def new_client(tokens=None, ip=None):
    c = APIClient(**({"REMOTE_ADDR": ip} if ip else {}))
    if tokens:
        auth_client(c, tokens)
    return c


def sign_in(email="student@example.com", ip=None):
    c = new_client(ip=ip)
    res = post(c, LOGIN, {"email": email, "password": PASSWORD})
    assert res.status_code == 200, res.content
    tokens = res.json()["data"]["tokens"]
    return auth_client(c, tokens), tokens


# ------------------------------------------------------------------ per-device sessions

class TestPerDeviceSessions:
    def test_logout_on_one_device_keeps_the_other(self, student):
        a, tokens_a = sign_in()
        b, _ = sign_in()
        assert post(a, "/api/accounts/logout/", {"refresh": tokens_a["refresh"]}).status_code == 200
        assert a.get("/api/accounts/me/").status_code == 401
        assert b.get("/api/accounts/me/").status_code == 200

    def test_inactivity_timeout_is_per_device(self, student):
        a, tokens_a = sign_in()
        b, _ = sign_in()
        sid = RefreshToken(tokens_a["refresh"])["sid"]
        services.end_session(student.id, sid)
        res = a.get("/api/accounts/me/")
        assert res.status_code == 401 and code(res) == "SESSION_EXPIRED"
        assert b.get("/api/accounts/me/").status_code == 200

    def test_each_sign_in_gets_its_own_session_id(self, student):
        _, t1 = sign_in()
        _, t2 = sign_in()
        assert RefreshToken(t1["refresh"])["sid"] != RefreshToken(t2["refresh"])["sid"]

    def test_refresh_keeps_the_same_session(self, student):
        _, tokens = sign_in()
        sid = RefreshToken(tokens["refresh"])["sid"]
        new = post(APIClient(), "/api/accounts/refresh/", {"refresh": tokens["refresh"]}).json()["data"]["tokens"]
        assert RefreshToken(new["refresh"])["sid"] == sid
        assert new_client(new).get("/api/accounts/me/").status_code == 200

    def test_password_change_revokes_every_other_device(self, student):
        a, tokens_a = sign_in()
        b, _ = sign_in()
        res = post(b, "/api/accounts/password-change/", {"current_password": PASSWORD, "new_password": "An0ther-Str0ng-Pass!"})
        assert res.status_code == 200
        assert a.get("/api/accounts/me/").status_code == 401
        assert post(APIClient(), "/api/accounts/refresh/", {"refresh": tokens_a["refresh"]}).status_code == 401
        assert new_client(res.json()["data"]["tokens"]).get("/api/accounts/me/").status_code == 200

    def test_suspension_revokes_every_device(self, admin_client, student):
        a, _ = sign_in()
        b, _ = sign_in()
        assert admin_client.post(f"/api/admin/students/{student.id}/suspend/").status_code == 200
        assert a.get("/api/accounts/me/").status_code == 401 and b.get("/api/accounts/me/").status_code == 401
        student.status = "active"
        student.save()
        assert post(APIClient(), LOGIN, {"email": student.email, "password": PASSWORD}).status_code == 200

    def test_token_without_session_claims_is_rejected(self, student):
        legacy = RefreshToken.for_user(student)  # signed correctly but not issued by the login flow
        assert new_client({"access": str(legacy.access_token)}).get("/api/accounts/me/").status_code == 401


# ------------------------------------------------------------------ refresh tokens

class TestRefreshTokens:
    def test_valid_refresh(self, student):
        _, tokens = sign_in()
        res = post(APIClient(), "/api/accounts/refresh/", {"refresh": tokens["refresh"]})
        assert res.status_code == 200 and res.json()["data"]["tokens"]["refresh"] != tokens["refresh"]

    def test_expired_refresh(self, student):
        _, tokens = sign_in()
        token = RefreshToken(tokens["refresh"])
        token.set_exp(lifetime=-timedelta(seconds=5))
        res = post(APIClient(), "/api/accounts/refresh/", {"refresh": str(token)})
        assert res.status_code == 401 and code(res) == "INVALID_REFRESH_TOKEN"

    def test_access_token_is_not_a_refresh_token(self, student):
        _, tokens = sign_in()
        assert post(APIClient(), "/api/accounts/refresh/", {"refresh": tokens["access"]}).status_code == 401

    def test_garbage_refresh(self, db):
        res = post(APIClient(), "/api/accounts/refresh/", {"refresh": "not-a-token"})
        assert res.status_code == 401 and code(res) == "INVALID_REFRESH_TOKEN"

    def test_logged_out_refresh_is_revoked(self, student):
        c, tokens = sign_in()
        post(c, "/api/accounts/logout/", {"refresh": tokens["refresh"]})
        assert post(APIClient(), "/api/accounts/refresh/", {"refresh": tokens["refresh"]}).status_code == 401

    def test_rotated_token_reuse_ends_the_session(self, student):
        _, tokens = sign_in()
        new = post(APIClient(), "/api/accounts/refresh/", {"refresh": tokens["refresh"]}).json()["data"]["tokens"]
        assert post(APIClient(), "/api/accounts/refresh/", {"refresh": tokens["refresh"]}).status_code == 401
        assert post(APIClient(), "/api/accounts/refresh/", {"refresh": new["refresh"]}).status_code == 401
        assert new_client(new).get("/api/accounts/me/").status_code == 401
        assert AuditEvent.objects.filter(action="auth.refresh.reuse_detected").exists()

    def test_reuse_only_ends_that_device(self, student):
        _, a = sign_in()
        b, _ = sign_in()
        post(APIClient(), "/api/accounts/refresh/", {"refresh": a["refresh"]})
        post(APIClient(), "/api/accounts/refresh/", {"refresh": a["refresh"]})  # replay
        assert b.get("/api/accounts/me/").status_code == 200

    def test_refresh_after_user_is_suspended(self, admin_client, student):
        _, tokens = sign_in()
        admin_client.post(f"/api/admin/students/{student.id}/suspend/")
        assert post(APIClient(), "/api/accounts/refresh/", {"refresh": tokens["refresh"]}).status_code == 401

    def test_failed_logins_do_not_reveal_which_part_was_wrong(self, student):
        wrong_pw = post(APIClient(), LOGIN, {"email": student.email, "password": "nope-nope-nope"})
        ghost = post(APIClient(), LOGIN, {"email": "ghost@example.com", "password": "nope-nope-nope"})
        assert wrong_pw.status_code == ghost.status_code == 401
        assert wrong_pw.json() == ghost.json()

    def test_sensitive_values_never_reach_the_audit_log(self, student):
        c, tokens = sign_in()
        post(APIClient(), LOGIN, {"email": student.email, "password": "wrong-Password-1"})
        post(c, "/api/accounts/logout/", {"refresh": tokens["refresh"]})
        dump = json.dumps(list(AuditEvent.objects.values("action", "actor_email", "metadata", "target_id")), default=str)
        for secret in (PASSWORD, "wrong-Password-1", tokens["refresh"], tokens["access"]):
            assert secret not in dump
        assert {"auth.login.success", "auth.login.failed", "auth.logout"} <= set(
            AuditEvent.objects.values_list("action", flat=True)
        )


# ------------------------------------------------------------------ lockout

class TestLoginLockout:
    def fail(self, email, ip, times=1):
        out = None
        for _ in range(times):
            out = post(new_client(ip=ip), LOGIN, {"email": email, "password": "wrong-Password-1"})
        return out

    def test_one_client_cannot_lock_the_victim_out_elsewhere(self, student, settings):
        self.fail(student.email, "10.0.0.1", settings.LOGIN_MAX_ATTEMPTS)
        attacker = post(new_client(ip="10.0.0.1"), LOGIN, {"email": student.email, "password": PASSWORD})
        assert attacker.status_code == 429 and code(attacker) == "ACCOUNT_LOCKED"
        owner = post(new_client(ip="10.0.0.2"), LOGIN, {"email": student.email, "password": PASSWORD})
        assert owner.status_code == 200

    def test_other_accounts_from_the_same_ip_are_unaffected(self, student, other_student, settings):
        self.fail(student.email, "10.0.0.1", settings.LOGIN_MAX_ATTEMPTS)
        res = post(new_client(ip="10.0.0.1"), LOGIN, {"email": other_student.email, "password": PASSWORD})
        assert res.status_code == 200

    def test_distributed_guessing_trips_the_email_wide_lock(self, student, settings):
        total = settings.LOGIN_MAX_ATTEMPTS * services.EMAIL_WIDE_LOCK_FACTOR
        for n in range(total):
            self.fail(student.email, f"10.1.{n // 200}.{n % 200 + 1}")
        res = post(new_client(ip="10.9.9.9"), LOGIN, {"email": student.email, "password": PASSWORD})
        assert res.status_code == 429

    def test_unknown_email_is_throttled_the_same_way(self, db, settings):
        res = self.fail("ghost@example.com", "10.0.0.1", settings.LOGIN_MAX_ATTEMPTS)
        again = post(new_client(ip="10.0.0.1"), LOGIN, {"email": "ghost@example.com", "password": "x"})
        assert res.status_code == 401 and again.status_code == 429  # same behaviour as a real account: no signal about whether the account exists

    def test_successful_login_resets_the_counter(self, student, settings):
        self.fail(student.email, "10.0.0.1", settings.LOGIN_MAX_ATTEMPTS - 1)
        assert post(new_client(ip="10.0.0.1"), LOGIN, {"email": student.email, "password": PASSWORD}).status_code == 200
        self.fail(student.email, "10.0.0.1", settings.LOGIN_MAX_ATTEMPTS - 1)
        assert post(new_client(ip="10.0.0.1"), LOGIN, {"email": student.email, "password": PASSWORD}).status_code == 200

    def test_lockout_expires(self, student, settings):
        settings.LOGIN_LOCKOUT_SECONDS = 1
        self.fail(student.email, "10.0.0.1", settings.LOGIN_MAX_ATTEMPTS)
        assert post(new_client(ip="10.0.0.1"), LOGIN, {"email": student.email, "password": PASSWORD}).status_code == 429
        time.sleep(1.2)
        assert post(new_client(ip="10.0.0.1"), LOGIN, {"email": student.email, "password": PASSWORD}).status_code == 200

    def test_admin_login_uses_the_same_protection(self, admin, settings):
        for _ in range(settings.LOGIN_MAX_ATTEMPTS):
            post(new_client(ip="10.0.0.1"), ADMIN_LOGIN, {"email": admin.email, "password": "wrong-Password-1"})
        res = post(new_client(ip="10.0.0.1"), ADMIN_LOGIN, {"email": admin.email, "password": PASSWORD})
        assert res.status_code == 429
        assert post(new_client(ip="10.0.0.2"), ADMIN_LOGIN, {"email": admin.email, "password": PASSWORD}).status_code == 200


# ------------------------------------------------------------------ admin TOTP policy

class TestAdminTotpPolicy:
    def challenge(self, admin):
        return post(APIClient(), ADMIN_LOGIN, {"email": admin.email, "password": PASSWORD}).json()["data"]

    def test_password_alone_never_yields_tokens(self, admin):
        data = self.challenge(admin)
        assert data["requires_two_factor"] is True and "tokens" not in data and "access" not in json.dumps(data)

    def test_cannot_log_in_as_admin_through_the_student_endpoint(self, admin):
        res = post(APIClient(), LOGIN, {"email": admin.email, "password": PASSWORD})
        assert res.status_code == 401 and "tokens" not in res.content.decode()

    def test_the_emailed_code_is_the_only_second_factor(self, admin):
        data = self.challenge(admin)
        res = post(APIClient(), "/api/admin/login/2fa/verify/", {"challenge_token": data["challenge_token"], "otp": admin_otp_from_outbox(admin.email)})
        assert res.status_code == 200 and "access" in res.json()["data"]["tokens"]

    def test_an_emailed_code_cannot_be_replayed(self, admin_client, admin):
        first_challenge = self.challenge(admin)["challenge_token"]
        otp = admin_otp_from_outbox(admin.email)
        first = post(APIClient(), "/api/admin/login/2fa/verify/", {"challenge_token": first_challenge, "otp": otp})
        replay = post(APIClient(), "/api/admin/login/2fa/verify/", {"challenge_token": self.challenge(admin)["challenge_token"], "otp": otp})
        assert first.status_code == 200
        assert replay.status_code == 401 and code(replay) == "INVALID_TWO_FACTOR_CODE"

    def test_invalid_and_valid_otp(self, admin_client, admin):
        challenge = self.challenge(admin)["challenge_token"]
        otp = admin_otp_from_outbox(admin.email)
        bad = post(APIClient(), "/api/admin/login/2fa/verify/", {"challenge_token": challenge, "otp": "000000" if otp != "000000" else "000001"})
        good = post(APIClient(), "/api/admin/login/2fa/verify/", {"challenge_token": challenge, "otp": otp})
        assert bad.status_code == 401 and good.status_code == 200

    def test_suspended_admin_cannot_continue(self, admin_client, admin):
        data = self.challenge(admin)
        admin.status = "suspended"
        admin.save()
        res = post(APIClient(), "/api/admin/login/2fa/verify/", {"challenge_token": data["challenge_token"], "otp": admin_otp_from_outbox(admin.email)})
        assert res.status_code == 401
        assert post(APIClient(), ADMIN_LOGIN, {"email": admin.email, "password": PASSWORD}).status_code == 403

    def test_students_are_not_put_through_two_factor(self, student):
        res = post(APIClient(), LOGIN, {"email": student.email, "password": PASSWORD})
        assert res.status_code == 200 and "tokens" in res.json()["data"]

    def test_student_cannot_obtain_an_admin_challenge(self, student):
        res = post(APIClient(), ADMIN_LOGIN, {"email": student.email, "password": PASSWORD})
        assert res.status_code == 401 and "challenge_token" not in res.content.decode()


# ------------------------------------------------------------------ role separation

ADMIN_URLS = [
    "/api/admin/students/", "/api/admin/course/", "/api/admin/reports/dashboard/", "/api/admin/audit-logs/",
    "/api/admin/settings/", "/api/admin/notifications/", "/api/admin/students/payments/",
]
STUDENT_URLS = [
    "/api/student/dashboard/", "/api/student/profile/", "/api/student/course/", "/api/student/access/",
    "/api/student/payments/", "/api/student/learning-history/", "/api/student/notifications/",
]


class TestRoleSeparation:
    @pytest.mark.parametrize("url", ADMIN_URLS)
    def test_admin_endpoints(self, url, student_client, admin_client):
        assert APIClient().get(url).status_code == 401
        assert student_client.get(url).status_code == 403
        assert admin_client.get(url).status_code == 200

    @pytest.mark.parametrize("url", STUDENT_URLS)
    def test_student_endpoints(self, url, student_client, admin_client):
        assert APIClient().get(url).status_code == 401
        assert student_client.get(url).status_code == 200
        assert admin_client.get(url).status_code == 403

    def test_role_is_never_taken_from_the_request(self, student_client, student):
        student_client.patch("/api/accounts/me/", {"full_name": "X", "role": "admin", "status": "active", "is_staff": True}, format="json")
        student.refresh_from_db()
        assert student.role == "student" and not student.is_staff

    def test_decision_endpoint_is_admin_only(self, student_client, admin_client, student):
        course = Course.objects.create(title="C", slug="c", status="published", access_mode="manual_approval")
        url = f"/api/admin/students/{student.id}/decision/"
        body = {"decision": "pending", "course": str(course.id)}
        assert post(APIClient(), url, body).status_code == 401
        assert post(student_client, url, body).status_code == 403
        assert post(admin_client, url, body).status_code == 200


# ------------------------------------------------------------------ object-level authorization

class TestObjectLevelAuthorization:
    def make_course(self, **kw):
        return Course.objects.create(title="C", slug=kw.pop("slug", "c"), status="published", **kw)

    def test_notifications_are_private(self, student_client, other_student):
        theirs = Notification.objects.create(user=other_student, type="security", title="t", message="m")
        base = f"/api/student/notifications/{theirs.id}/"
        assert student_client.post(base + "read/").status_code == 404
        assert student_client.delete(base).status_code == 404
        listing = student_client.get("/api/student/notifications/").json()
        assert str(theirs.id) not in json.dumps(listing)

    def test_payments_are_private(self, student_client, other_student):
        course = self.make_course(access_mode="payment_required", price_amount="5.00")
        pay = Payment.objects.create(student=other_student, course=course, amount="5.00", currency="USD")
        assert student_client.get(f"/api/student/payments/{pay.id}/").status_code == 404
        assert str(pay.id) not in json.dumps(student_client.get("/api/student/payments/").json())

    def test_access_records_are_private(self, student_client, other_student):
        course = self.make_course()
        record = CourseAccess.objects.create(student=other_student, course=course, status="active")
        assert student_client.get(f"/api/student/access/{record.id}/").status_code == 404
        assert str(record.id) not in json.dumps(student_client.get("/api/student/access/").json())

    def test_learning_history_and_profile_are_own_only(self, student_client, student, other_student, admin_client):
        course = self.make_course()
        pdf = upload(admin_client, course, data=make_pdf_bytes(pages=1)).json()["data"]["id"]
        admin_client.post(f"/api/admin/course/resources/{pdf}/validate/")
        admin_client.post(f"/api/admin/course/resources/{pdf}/publish/")
        CourseAccess.objects.create(student=other_student, course=course, status="active")
        other, _ = sign_in("other@example.com")
        assert other.get(f"/api/student/viewing/resources/{pdf}/pages/1/").status_code == 200
        assert student_client.get("/api/student/learning-history/").json()["meta"]["count"] == 0
        assert other.get("/api/student/learning-history/").json()["meta"]["count"] == 1
        assert student_client.get("/api/student/profile/").json()["data"]["email"] == student.email

    def test_viewer_duration_of_another_students_view_is_refused(self, student, other_student, admin_client):
        course = self.make_course()
        rid = upload(admin_client, course, data=make_pdf_bytes(pages=1)).json()["data"]["id"]
        admin_client.post(f"/api/admin/course/resources/{rid}/validate/")
        admin_client.post(f"/api/admin/course/resources/{rid}/publish/")
        for s in (student, other_student):
            CourseAccess.objects.create(student=s, course=course, status="active")
        owner, _ = sign_in("other@example.com")
        view_id = owner.get(f"/api/student/viewing/resources/{rid}/pages/1/").json()["data"]["view_id"]
        intruder, _ = sign_in()
        res = post(intruder, f"/api/student/viewing/resources/{rid}/activity/", {"view_id": view_id, "duration_seconds": 30})
        assert res.status_code == 404

    def test_student_cannot_read_audit_logs(self, student_client):
        assert student_client.get("/api/admin/audit-logs/").status_code == 403

    def test_audit_log_is_read_only_for_admins_too(self, admin_client):
        event = AuditEvent.objects.first()
        url = f"/api/admin/audit-logs/{event.id}/"
        for method in ("patch", "put", "delete", "post"):
            assert getattr(admin_client, method)(url, {}, format="json").status_code == 405


# ------------------------------------------------------------------ course access vs viewer

class TestCourseAccessEnforcement:
    @pytest.fixture
    def setup(self, admin_client, student):
        course = Course.objects.create(
            title="Paid", slug="paid", status="published", access_mode="payment_required", price_amount="9.00"
        )
        rid = upload(admin_client, course, data=make_pdf_bytes(pages=1)).json()["data"]["id"]
        admin_client.post(f"/api/admin/course/resources/{rid}/validate/")
        admin_client.post(f"/api/admin/course/resources/{rid}/publish/")
        client, _ = sign_in()
        return course, f"/api/student/viewing/resources/{rid}/pages/1/", client

    def state(self, course, student, **kw):
        CourseAccess.objects.update_or_create(student=student, course=course, defaults=kw)

    def test_active(self, setup, student):
        course, url, client = setup
        self.state(course, student, status="active")
        assert client.get(url).status_code == 200

    def test_pending(self, setup, student):
        course, url, client = setup
        self.state(course, student, status="pending")
        assert client.get(url).status_code == 403

    def test_payment_required(self, setup, student):
        _, url, client = setup
        res = client.get(url)  # no request and no admin decision yet: nothing to pay for
        assert res.status_code == 403 and code(res) == "ACCESS_REQUESTABLE"

    def test_payment_required_by_admin_decision(self, setup, student, admin_client):
        course, url, client = setup
        self.state(course, student, status="revoked")
        post(admin_client, f"/api/admin/students/{student.id}/decision/", {"decision": "payment_required", "course": str(course.id)})
        assert client.get(url).status_code == 403

    def test_expired(self, setup, student):
        course, url, client = setup
        self.state(course, student, status="active", expires_at=timezone.now() - timedelta(seconds=1))
        res = client.get(url)
        assert res.status_code == 403 and code(res) == "ACCESS_EXPIRED"

    def test_revoked(self, setup, student):
        course, url, client = setup
        self.state(course, student, status="revoked")
        assert client.get(url).status_code == 403

    def test_suspended_student(self, setup, student):
        course, url, client = setup
        self.state(course, student, status="active")
        student.status = "suspended"
        student.save()
        assert client.get(url).status_code == 401

    def test_unpublished_resource_is_not_found(self, setup, student):
        course, url, client = setup
        self.state(course, student, status="active")
        Resource.objects.update(status="archived")
        assert client.get(url).status_code == 404

    def test_page_parameters_are_validated(self, setup, student):
        course, url, client = setup
        self.state(course, student, status="active")
        assert client.get(url.replace("/pages/1/", "/pages/0/")).status_code == 404
        assert client.get(url.replace("/pages/1/", "/pages/99/")).status_code == 404
        assert client.get(url.replace("/pages/1/", "/pages/-1/")).status_code == 404


# ------------------------------------------------------------------ Stripe webhook

class TestWebhookSecurity:
    @pytest.fixture(autouse=True)
    def keys(self, settings):
        settings.STRIPE_SECRET_KEY = "sk_test_dummy_for_pytest"
        settings.STRIPE_WEBHOOK_SECRET = "whsec_test_secret_for_pytest"

    def test_needs_a_valid_signature(self, db):
        res, _ = send_event("checkout.session.completed", {"id": "cs_x"}, signed=False)
        assert res.status_code == 400 and code(res) == "INVALID_SIGNATURE"
        res, _ = send_event("checkout.session.completed", {"id": "cs_x"}, secret="whsec_wrong")
        assert res.status_code == 400

    def test_malformed_body_fails_safely(self, db):
        res = APIClient().post("/api/payment/stripe/webhook/", data="{not json", content_type="application/json", HTTP_STRIPE_SIGNATURE="t=1,v1=x")
        assert res.status_code == 400 and "Traceback" not in res.content.decode()

    def test_clients_cannot_activate_access(self, student_client, student):
        course = Course.objects.create(title="P", slug="p", status="published", access_mode="payment_required", price_amount="5.00")
        res = student_client.post("/api/payment/stripe/webhook/", {"type": "checkout.session.completed"}, format="json")
        assert res.status_code == 400
        assert not CourseAccess.objects.filter(student=student, course=course).exists()
        assert student_client.post("/api/student/payment/create-checkout/", {"course": str(course.id), "status": "paid"}, format="json").status_code == 403  # no admin payment approval
        assert not Payment.objects.exists()
        assert not Payment.objects.filter(status="paid").exists()


# ------------------------------------------------------------------ errors and URL layout

class TestErrorsAndUrls:
    def test_errors_use_the_envelope_and_leak_nothing(self, student_client):
        res = student_client.get("/api/student/viewing/resources/not-a-uuid/")
        body = res.content.decode()
        assert res.status_code == 404 and res.json()["success"] is False
        for leak in ("Traceback", "site-packages", "C:\\\\", "SECRET", "django.db"):
            assert leak not in body

    @pytest.mark.parametrize(
        "path",
        [
            "/api/admin/login/", "/api/admin/login/2fa/verify/", "/api/admin/course/", "/api/admin/students/",
            "/api/admin/reports/dashboard/", "/api/admin/audit-logs/", "/api/admin/settings/",
            "/api/admin/notifications/", "/api/student/dashboard/", "/api/student/profile/", "/api/student/course/",
            "/api/student/access/", "/api/student/payments/", "/api/student/learning-history/",
            "/api/student/notifications/",
        ],
    )
    def test_phase2_urls_still_resolve(self, path):
        from django.urls import resolve

        resolve(path)

    @pytest.mark.parametrize(
        "path",
        ["/api/accounts/admin/login/", "/api/admin/courses/", "/api/admin/users/", "/api/course/", "/api/viewing/", "/api/notifications/"],
    )
    def test_removed_urls_stay_removed(self, path, client):
        assert client.get(path).status_code == 404
