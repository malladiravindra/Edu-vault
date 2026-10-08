"""Student registration (email OTP) -> login -> profile/courses -> forgot password."""
import json
import logging
from unittest import mock

import pytest
from django.core import mail
from django.core.cache import cache
from rest_framework.test import APIClient

from access.models import CourseAccess
from accounts.models import User
from audit.models import AuditEvent
from courses.models import Course

from .conftest import PASSWORD, auth_client, login_student, otp_from_outbox, register_via_api

pytestmark = pytest.mark.django_db

SEND = "/api/accounts/register/send-otp/"
VERIFY = "/api/accounts/register/verify-otp/"
REGISTER = "/api/accounts/register/"
EMAIL = "john@example.com"


def post(client, url, data=None):
    return client.post(url, data or {}, format="json")


def code(res):
    return res.json().get("error", {}).get("code")


def payload(**over):
    body = {
        "first_name": "John", "middle_name": "M", "last_name": "Doe", "phone_number": "9876543210",
        "email": EMAIL, "password": PASSWORD, "confirm_password": PASSWORD,
    }
    body.update(over)
    return body


def verify_email(client, email=EMAIL):
    post(client, SEND, {"email": email})
    return post(client, VERIFY, {"email": email, "otp": otp_from_outbox(email)})


# ------------------------------------------------------------------ send OTP

class TestSendOtp:
    def test_sends_an_email_and_never_returns_the_otp(self, client):
        res = post(client, SEND, {"email": EMAIL})
        assert res.status_code == 200
        assert res.json() == {"success": True, "data": {"message": "Verification OTP sent successfully."}, "meta": {}}
        sent = mail.outbox[-1]
        otp = otp_from_outbox(EMAIL)
        assert sent.to == [EMAIL] and sent.subject == "EduVault Email Verification OTP"
        assert otp and otp not in res.content.decode()
        assert "expire in 10 minutes" in sent.body and "please ignore this email" in sent.body

    def test_otp_is_random_and_not_logged(self, client, caplog):
        caplog.set_level(logging.DEBUG)
        post(client, SEND, {"email": "a@example.com"})
        post(client, SEND, {"email": "b@example.com"})
        codes = {otp_from_outbox("a@example.com"), otp_from_outbox("b@example.com")}
        assert all(c and len(c) == 6 for c in codes)
        for c in codes:
            assert c not in caplog.text
        dumped = json.dumps(list(AuditEvent.objects.values("action", "actor_email", "metadata")), default=str)
        assert not any(c in dumped for c in codes)

    def test_existing_email_gets_the_same_answer_and_no_email(self, client, student):
        fresh = post(APIClient(), SEND, {"email": "brand-new@example.com"})
        sent_before = len(mail.outbox)
        known = post(client, SEND, {"email": student.email})
        assert known.status_code == fresh.status_code == 200 and known.json() == fresh.json()
        assert len(mail.outbox) == sent_before

    @pytest.mark.parametrize("body", [{}, {"email": ""}, {"email": "not-an-email"}])
    def test_invalid_email(self, client, body):
        res = post(client, SEND, body)
        assert res.status_code == 400 and code(res) == "VALIDATION_ERROR" and not mail.outbox

    def test_resend_cooldown(self, client, settings):
        settings.OTP_RESEND_COOLDOWN_SECONDS = 60
        assert post(client, SEND, {"email": EMAIL}).status_code == 200
        res = post(client, SEND, {"email": EMAIL})
        assert res.status_code == 429 and code(res) == "OTP_COOLDOWN" and res.json()["error"]["details"]["retry_after"] == 60
        assert len(mail.outbox) == 1
        assert post(client, SEND, {"email": "other@example.com"}).status_code == 200

    def test_resending_replaces_the_previous_code(self, client):
        post(client, SEND, {"email": EMAIL})
        first = otp_from_outbox(EMAIL)
        post(client, SEND, {"email": EMAIL})
        second = otp_from_outbox(EMAIL)
        if first != second:
            assert post(client, VERIFY, {"email": EMAIL, "otp": first}).status_code == 400
        assert post(client, VERIFY, {"email": EMAIL, "otp": second}).status_code == 200

    def test_audited_without_the_code(self, client):
        post(client, SEND, {"email": EMAIL})
        event = AuditEvent.objects.get(action="auth.register.otp_sent")
        assert event.actor_email == EMAIL and otp_from_outbox(EMAIL) not in json.dumps(event.metadata)


