"""JWT security: signature/algorithm/type/expiry, claims, rotation races, logout, status, 2FA, key policy."""
import base64
import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import jwt
import pytest
from django.conf import settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts import services
from audit.models import AuditEvent

from .conftest import PASSWORD, auth_client
from .test_phase3_security import ADMIN_LOGIN, LOGIN, code, new_client, post, sign_in

pytestmark = pytest.mark.django_db

ME = "/api/accounts/me/"
REFRESH = "/api/accounts/refresh/"
BACKEND = Path(__file__).resolve().parent.parent


def get_me(token=None, header=None):
    c = APIClient()
    if header is not None:
        return c.get(ME, HTTP_AUTHORIZATION=header)
    return c.get(ME, HTTP_AUTHORIZATION=f"Bearer {token}") if token is not None else c.get(ME)


def forged(claims, key=None, alg="HS256"):
    return jwt.encode(claims, key or settings.SIMPLE_JWT["SIGNING_KEY"], algorithm=alg)


def b64(data):
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


# ------------------------------------------------------------------ access token validation

class TestAccessTokenValidation:
    def test_valid_token_is_accepted(self, student):
        _, tokens = sign_in()
        assert get_me(tokens["access"]).status_code == 200

    def test_access_lifetime_is_short(self):
        assert settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] <= timedelta(minutes=15)
        assert settings.SIMPLE_JWT["ALGORITHM"] == "HS256"

    def test_expired_token_is_rejected(self, student):
        _, tokens = sign_in()
        token = AccessToken(tokens["access"])
        token.set_exp(lifetime=-timedelta(seconds=5))
        assert get_me(str(token)).status_code == 401

    def test_tampered_payload_is_rejected(self, student):
        _, tokens = sign_in()
        header, payload, signature = tokens["access"].split(".")
        claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
        claims["user_id"] = "00000000-0000-0000-0000-000000000000"
        assert get_me(f"{header}.{b64(claims)}.{signature}").status_code == 401

    def test_wrong_signing_key_is_rejected(self, student):
        _, tokens = sign_in()
        claims = AccessToken(tokens["access"]).payload
        assert get_me(forged(claims, key="a-completely-different-signing-key-0123456789")).status_code == 401

    def test_alg_none_is_rejected(self, student):
        _, tokens = sign_in()
        claims = AccessToken(tokens["access"]).payload
        unsigned = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(claims)}."
        assert get_me(unsigned).status_code == 401

    def test_unexpected_algorithm_is_rejected(self, student):
        _, tokens = sign_in()
        claims = AccessToken(tokens["access"]).payload
        assert get_me(forged(claims, alg="HS512")).status_code == 401

    @pytest.mark.parametrize("token", ["", "abc", "a.b.c", "....", "not a jwt at all"])
    def test_malformed_tokens_are_rejected(self, token, student):
        assert get_me(header=f"Bearer {token}").status_code == 401

    @pytest.mark.parametrize("header", ["Bearer", "Bearer ", "Basic abc", "Token abc", "bearer"])
    def test_bad_authorization_headers_are_rejected(self, header, student):
        assert get_me(header=header).status_code == 401

    def test_missing_token_is_rejected(self, student):
        assert get_me().status_code == 401

    def test_refresh_token_is_not_an_access_token(self, student):
        _, tokens = sign_in()
        assert get_me(tokens["refresh"]).status_code == 401

    def test_access_token_is_not_a_refresh_token(self, student):
        _, tokens = sign_in()
        assert post(APIClient(), REFRESH, {"refresh": tokens["access"]}).status_code == 401

    def test_errors_use_the_envelope_and_hide_jwt_internals(self, student):
        res = get_me("a.b.c")
        body = res.json()
        assert body["success"] is False and set(body["error"]) == {"code", "message", "details"}
        text = res.content.decode().lower()
        for leak in ("signature", "token_class", "jwt", "hs256", "expired", "traceback"):
            assert leak not in text


# ------------------------------------------------------------------ claims

