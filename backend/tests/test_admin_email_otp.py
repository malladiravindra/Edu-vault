"""API admin sign-in: password -> e-mailed 6-digit code (valid 30 s, single-use) -> JWT."""
import json
import logging
import re
import time
from datetime import timedelta

import pytest
from django.core import mail
from django.core.cache import cache
from rest_framework.test import APIClient

from accounts import services
from accounts.models import User
from audit.models import Actions, AuditEvent

from .conftest import PASSWORD, admin_login_step, admin_otp_from_outbox

pytestmark = pytest.mark.django_db

LOGIN = "/api/admin/login/"
VERIFY = "/api/admin/login/2fa/verify/"
DASHBOARD = "/api/admin/reports/dashboard/"


def verify(client, challenge, otp):
    return client.post(VERIFY, {"challenge_token": challenge, "otp": otp}, format="json")


def wrong_for(otp):
    return "000000" if otp != "000000" else "000001"


def clock_forward(monkeypatch, seconds):
    """Move the server clock (cache expiry, signed-token age and the OTP's own timestamp all follow)."""
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + seconds)


@pytest.fixture
def step1(admin):
    c = APIClient()
    res = admin_login_step(c, admin.email)
    assert res.status_code == 200
    return c, res.json()["data"]


class TestSuccessfulSignIn:
    def test_password_then_emailed_code_issues_tokens_and_opens_the_dashboard(self, admin, step1):
        c, data = step1
        otp = admin_otp_from_outbox(admin.email)
        assert re.fullmatch(r"\d{6}", otp)
        res = verify(c, data["challenge_token"], otp)
        assert res.status_code == 200
        tokens = res.json()["data"]["tokens"]
        assert set(tokens) == {"access", "refresh"}
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        assert c.get(DASHBOARD).status_code == 200
        assert c.get("/api/admin/students/").status_code == 200

    def test_step_one_response_only_says_a_code_was_sent(self, admin, step1):
        _, data = step1
        otp = admin_otp_from_outbox(admin.email)
        assert data["message"] == "A verification code has been sent to your registered email."
        assert data["requires_two_factor"] is True and data["two_factor_method"] == "email_otp" and data["expires_in"] == 30
        assert "tokens" not in data and otp not in json.dumps(data)

    def test_envelope_is_preserved(self, admin):
        res = admin_login_step(APIClient(), admin.email).json()
        assert res["success"] is True and set(res) >= {"success", "data"} and "meta" in res

    def test_sign_in_is_audited_without_the_code(self, admin, step1):
        c, data = step1
        otp = admin_otp_from_outbox(admin.email)
        verify(c, data["challenge_token"], otp)
        actions = list(AuditEvent.objects.values_list("action", flat=True))
        for expected in ("auth.admin_otp.sent", "auth.admin_otp.verified", "auth.login.success"):
            assert expected in actions, expected
        assert otp not in json.dumps(list(AuditEvent.objects.values_list("metadata", flat=True)))