# ------------------------------------------------------------------ verify OTP

class TestVerifyOtp:
    def test_correct_code(self, client):
        post(client, SEND, {"email": EMAIL})
        res = post(client, VERIFY, {"email": EMAIL, "otp": otp_from_outbox(EMAIL)})
        assert res.status_code == 200 and res.json()["data"]["email_verified"] is True
        assert AuditEvent.objects.filter(action="auth.register.email_verified").exists()

    def test_wrong_code(self, client):
        post(client, SEND, {"email": EMAIL})
        otp = otp_from_outbox(EMAIL)
        res = post(client, VERIFY, {"email": EMAIL, "otp": "000000" if otp != "000000" else "111111"})
        assert res.status_code == 400 and code(res) == "INVALID_OTP"
        assert AuditEvent.objects.filter(action="auth.otp.failed", actor_email=EMAIL).exists()

    def test_expired_code(self, client):
        post(client, SEND, {"email": EMAIL})
        otp = otp_from_outbox(EMAIL)
        cache.clear()  # what expiry does to the stored code
        assert code(post(client, VERIFY, {"email": EMAIL, "otp": otp})) == "INVALID_OTP"

    def test_code_expires_with_the_configured_lifetime(self, client, settings):
        settings.OTP_EXPIRY_SECONDS = 1
        post(client, SEND, {"email": EMAIL})
        otp = otp_from_outbox(EMAIL)
        import time

        time.sleep(1.2)
        assert post(client, VERIFY, {"email": EMAIL, "otp": otp}).status_code == 400

    def test_single_use(self, client):
        post(client, SEND, {"email": EMAIL})
        otp = otp_from_outbox(EMAIL)
        assert post(client, VERIFY, {"email": EMAIL, "otp": otp}).status_code == 200
        assert post(client, VERIFY, {"email": EMAIL, "otp": otp}).status_code == 400

    def test_attempt_limit_burns_the_code(self, client, settings):
        post(client, SEND, {"email": EMAIL})
        otp = otp_from_outbox(EMAIL)
        wrong = "000000" if otp != "000000" else "111111"
        for _ in range(settings.OTP_MAX_ATTEMPTS):
            assert post(client, VERIFY, {"email": EMAIL, "otp": wrong}).status_code == 400
        assert post(client, VERIFY, {"email": EMAIL, "otp": otp}).status_code == 400

    def test_code_is_bound_to_its_email(self, client):
        post(client, SEND, {"email": "a@example.com"})
        post(client, SEND, {"email": "b@example.com"})
        otp_a = otp_from_outbox("a@example.com")
        res = post(client, VERIFY, {"email": "b@example.com", "otp": otp_a})
        if otp_a != otp_from_outbox("b@example.com"):
            assert res.status_code == 400

    def test_no_code_requested(self, client):
        assert code(post(client, VERIFY, {"email": EMAIL, "otp": "123456"})) == "INVALID_OTP"

    def test_missing_fields(self, client):
        assert post(client, VERIFY, {"email": EMAIL}).status_code == 400
        assert post(client, VERIFY, {"otp": "123456"}).status_code == 400


# ------------------------------------------------------------------ create account