class TestJwtPayload:
    def test_claims_are_minimal_and_free_of_secrets(self, student):
        _, tokens = sign_in()
        allowed = {"token_type", "exp", "iat", "jti", "user_id", "sid", "ep"}
        for raw in (tokens["access"], tokens["refresh"]):
            claims = jwt.decode(raw, options={"verify_signature": False})
            assert set(claims) <= allowed, set(claims) - allowed
            assert "role" not in claims and "email" not in claims
        blob = (tokens["access"] + tokens["refresh"]).lower()
        assert PASSWORD.lower() not in blob

    def test_admin_tokens_carry_no_2fa_material(self, admin):
        claims = jwt.decode(services.issue_tokens(admin)["access"], options={"verify_signature": False})
        for forbidden in ("totp", "secret", "backup", "otp", "password"):
            assert not any(forbidden in key.lower() for key in claims)


# ------------------------------------------------------------------ refresh rotation / reuse / races

class TestRefreshRotation:
    def test_rotation_issues_a_new_token_and_kills_the_old_one(self, student):
        _, a = sign_in()
        res = post(APIClient(), REFRESH, {"refresh": a["refresh"]})
        b = res.json()["data"]["tokens"]
        assert res.status_code == 200 and b["refresh"] != a["refresh"]
        assert post(APIClient(), REFRESH, {"refresh": a["refresh"]}).status_code == 401

    def test_concurrent_rotation_cannot_fork_a_session(self, student, monkeypatch):
        """Two requests pass the blacklist check with the same token; only one may win."""
        _, a = sign_in()
        real = services.touch_session

        def racing_touch(user_id, sid):  # runs after the token was verified, before it is blacklisted
            token = RefreshToken(a["refresh"])
            token.blacklist()  # the competing request wins the race
            return real(user_id, sid)

        monkeypatch.setattr(services, "touch_session", racing_touch)
        res = post(APIClient(), REFRESH, {"refresh": a["refresh"]})
        assert res.status_code == 401 and code(res) == "INVALID_REFRESH_TOKEN"
        monkeypatch.undo()
        assert AuditEvent.objects.filter(action="auth.refresh.reuse_detected").exists()

    def test_refresh_rejects_tokens_of_a_suspended_user(self, admin_client, student):
        _, tokens = sign_in()
        admin_client.post(f"/api/admin/students/{student.id}/suspend/")
        assert post(APIClient(), REFRESH, {"refresh": tokens["refresh"]}).status_code == 401


# ------------------------------------------------------------------ logout

class TestLogout:
    def test_logout_revokes_refresh_and_access(self, student):
        c, tokens = sign_in()
        assert post(c, "/api/accounts/logout/", {"refresh": tokens["refresh"]}).status_code == 200
        assert post(APIClient(), REFRESH, {"refresh": tokens["refresh"]}).status_code == 401
        assert get_me(tokens["access"]).status_code == 401

    def test_logout_with_a_bad_refresh_token_still_ends_the_access_session(self, student):
        c, tokens = sign_in()
        assert post(c, "/api/accounts/logout/", {"refresh": "garbage"}).status_code == 200
        assert get_me(tokens["access"]).status_code == 401

    def test_logout_cannot_revoke_another_users_refresh_token(self, student, other_student):
        c, _ = sign_in()
        _, theirs = sign_in(email=other_student.email)
        post(c, "/api/accounts/logout/", {"refresh": theirs["refresh"]})
        assert post(APIClient(), REFRESH, {"refresh": theirs["refresh"]}).status_code == 200

    def test_logout_requires_authentication(self, student):
        _, tokens = sign_in()
        assert post(APIClient(), "/api/accounts/logout/", {"refresh": tokens["refresh"]}).status_code == 401
        assert post(APIClient(), REFRESH, {"refresh": tokens["refresh"]}).status_code == 200


# ------------------------------------------------------------------ user status is authoritative

class TestDatabaseStatusWins:
    def test_suspending_a_user_kills_existing_access_tokens(self, admin_client, student):
        c, tokens = sign_in()
        assert c.get(ME).status_code == 200
        admin_client.post(f"/api/admin/students/{student.id}/suspend/")
        assert get_me(tokens["access"]).status_code == 401

    def test_status_change_without_revocation_is_still_enforced(self, student):
        """Even if only the row changes (e.g. via Django admin) a valid JWT must not keep working."""
        _, tokens = sign_in()
        student.status = "suspended"
        student.save()
        assert get_me(tokens["access"]).status_code == 401
        assert post(APIClient(), REFRESH, {"refresh": tokens["refresh"]}).status_code == 401

    def test_deleted_user_token_is_rejected(self, student):
        _, tokens = sign_in()
        student.delete()
        assert get_me(tokens["access"]).status_code == 401

    def test_demotion_is_not_hidden_by_the_token(self, admin_client, admin):
        tokens = services.issue_tokens(admin)
        c = new_client(tokens)
        assert c.get("/api/admin/students/").status_code == 200
        admin.role = "student"
        admin.save()
        assert c.get("/api/admin/students/").status_code == 403