class TestNoTokensBeforeTheCode:
    def test_password_alone_issues_nothing(self, admin, step1):
        c, data = step1
        assert "tokens" not in data and "access" not in json.dumps(data) and "refresh" not in json.dumps(data)
        assert c.get(DASHBOARD).status_code == 401
        assert c.get(DASHBOARD, HTTP_AUTHORIZATION=f"Bearer {data['challenge_token']}").status_code == 401

    def test_no_django_admin_session_is_created(self, admin, step1):
        c, _ = step1
        assert "sessionid" not in c.cookies and c.get("/admin/").status_code == 302

    def test_wrong_password_sends_no_code(self, admin):
        res = admin_login_step(APIClient(), admin.email, "wrong-Password-1")
        assert res.status_code == 401 and res.json()["error"]["code"] == "INVALID_CREDENTIALS"
        assert not mail.outbox and "tokens" not in res.content.decode()

    def test_a_student_never_gets_an_admin_code(self, student):
        res = admin_login_step(APIClient(), student.email)
        assert res.status_code == 401 and not mail.outbox and "challenge_token" not in res.content.decode()

    def test_unknown_wrong_and_student_answers_are_indistinguishable(self, admin, student):
        answers = {
            json.dumps(admin_login_step(APIClient(), email, password).json(), sort_keys=True)
            for email, password in (
                ("nobody@example.com", PASSWORD), (admin.email, "wrong-Password-1"), (student.email, PASSWORD),
            )
        }
        assert len(answers) == 1

    @pytest.mark.parametrize("status", ["pending", "rejected"])
    def test_an_admin_who_is_not_approved_gets_no_code(self, admin, status):
        User.objects.filter(pk=admin.pk).update(status=status)
        res = admin_login_step(APIClient(), admin.email)
        assert res.status_code == 401 and res.json()["error"]["code"] == "INVALID_CREDENTIALS" and not mail.outbox

    def test_a_suspended_admin_gets_no_code_and_no_tokens(self, admin):
        User.objects.filter(pk=admin.pk).update(status="suspended")
        res = admin_login_step(APIClient(), admin.email)
        assert res.status_code == 403 and not mail.outbox and "tokens" not in res.content.decode()

    def test_an_admin_suspended_after_the_password_step_cannot_finish(self, admin, step1):
        c, data = step1
        otp = admin_otp_from_outbox(admin.email)
        User.objects.filter(pk=admin.pk).update(status="suspended")
        res = verify(c, data["challenge_token"], otp)
        assert res.status_code == 401 and "tokens" not in res.content.decode()


class TestTheCode:
    def test_a_wrong_code_is_refused(self, admin, step1):
        c, data = step1
        res = verify(c, data["challenge_token"], wrong_for(admin_otp_from_outbox(admin.email)))
        assert res.status_code == 401 and res.json()["error"]["code"] == "INVALID_TWO_FACTOR_CODE"
        assert "tokens" not in res.content.decode()

    @pytest.mark.parametrize("bad", ["12345", "1234567", "abcdef", "12 456", ""])
    def test_malformed_codes_are_rejected_before_any_check(self, admin, step1, bad):
        c, data = step1
        assert verify(c, data["challenge_token"], bad).status_code == 400

    def test_the_code_is_six_digits_and_random(self, admin, monkeypatch):
        seen = set()
        for _ in range(12):
            mail.outbox.clear()
            admin_login_step(APIClient(), admin.email)
            seen.add(admin_otp_from_outbox(admin.email))
        assert all(re.fullmatch(r"\d{6}", c) for c in seen) and len(seen) > 6

    def test_a_correct_code_works_once(self, admin, step1):
        c, data = step1
        otp = admin_otp_from_outbox(admin.email)
        assert verify(c, data["challenge_token"], otp).status_code == 200
        again = verify(c, data["challenge_token"], otp)
        assert again.status_code == 401 and "tokens" not in again.content.decode()

    def test_a_used_code_does_not_work_on_a_new_attempt(self, admin, step1):
        c, data = step1
        otp = admin_otp_from_outbox(admin.email)
        verify(c, data["challenge_token"], otp)
        second = admin_login_step(APIClient(), admin.email).json()["data"]["challenge_token"]
        new = admin_otp_from_outbox(admin.email)
        if new != otp:
            assert verify(APIClient(), second, otp).status_code == 401

    def test_a_new_code_invalidates_the_previous_one(self, admin, step1):
        c, first = step1
        old = admin_otp_from_outbox(admin.email)
        second = admin_login_step(APIClient(), admin.email).json()["data"]["challenge_token"]
        new = admin_otp_from_outbox(admin.email)
        if new != old:
            assert verify(c, first["challenge_token"], old).status_code == 401  # old challenge + old code
            assert verify(c, second, old).status_code == 401  # new challenge + old code
        assert verify(c, first["challenge_token"], new).status_code == 401  # old challenge + new code
        assert verify(c, second, new).status_code == 200  # only the newest pair works

    def test_the_code_is_bound_to_its_purpose_and_admin(self, admin, step1, db):
        _, data = step1
        otp = admin_otp_from_outbox(admin.email)
        ident = f"{admin.id}:{services._challenge_nonce(data['challenge_token'])}"
        for purpose in ("registration", "admin_login"):
            assert services._check_otp(purpose, ident, otp) is None  # nothing live for any other purpose
        other = User.objects.create_superuser("admin2@example.com", PASSWORD, full_name="Admin Two")
        c2 = APIClient()
        c2_challenge = admin_login_step(c2, other.email).json()["data"]["challenge_token"]
        mail_for_other = admin_otp_from_outbox(other.email)
        if mail_for_other != otp:
            assert verify(c2, c2_challenge, otp).status_code == 401  # another admin's code is useless

    def test_a_student_registration_code_is_not_an_admin_code(self, admin, step1):
        c, data = step1
        services._store_otp("registration", "x@example.com")
        assert services._check_otp("admin_login_2fa", "x@example.com", "000000") is None

    def test_codes_are_stored_hashed(self, admin, step1):
        _, data = step1
        otp = admin_otp_from_outbox(admin.email)
        nonce = services._challenge_nonce(data["challenge_token"])
        code_key, attempts_key = services._otp_keys("admin_login_2fa", f"{admin.id}:{nonce}")
        stored = cache.get(code_key)
        assert stored and otp not in stored and len(stored) == 64