class TestRegisterAccount:
    def test_full_flow_returns_201_without_secrets(self, client):
        assert verify_email(client).status_code == 200
        res = post(client, REGISTER, payload())
        body = res.json()
        assert res.status_code == 201 and body["success"] is True and body["meta"] == {}
        student = body["data"]["student"]
        assert body["data"]["message"] == "Student account created successfully."
        assert student["first_name"] == "John" and student["middle_name"] == "M" and student["last_name"] == "Doe"
        assert student["email"] == EMAIL and student["phone_number"] == "9876543210" and student["status"] == "pending"
        raw = res.content.decode()
        for forbidden in (PASSWORD, "password", "tokens", "access", "refresh", "otp"):
            assert forbidden not in raw.lower() or forbidden == "password" and "password" not in body["data"]["student"]
        assert set(student) == {"id", "first_name", "middle_name", "last_name", "full_name", "email", "phone_number", "status"}

    def test_stored_in_the_database_with_a_hashed_password(self, client):
        verify_email(client)
        post(client, REGISTER, payload(email=EMAIL))
        user = User.objects.get(email=EMAIL)
        assert user.role == "student" and user.status == "pending"
        assert user.full_name == "John M Doe" and user.first_name == "John" and user.phone_number == "9876543210"
        assert user.password != PASSWORD and user.password.startswith(("argon2", "md5", "pbkdf2")) and user.check_password(PASSWORD)
        assert AuditEvent.objects.filter(action="auth.register").exists()

    def test_requires_a_verified_email(self, client):
        res = post(client, REGISTER, payload())
        assert res.status_code == 403 and code(res) == "EMAIL_NOT_VERIFIED" and not User.objects.filter(email=EMAIL).exists()

    def test_sent_but_unverified_is_not_enough(self, client):
        post(client, SEND, {"email": EMAIL})
        assert code(post(client, REGISTER, payload())) == "EMAIL_NOT_VERIFIED"

    def test_verification_belongs_to_one_email(self, client):
        verify_email(client, "a@example.com")
        assert code(post(client, REGISTER, payload(email="b@example.com"))) == "EMAIL_NOT_VERIFIED"

    def test_verification_is_single_use(self, client):
        verify_email(client)
        assert post(client, REGISTER, payload()).status_code == 201
        assert post(client, REGISTER, payload()).status_code == 403

    def test_verification_expires(self, client):
        verify_email(client)
        cache.clear()
        assert code(post(client, REGISTER, payload())) == "EMAIL_NOT_VERIFIED"

    def test_duplicate_email_is_409_when_it_slips_through(self, client, student):
        cache.set("eduvault:reg_verified:" + student.email, 1, timeout=60)  # a race: verified, then taken
        res = post(client, REGISTER, payload(email=student.email))
        assert res.status_code == 409 and code(res) == "EMAIL_ALREADY_REGISTERED"
        assert "student@example.com" not in json.dumps(res.json()["error"]["details"])

    def test_password_mismatch(self, client):
        verify_email(client)
        res = post(client, REGISTER, payload(confirm_password="Different-Passw0rd!x"))
        assert res.status_code == 400 and "confirm_password" in res.json()["error"]["details"]["fields"]
        assert not User.objects.filter(email=EMAIL).exists()

    def test_weak_password(self, client):
        verify_email(client)
        res = post(client, REGISTER, payload(password="123", confirm_password="123"))
        assert res.status_code == 400 and "password" in res.json()["error"]["details"]["fields"]

    @pytest.mark.parametrize(
        "field,value",
        [("first_name", ""), ("last_name", ""), ("first_name", "J0hn"), ("last_name", "<script>"),
         ("phone_number", "abc"), ("phone_number", "123"), ("phone_number", "1" * 20), ("email", "nope")],
    )
    def test_field_validation(self, client, field, value):
        verify_email(client)
        res = post(client, REGISTER, payload(**{field: value}))
        assert res.status_code == 400 and code(res) == "VALIDATION_ERROR"

    @pytest.mark.parametrize("missing", ["first_name", "last_name", "phone_number", "email", "password", "confirm_password"])
    def test_required_fields(self, client, missing):
        verify_email(client)
        body = payload()
        body.pop(missing)
        assert post(client, REGISTER, body).status_code == 400

    def test_middle_name_is_optional_and_phone_is_normalised(self, client):
        verify_email(client)
        body = payload(phone_number="+91 98765-43210")
        body.pop("middle_name")
        res = post(client, REGISTER, body)
        assert res.status_code == 201
        user = User.objects.get(email=EMAIL)
        assert user.middle_name == "" and user.full_name == "John Doe" and user.phone_number == "+919876543210"

    def test_role_and_status_cannot_be_chosen(self, client):
        verify_email(client)
        res = post(client, REGISTER, payload(role="admin", status="active", is_staff=True))
        user = User.objects.get(email=EMAIL)
        assert res.status_code == 201 and user.role == "student" and user.status == "pending" and not user.is_staff

    def test_email_is_normalised(self, client):
        verify_email(client, "Mixed@Example.COM")
        assert post(client, REGISTER, payload(email="Mixed@Example.COM")).status_code == 201
        assert User.objects.filter(email="mixed@example.com").exists()

    def test_active_immediately_when_approval_is_not_required(self, client, settings):
        settings.REGISTRATION_REQUIRES_APPROVAL = False
        verify_email(client)
        assert post(client, REGISTER, payload()).json()["data"]["student"]["status"] == "active"