# ------------------------------------------------------------------ roles and admin 2FA

class TestRolesAndTwoFactor:
    def test_student_token_cannot_use_admin_apis(self, student_client):
        assert student_client.get("/api/admin/students/").status_code == 403
        assert student_client.get("/api/admin/audit-logs/").status_code == 403

    def test_anonymous_cannot_use_protected_apis(self, db):
        for url in ("/api/admin/students/", "/api/student/dashboard/", ME):
            assert APIClient().get(url).status_code == 401

    def test_admin_password_alone_yields_no_tokens(self, admin):
        res = post(APIClient(), ADMIN_LOGIN, {"email": admin.email, "password": PASSWORD})
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["requires_two_factor"] is True and "tokens" not in data and "access" not in json.dumps(data)

    def test_challenge_token_is_not_a_bearer_token(self, admin):
        challenge = post(APIClient(), ADMIN_LOGIN, {"email": admin.email, "password": PASSWORD}).json()["data"]["challenge_token"]
        assert get_me(challenge).status_code == 401
        assert APIClient().get("/api/admin/students/", HTTP_AUTHORIZATION=f"Bearer {challenge}").status_code == 401

    def test_admin_cannot_get_tokens_from_the_student_endpoint(self, admin):
        res = post(APIClient(), LOGIN, {"email": admin.email, "password": PASSWORD})
        assert res.status_code == 401 and "tokens" not in res.content.decode()


# ------------------------------------------------------------------ password changes revoke sessions

class TestCredentialChange:
    def test_password_change_revokes_old_refresh_and_access(self, student):
        c, old = sign_in()
        res = post(c, "/api/accounts/password-change/", {"current_password": PASSWORD, "new_password": "Brand-New-Pass-77!"})
        assert res.status_code == 200
        assert get_me(old["access"]).status_code == 401
        assert post(APIClient(), REFRESH, {"refresh": old["refresh"]}).status_code == 401
        assert get_me(res.json()["data"]["tokens"]["access"]).status_code == 200


# ------------------------------------------------------------------ audit hygiene

class TestAuditHasNoRawTokens:
    def test_reuse_and_logout_events_contain_no_tokens(self, student):
        c, a = sign_in()
        post(APIClient(), REFRESH, {"refresh": a["refresh"]})
        post(APIClient(), REFRESH, {"refresh": a["refresh"]})
        post(c, "/api/accounts/logout/", {"refresh": a["refresh"]})
        dump = json.dumps(list(AuditEvent.objects.values()), default=str)
        for raw in (a["refresh"], a["access"]):
            assert raw not in dump
        assert "eyJ" not in dump  # no JWT header of any kind


# ------------------------------------------------------------------ signing key policy

class TestSigningKeyPolicy:
    def run(self, **env):
        base = {
            "SECRET_KEY": "s" * 50, "JWT_SIGNING_KEY": "j" * 50, "FIELD_ENCRYPTION_KEY": "x" * 44,
            "REDIS_URL": "locmemcache://", "DATABASE_URL": "sqlite:///:memory:", "DEBUG": "False",
        }
        base.update(env)
        import os
        proc = subprocess.run(
            [sys.executable, "-c", "import os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; import config.settings"],
            cwd=BACKEND, env={**os.environ, **base}, capture_output=True, text=True,
        )
        return proc

    def test_strong_key_is_accepted(self):
        assert self.run().returncode == 0

    def test_short_key_is_refused_in_production(self):
        proc = self.run(JWT_SIGNING_KEY="short")
        assert proc.returncode != 0 and "JWT_SIGNING_KEY" in proc.stderr

    def test_key_equal_to_secret_key_is_refused_in_production(self):
        assert self.run(JWT_SIGNING_KEY="s" * 50).returncode != 0

    def test_there_is_no_fallback_signing_key(self):
        source = (BACKEND / "config" / "settings.py").read_text()
        assert 'env("JWT_SIGNING_KEY")' in source and 'JWT_SIGNING_KEY", default' not in source