class TestThirtySecondExpiry:
    def test_a_code_is_valid_inside_thirty_seconds(self, admin, step1, monkeypatch):
        c, data = step1
        otp = admin_otp_from_outbox(admin.email)
        clock_forward(monkeypatch, 25)
        assert verify(c, data["challenge_token"], otp).status_code == 200

    def test_an_expired_code_is_refused_even_if_correct(self, admin, step1, monkeypatch):
        c, data = step1
        otp = admin_otp_from_outbox(admin.email)
        clock_forward(monkeypatch, 31)
        res = verify(c, data["challenge_token"], otp)
        assert res.status_code == 401 and res.json()["error"]["code"] == "INVALID_TWO_FACTOR_CODE"
        assert "tokens" not in res.content.decode()
        assert AuditEvent.objects.filter(action="auth.admin_otp.expired").exists()

    def test_expiry_is_judged_by_the_server_not_by_the_cache_alone(self, admin, step1, monkeypatch):
        """Even if the cache still held the code, the issue timestamp stops it from working after 30 s."""
        c, data = step1
        otp = admin_otp_from_outbox(admin.email)
        real = time.time
        monkeypatch.setattr(services.time, "time", lambda: real() + 31)  # only the service's clock moves
        assert verify(c, data["challenge_token"], otp).status_code == 401

    def test_expiry_is_not_extended_by_retries(self, admin, step1, monkeypatch):
        c, data = step1
        otp = admin_otp_from_outbox(admin.email)
        clock_forward(monkeypatch, 20)
        assert verify(c, data["challenge_token"], wrong_for(otp)).status_code == 401  # a retry at 20 s
        clock_forward(monkeypatch, 31)
        assert verify(c, data["challenge_token"], otp).status_code == 401

    def test_after_expiry_the_admin_must_start_again_with_the_password(self, admin, step1, monkeypatch):
        c, data = step1
        old = admin_otp_from_outbox(admin.email)
        clock_forward(monkeypatch, 40)
        assert verify(c, data["challenge_token"], old).status_code == 401
        # there is no "resend" from the old challenge: only a fresh email + password produces a new code
        mail.outbox.clear()
        fresh = admin_login_step(APIClient(), admin.email)
        assert fresh.status_code == 200 and len(mail.outbox) == 1
        new = admin_otp_from_outbox(admin.email)
        assert verify(c, data["challenge_token"], new).status_code == 401  # the old challenge stays dead
        assert verify(APIClient(), fresh.json()["data"]["challenge_token"], new).status_code == 200

    def test_the_expired_code_stays_invalid_after_a_new_login(self, admin, step1, monkeypatch):
        c, data = step1
        old = admin_otp_from_outbox(admin.email)
        clock_forward(monkeypatch, 40)
        fresh = admin_login_step(APIClient(), admin.email).json()["data"]["challenge_token"]
        new = admin_otp_from_outbox(admin.email)
        if new != old:
            assert verify(APIClient(), fresh, old).status_code == 401