# ------------------------------------------------------------------ login

class TestStudentLogin:
    @pytest.fixture
    def registered(self, db):
        c = APIClient()
        register_via_api(c, EMAIL, first_name="John", last_name="Doe")
        return User.objects.get(email=EMAIL)

    @pytest.fixture
    def approved(self, registered):
        registered.status = "active"
        registered.save()
        return registered

    def test_valid_login_returns_jwt_and_profile(self, approved):
        res = login_student(APIClient(), EMAIL)
        data = res.json()["data"]
        assert res.status_code == 200 and data["tokens"]["access"] and data["tokens"]["refresh"]
        assert data["user"]["first_name"] == "John" and data["user"]["status"] == "active"
        assert "password" not in json.dumps(data) and "otp" not in json.dumps(data).lower()

    def test_jwt_authenticates_the_student(self, approved):
        c = APIClient()
        auth_client(c, login_student(c, EMAIL).json()["data"]["tokens"])
        assert c.get("/api/student/profile/").json()["data"]["email"] == EMAIL

    def test_invalid_password_and_unknown_email_look_identical(self, registered):
        wrong = login_student(APIClient(), EMAIL, "Wrong-Passw0rd!x")
        ghost = login_student(APIClient(), "ghost@example.com", "Wrong-Passw0rd!x")
        assert wrong.status_code == ghost.status_code == 401 and wrong.json() == ghost.json()
        assert code(wrong) == "INVALID_CREDENTIALS"

    def test_pending_student_cannot_sign_in(self, registered):
        res = login_student(APIClient(), EMAIL)
        assert res.status_code == 403 and code(res) == "REGISTRATION_PENDING" and "tokens" not in res.content.decode()
        assert "awaiting admin approval" in res.json()["error"]["message"]

    def test_rejected_student_cannot_sign_in(self, registered):
        registered.status, registered.rejection_reason = "rejected", "Incomplete details"
        registered.save()
        res = login_student(APIClient(), EMAIL)
        assert res.status_code == 403 and code(res) == "REGISTRATION_REJECTED" and "tokens" not in res.content.decode()
        assert res.json()["error"]["details"]["reason"] == "Incomplete details"

    def test_a_wrong_password_never_reveals_the_registration_status(self, registered):
        assert code(login_student(APIClient(), EMAIL, "Wrong-Passw0rd!x")) == "INVALID_CREDENTIALS"

    def test_suspended_student_is_refused(self, registered):
        registered.status = "suspended"
        registered.save()
        res = login_student(APIClient(), EMAIL)
        assert res.status_code == 403 and code(res) == "ACCOUNT_SUSPENDED"

    def test_wrong_password_for_a_suspended_account_does_not_reveal_it(self, registered):
        registered.status = "suspended"
        registered.save()
        assert code(login_student(APIClient(), EMAIL, "Wrong-Passw0rd!x")) == "INVALID_CREDENTIALS"

    @pytest.mark.parametrize("body", [{}, {"email": EMAIL}, {"password": PASSWORD}, {"email": "nope", "password": PASSWORD}])
    def test_missing_or_malformed_fields(self, registered, body):
        res = post(APIClient(), "/api/accounts/login/", body)
        assert res.status_code == 400 and code(res) == "VALIDATION_ERROR"

    def test_admin_account_cannot_use_the_student_login(self, admin):
        assert login_student(APIClient(), admin.email).status_code == 401


# ------------------------------------------------------------------ profile / courses belong to the token

class TestStudentOwnData:
    @pytest.fixture
    def two(self, db, admin):
        a = User.objects.create_user("a@example.com", PASSWORD, full_name="Student A", status="active")
        b = User.objects.create_user("b@example.com", PASSWORD, full_name="Student B", status="active")
        course = Course.objects.create(title="Django", slug="django", status="published", access_mode="manual_approval", created_by=admin)
        CourseAccess.objects.create(student=a, course=course, status="active")
        clients = {}
        for key, user in (("a", a), ("b", b)):
            c = APIClient()
            auth_client(c, login_student(c, user.email).json()["data"]["tokens"])
            clients[key] = c
        return a, b, course, clients

    def test_profile_comes_from_the_token_not_the_request(self, two):
        a, b, _, clients = two
        for query in ("", f"?email={b.email}", f"?student={b.id}", f"?student_id={b.id}"):
            assert clients["a"].get("/api/student/profile/" + query).json()["data"]["email"] == a.email
        assert clients["b"].get("/api/student/profile/").json()["data"]["email"] == b.email

    def test_no_url_takes_a_student_name_or_id(self, two):
        a, b, _, clients = two
        for path in (f"/api/student/{b.id}/", "/api/student/student-b/", f"/api/student/profile/{b.id}/", "/api/student/john/"):
            assert clients["a"].get(path).status_code == 404

    def test_courses_show_only_my_access_state(self, two):
        a, b, course, clients = two
        mine = clients["a"].get(f"/api/student/course/?student={b.id}").json()["data"][0]
        theirs = clients["b"].get(f"/api/student/course/?student={a.id}").json()["data"][0]
        assert mine["title"] == "Django" and mine["access"]["state"] == "granted"
        assert theirs["access"]["state"] == "requestable"  # B never sees A's access

    def test_access_records_are_not_shared(self, two):
        a, b, course, clients = two
        record = CourseAccess.objects.get(student=a)
        assert clients["a"].get(f"/api/student/access/{record.id}/").status_code == 200
        assert clients["b"].get(f"/api/student/access/{record.id}/").status_code == 404
        assert str(record.id) not in json.dumps(clients["b"].get("/api/student/access/").json())

    def test_viewer_follows_the_students_own_access(self, two):
        a, b, course, clients = two
        url = f"/api/student/viewing/courses/{course.id}/resources/"
        assert clients["a"].get(url).status_code == 200
        assert clients["b"].get(url).status_code == 403

    def test_unauthenticated_requests_are_refused(self, two):
        for path in ("/api/student/profile/", "/api/student/course/", "/api/student/access/", "/api/student/dashboard/"):
            assert APIClient().get(path).status_code == 401


# ------------------------------------------------------------------ forgot password