class TestRateLimiting:
    def test_requests_for_codes_are_spaced_out(self, admin, settings):
        settings.ADMIN_LOGIN_OTP_RESEND_COOLDOWN_SECONDS = 10
        assert admin_login_step(APIClient(), admin.email).status_code == 200
        res = admin_login_step(APIClient(), admin.email)
        assert res.status_code == 429 and res.json()["error"]["code"] == "OTP_RATE_LIMITED"
        assert len(mail.outbox) == 1 and "challenge_token" not in res.content.decode()
        assert AuditEvent.objects.filter(action="auth.admin_otp.rate_limited").exists()

    def test_the_cooldown_ends(self, admin, settings, monkeypatch):
        settings.ADMIN_LOGIN_OTP_RESEND_COOLDOWN_SECONDS = 10
        admin_login_step(APIClient(), admin.email)
        clock_forward(monkeypatch, 11)
        assert admin_login_step(APIClient(), admin.email).status_code == 200

    def test_an_hourly_cap_applies_per_admin(self, admin, settings):
        settings.ADMIN_LOGIN_OTP_MAX_PER_HOUR = 3
        statuses = [admin_login_step(APIClient(), admin.email).status_code for _ in range(5)]
        assert statuses == [200, 200, 200, 429, 429] and len(mail.outbox) == 3

    def test_password_failures_lock_the_login_without_sending_mail(self, admin, settings):
        for _ in range(settings.LOGIN_MAX_ATTEMPTS):
            admin_login_step(APIClient(), admin.email, "wrong-Password-1")
        res = admin_login_step(APIClient(), admin.email)  # correct password, but locked out
        assert res.status_code == 429 and res.json()["error"]["code"] == "ACCOUNT_LOCKED" and not mail.outbox

    def test_too_many_wrong_codes_burn_the_code_and_require_a_fresh_login(self, admin, step1, settings):
        settings.ADMIN_LOGIN_OTP_MAX_ATTEMPTS = 3
        c, data = step1
        otp = admin_otp_from_outbox(admin.email)
        for _ in range(3):
            assert verify(c, data["challenge_token"], wrong_for(otp)).status_code == 401
        assert verify(c, data["challenge_token"], otp).status_code == 401  # the right code no longer works
        mail.outbox.clear()
        fresh = admin_login_step(APIClient(), admin.email)
        assert fresh.status_code == 200 and mail.outbox
        assert verify(APIClient(), fresh.json()["data"]["challenge_token"], admin_otp_from_outbox(admin.email)).status_code == 200

    def test_repeated_failures_lock_the_account(self, admin, settings):
        settings.LOGIN_MAX_ATTEMPTS = 2
        c = APIClient()
        challenge = admin_login_step(c, admin.email).json()["data"]["challenge_token"]
        otp = admin_otp_from_outbox(admin.email)
        for _ in range(2):
            verify(c, challenge, wrong_for(otp))
        res = verify(c, challenge, otp)
        assert res.status_code == 429 and "tokens" not in res.content.decode()