class TestForgotPassword:
    NEW = "Brand-New-Passw0rd!x"

    def request(self, client, email, capture):
        with capture(execute=True):
            res = post(client, "/api/accounts/forgot-password/", {"email": email})
        assert res.status_code == 200
        return otp_from_outbox(email)

    def reset_token(self, client, email, capture):
        otp = self.request(client, email, capture)
        return post(client, "/api/accounts/forgot-password/verify/", {"email": email, "otp": otp}).json()["data"]["reset_token"]

    def test_end_to_end(self, client, student, django_capture_on_commit_callbacks):
        with django_capture_on_commit_callbacks(execute=True):
            res = post(client, "/api/accounts/forgot-password/", {"email": student.email})
        otp = otp_from_outbox(student.email)
        assert res.status_code == 200 and otp and otp not in res.content.decode()
        assert mail.outbox[-1].subject == "EduVault Password Reset OTP" and "expire" in mail.outbox[-1].body
        verify = post(client, "/api/accounts/forgot-password/verify/", {"email": student.email, "otp": otp})
        assert verify.status_code == 200 and set(verify.json()["data"]) == {"reset_token"}
        done = post(client, "/api/accounts/reset-password/", {"reset_token": verify.json()["data"]["reset_token"], "new_password": self.NEW, "confirm_password": self.NEW})
        assert done.status_code == 200
        assert login_student(APIClient(), student.email).status_code == 401  # old password
        assert login_student(APIClient(), student.email, self.NEW).status_code == 200
        student.refresh_from_db()
        assert student.password != self.NEW and student.check_password(self.NEW)

    def test_unknown_email_gets_the_same_answer_and_no_email(self, client, student, django_capture_on_commit_callbacks):
        with django_capture_on_commit_callbacks(execute=True):
            known = post(client, "/api/accounts/forgot-password/", {"email": student.email})
            ghost = post(APIClient(), "/api/accounts/forgot-password/", {"email": "ghost@example.com"})
        assert known.json() == ghost.json() and len(mail.outbox) == 1

    def test_invalid_expired_and_reused_codes(self, client, student, django_capture_on_commit_callbacks):
        otp = self.request(client, student.email, django_capture_on_commit_callbacks)
        wrong = "000000" if otp != "000000" else "111111"
        assert code(post(client, "/api/accounts/forgot-password/verify/", {"email": student.email, "otp": wrong})) == "INVALID_OTP"
        assert post(client, "/api/accounts/forgot-password/verify/", {"email": student.email, "otp": otp}).status_code == 200
        assert post(client, "/api/accounts/forgot-password/verify/", {"email": student.email, "otp": otp}).status_code == 400
        otp2 = self.request(client, student.email, django_capture_on_commit_callbacks)
        cache.clear()
        assert post(client, "/api/accounts/forgot-password/verify/", {"email": student.email, "otp": otp2}).status_code == 400

    def test_resend_cooldown_is_uniform(self, client, student, settings, django_capture_on_commit_callbacks):
        settings.OTP_RESEND_COOLDOWN_SECONDS = 60
        with django_capture_on_commit_callbacks(execute=True):
            assert post(client, "/api/accounts/forgot-password/", {"email": student.email}).status_code == 200
            assert post(client, "/api/accounts/forgot-password/", {"email": "ghost@example.com"}).status_code == 200
        again_real = post(client, "/api/accounts/forgot-password/", {"email": student.email})
        again_ghost = post(client, "/api/accounts/forgot-password/", {"email": "ghost@example.com"})
        assert again_real.status_code == again_ghost.status_code == 429 and again_real.json() == again_ghost.json()

    def test_password_mismatch_and_weak_password(self, client, student, django_capture_on_commit_callbacks):
        token = self.reset_token(client, student.email, django_capture_on_commit_callbacks)
        mismatch = post(client, "/api/accounts/reset-password/", {"reset_token": token, "new_password": self.NEW, "confirm_password": "Other-Passw0rd!xx"})
        weak = post(client, "/api/accounts/reset-password/", {"reset_token": token, "new_password": "123", "confirm_password": "123"})
        assert mismatch.status_code == 400 and "confirm_password" in mismatch.json()["error"]["details"]["fields"]
        assert weak.status_code == 400
        assert login_student(APIClient(), student.email).status_code == 200  # nothing changed

    def test_reset_ends_every_session(self, client, student, django_capture_on_commit_callbacks):
        c = APIClient()
        auth_client(c, login_student(c, student.email).json()["data"]["tokens"])
        token = self.reset_token(client, student.email, django_capture_on_commit_callbacks)
        post(client, "/api/accounts/reset-password/", {"reset_token": token, "new_password": self.NEW, "confirm_password": self.NEW})
        assert c.get("/api/accounts/me/").status_code == 401


# ------------------------------------------------------------------ e-mail backends

class TestEmailBackends:
    def test_console_backend_prints_the_message(self, client, settings, capsys):
        settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
        post(client, SEND, {"email": EMAIL})
        out = capsys.readouterr().out
        assert "EduVault Email Verification OTP" in out and f"To: {EMAIL}" in out and "OTP is:" in out

    def test_smtp_backend_is_used_with_the_configured_server(self, client, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
        settings.EMAIL_HOST = "smtp.configured.invalid"
        settings.EMAIL_PORT = 587
        settings.EMAIL_USE_TLS = True
        settings.DEFAULT_FROM_EMAIL = "no-reply@configured.invalid"
        with mock.patch("django.core.mail.backends.smtp.EmailBackend.send_messages", autospec=True, return_value=1) as send:
            res = post(client, SEND, {"email": EMAIL})
        assert res.status_code == 200 and send.call_count == 1
        backend, messages = send.call_args.args
        assert (backend.host, backend.port, backend.use_tls) == ("smtp.configured.invalid", 587, True)
        assert messages[0].from_email == "no-reply@configured.invalid" and messages[0].to == [EMAIL]

    def test_a_failing_mail_server_does_not_break_or_leak(self, client, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
        with mock.patch("django.core.mail.backends.smtp.EmailBackend.send_messages", side_effect=OSError("smtp down: secret-host")):
            res = post(client, SEND, {"email": EMAIL})
        assert res.status_code == 200 and "secret-host" not in res.content.decode()

    def test_smtp_settings_come_from_the_environment_only(self):
        import re
        from pathlib import Path

        source = (Path(__file__).resolve().parent.parent / "config" / "settings.py").read_text(encoding="utf-8")
        for key in ("EMAIL_HOST", "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD"):
            assert re.search(rf'^{key}\s*=\s*env(\.\w+)?\(', source, flags=re.M), key