class TestEmail:
    def test_the_code_goes_to_the_registered_address_only(self, admin, step1):
        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.to == [admin.email] and message.subject == "EduVault Admin Login Verification"

    def test_the_email_has_the_code_and_nothing_sensitive(self, admin, step1):
        body = mail.outbox[0].body
        assert re.search(r"Your verification code is: \d{6}", body) and "expires in 30 seconds" in body
        assert "If you did not request this login, secure your account immediately." in body
        for secret in (PASSWORD, str(admin.id), "eyJ", "refresh", "access", "totp", "backup"):
            assert secret not in body, secret

    def test_the_code_is_not_in_any_response(self, admin):
        c = APIClient()
        res = admin_login_step(c, admin.email)
        otp = admin_otp_from_outbox(admin.email)
        assert otp not in res.content.decode() and otp not in json.dumps(dict(res.headers))

    def test_the_code_is_not_logged(self, admin, caplog):
        with caplog.at_level(logging.DEBUG):
            c = APIClient()
            data = admin_login_step(c, admin.email).json()["data"]
            otp = admin_otp_from_outbox(admin.email)
            verify(c, data["challenge_token"], otp)
            verify(c, data["challenge_token"], otp)  # a refused attempt is logged too
        assert otp not in caplog.text and PASSWORD not in caplog.text

    def test_the_code_is_not_inside_the_tokens(self, admin, step1):
        import jwt as pyjwt

        c, data = step1
        otp = admin_otp_from_outbox(admin.email)
        tokens = verify(c, data["challenge_token"], otp).json()["data"]["tokens"]
        for token in tokens.values():
            claims = pyjwt.decode(token, options={"verify_signature": False})
            assert otp not in json.dumps(claims)


class TestJwtUnchanged:
    def test_jwt_configuration(self, settings):
        jwt = settings.SIMPLE_JWT
        assert jwt["ACCESS_TOKEN_LIFETIME"] == timedelta(minutes=15) and jwt["REFRESH_TOKEN_LIFETIME"] == timedelta(days=7)
        assert jwt["ROTATE_REFRESH_TOKENS"] is True and jwt["BLACKLIST_AFTER_ROTATION"] is True
        assert jwt["ALGORITHM"] == "HS256" and jwt["AUTH_HEADER_TYPES"] == ("Bearer",)
        assert jwt["SIGNING_KEY"] == settings.JWT_SIGNING_KEY != settings.SECRET_KEY

    def test_nothing_but_the_emailed_code_produces_an_admin_token(self, admin, step1):
        c, data = step1
        for body in ({"code": "123456"}, {"backup_code": "abcdef1234"}, {}):
            res = c.post(VERIFY, {"challenge_token": data["challenge_token"], **body}, format="json")
            assert res.status_code == 400 and "tokens" not in res.content.decode()
        for removed in ("setup", "confirm"):  # the TOTP enrolment routes no longer exist
            assert c.post(f"/api/admin/login/2fa/{removed}/", {"challenge_token": data["challenge_token"]}, format="json").status_code == 404

    def test_refresh_rotation_still_works_after_an_otp_sign_in(self, admin, step1):
        c, data = step1
        tokens = verify(c, data["challenge_token"], admin_otp_from_outbox(admin.email)).json()["data"]["tokens"]
        res = APIClient().post("/api/accounts/refresh/", {"refresh": tokens["refresh"]}, format="json")
        assert res.status_code == 200 and res.json()["data"]["tokens"]["refresh"] != tokens["refresh"]
        assert APIClient().post("/api/accounts/refresh/", {"refresh": tokens["refresh"]}, format="json").status_code == 401

    def test_the_django_admin_site_is_independent_of_the_api_code_flow(self, admin):
        from django.test import Client

        from .conftest import django_admin_login

        mail.outbox.clear()
        c = Client()
        res = django_admin_login(c, admin.email)
        assert res.status_code == 302 and res["Location"] == "/admin/"  # password only
        assert not mail.outbox and c.get("/admin/").status_code == 200  # no code was generated or needed
        api = APIClient()
        assert api.get("/api/admin/students/").status_code == 401  # and the session is not an API credential
