import re

import pytest
from django.core import mail
from django.core.cache import cache
from rest_framework.test import APIClient

from accounts.models import User
from accounts import services
from audit.models import AuditEvent

from .conftest import register_via_api, PASSWORD, auth_client, login_student, admin_otp_from_outbox

pytestmark = pytest.mark.django_db


def post(client, url, data=None):
    return client.post(url, data or {}, format="json")


class TestLoginLogoutRefresh:
    def test_login_success_and_me(self, client, student):
        res = login_student(client)
        assert res.status_code == 200
        auth_client(client, res.json()["data"]["tokens"])
        me = client.get("/api/accounts/me/")
        assert me.status_code == 200 and me.json()["data"]["email"] == student.email

    def test_login_wrong_password(self, client, student):
        res = login_student(client, password="wrong-password")
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "INVALID_CREDENTIALS"

    def test_unknown_email_same_error(self, client):
        res = login_student(client, email="ghost@example.com")
        assert res.status_code == 401 and res.json()["error"]["code"] == "INVALID_CREDENTIALS"

    def test_admin_cannot_use_student_login(self, client, admin):
        res = login_student(client, email=admin.email)
        assert res.status_code == 401

    def test_unauthenticated_me(self, client):
        res = client.get("/api/accounts/me/")
        assert res.status_code == 401 and res.json()["success"] is False

    def test_garbage_token(self, client):
        client.credentials(HTTP_AUTHORIZATION="Bearer garbage")
        res = client.get("/api/accounts/me/")
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "TOKEN_NOT_VALID"

    def test_refresh_rotates_and_blacklists(self, client, student):
        tokens = login_student(client).json()["data"]["tokens"]
        first = post(client, "/api/accounts/refresh/", {"refresh": tokens["refresh"]})
        assert first.status_code == 200
        new = first.json()["data"]["tokens"]
        assert new["refresh"] != tokens["refresh"]
        reuse = post(client, "/api/accounts/refresh/", {"refresh": tokens["refresh"]})
        assert reuse.status_code == 401
        assert reuse.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"
        # Replaying a rotated token is treated as theft: the whole device session is ended, new token included.
        assert post(client, "/api/accounts/refresh/", {"refresh": new["refresh"]}).status_code == 401
        assert AuditEvent.objects.filter(action="auth.refresh.reuse_detected").exists()

    def test_logout_blacklists_refresh(self, client, student):
        tokens = login_student(client).json()["data"]["tokens"]
        auth_client(client, tokens)
        assert post(client, "/api/accounts/logout/", {"refresh": tokens["refresh"]}).status_code == 200
        assert post(APIClient(), "/api/accounts/refresh/", {"refresh": tokens["refresh"]}).status_code == 401
        assert client.get("/api/accounts/me/").status_code == 401  # session ended server-side

    def test_inactivity_timeout(self, client, student):
        tokens = login_student(client).json()["data"]["tokens"]
        auth_client(client, tokens)
        cache.clear()  # simulates the inactivity window expiring in Redis
        res = client.get("/api/accounts/me/")
        assert res.status_code == 401 and res.json()["error"]["code"] == "SESSION_EXPIRED"

    def test_lockout_after_repeated_failures(self, client, student, settings):
        for _ in range(settings.LOGIN_MAX_ATTEMPTS):
            login_student(client, password="bad-password")
        res = login_student(client)  # correct password, still locked
        assert res.status_code == 429 and res.json()["error"]["code"] == "ACCOUNT_LOCKED"
        assert AuditEvent.objects.filter(action="auth.login.locked").exists()

    def test_suspended_user_cannot_login(self, client, student):
        student.status = User.Status.SUSPENDED
        student.save()
        res = login_student(client)
        assert res.status_code == 403 and res.json()["error"]["code"] == "ACCOUNT_SUSPENDED"

    def test_suspended_user_token_rejected(self, client, student):
        tokens = login_student(client).json()["data"]["tokens"]
        auth_client(client, tokens)
        student.status = User.Status.SUSPENDED
        student.save()
        res = client.get("/api/accounts/me/")
        assert res.status_code == 401 and res.json()["error"]["code"] == "USER_INACTIVE"
        assert post(APIClient(), "/api/accounts/refresh/", {"refresh": tokens["refresh"]}).status_code == 401


class TestProfileAndPassword:
    def test_update_profile(self, student_client):
        res = student_client.patch("/api/accounts/me/", {"full_name": "Renamed"}, format="json")
        assert res.status_code == 200 and res.json()["data"]["full_name"] == "Renamed"

    def test_profile_cannot_change_role(self, student_client, student):
        student_client.patch("/api/accounts/me/", {"full_name": "X", "role": "admin"}, format="json")
        student.refresh_from_db()
        assert student.role == "student"

    def test_change_password_revokes_old_tokens(self, client, student):
        tokens = login_student(client).json()["data"]["tokens"]
        auth_client(client, tokens)
        new_pw = "An0ther-Str0ng-Pass!"
        res = post(client, "/api/accounts/password-change/", {"current_password": PASSWORD, "new_password": new_pw, "confirm_password": new_pw})
        assert res.status_code == 200
        assert post(APIClient(), "/api/accounts/refresh/", {"refresh": tokens["refresh"]}).status_code == 401
        assert login_student(APIClient(), password=new_pw).status_code == 200

    def test_change_password_wrong_current(self, student_client):
        res = post(student_client, "/api/accounts/password-change/", {"current_password": "nope", "new_password": "An0ther-Str0ng-Pass!", "confirm_password": "An0ther-Str0ng-Pass!"})
        assert res.status_code == 400

    def _request_otp(self, client, email, capture):
        with capture(execute=True):
            res = post(client, "/api/accounts/forgot-password/", {"email": email})
        assert res.status_code == 200
        return re.search(r"OTP is: (\d{6})", mail.outbox[-1].body).group(1)

    def test_password_reset_otp_flow(self, client, student, django_capture_on_commit_callbacks):
        otp = self._request_otp(client, student.email, django_capture_on_commit_callbacks)
        assert "EduVault" in mail.outbox[0].subject and mail.outbox[0].to == [student.email]
        verify = post(client, "/api/accounts/forgot-password/verify/", {"email": student.email, "otp": otp})
        assert verify.status_code == 200
        token = verify.json()["data"]["reset_token"]
        new_pw = "Reset-Str0ng-Pass!!"
        ok = post(client, "/api/accounts/reset-password/", {"reset_token": token, "new_password": new_pw, "confirm_password": new_pw})
        assert ok.status_code == 200
        assert login_student(APIClient(), password=new_pw).status_code == 200
        assert login_student(APIClient()).status_code == 401
        replay = post(client, "/api/accounts/reset-password/", {"reset_token": token, "new_password": "Third-Str0ng-Pass!!", "confirm_password": "Third-Str0ng-Pass!!"})
        assert replay.status_code == 400 and replay.json()["error"]["code"] == "INVALID_RESET_TOKEN"
        actions = set(AuditEvent.objects.values_list("action", flat=True))
        assert {"auth.password.reset_requested", "auth.password.reset_verified", "auth.password.reset_completed"} <= actions

    def test_otp_is_single_use(self, client, student, django_capture_on_commit_callbacks):
        otp = self._request_otp(client, student.email, django_capture_on_commit_callbacks)
        assert post(client, "/api/accounts/forgot-password/verify/", {"email": student.email, "otp": otp}).status_code == 200
        again = post(client, "/api/accounts/forgot-password/verify/", {"email": student.email, "otp": otp})
        assert again.status_code == 400 and again.json()["error"]["code"] == "INVALID_OTP"

    def test_wrong_otp_burns_code_after_max_attempts(self, client, student, settings, django_capture_on_commit_callbacks):
        otp = self._request_otp(client, student.email, django_capture_on_commit_callbacks)
        wrong = "000000" if otp != "000000" else "111111"
        for _ in range(settings.OTP_MAX_ATTEMPTS):
            assert post(client, "/api/accounts/forgot-password/verify/", {"email": student.email, "otp": wrong}).status_code == 400
        res = post(client, "/api/accounts/forgot-password/verify/", {"email": student.email, "otp": otp})
        assert res.status_code == 400  # the correct code no longer works
        assert AuditEvent.objects.filter(action="auth.otp.failed").count() == settings.OTP_MAX_ATTEMPTS

    def test_expired_otp(self, client, student, django_capture_on_commit_callbacks):
        otp = self._request_otp(client, student.email, django_capture_on_commit_callbacks)
        cache.clear()
        assert post(client, "/api/accounts/forgot-password/verify/", {"email": student.email, "otp": otp}).status_code == 400

    def test_otp_for_unknown_email_is_rejected_generically(self, client, db):
        res = post(client, "/api/accounts/forgot-password/verify/", {"email": "ghost@example.com", "otp": "123456"})
        assert res.status_code == 400 and res.json()["error"]["code"] == "INVALID_OTP"

    def test_reset_token_cannot_be_used_after_password_change(self, client, student, django_capture_on_commit_callbacks):
        otp = self._request_otp(client, student.email, django_capture_on_commit_callbacks)
        token = post(client, "/api/accounts/forgot-password/verify/", {"email": student.email, "otp": otp}).json()["data"]["reset_token"]
        student.set_password("Changed-Meanwhile-1!")
        student.save()
        res = post(client, "/api/accounts/reset-password/", {"reset_token": token, "new_password": "Reset-Str0ng-Pass!!", "confirm_password": "Reset-Str0ng-Pass!!"})
        assert res.status_code == 400

    def test_weak_new_password_rejected(self, client, student, django_capture_on_commit_callbacks):
        otp = self._request_otp(client, student.email, django_capture_on_commit_callbacks)
        token = post(client, "/api/accounts/forgot-password/verify/", {"email": student.email, "otp": otp}).json()["data"]["reset_token"]
        res = post(client, "/api/accounts/reset-password/", {"reset_token": token, "new_password": "123", "confirm_password": "123"})
        assert res.status_code == 400 and res.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_password_reset_unknown_email_is_silent(self, client, django_capture_on_commit_callbacks):
        with django_capture_on_commit_callbacks(execute=True):
            res = post(client, "/api/accounts/forgot-password/", {"email": "ghost@example.com"})
        assert res.status_code == 200 and len(mail.outbox) == 0

    def test_suspended_user_gets_no_otp(self, client, student, django_capture_on_commit_callbacks):
        student.status = "suspended"
        student.save()
        with django_capture_on_commit_callbacks(execute=True):
            post(client, "/api/accounts/forgot-password/", {"email": student.email})
        assert len(mail.outbox) == 0

    def test_garbage_reset_token(self, client, student):
        res = post(client, "/api/accounts/reset-password/", {"reset_token": "bad", "new_password": "Reset-Str0ng-Pass!!", "confirm_password": "Reset-Str0ng-Pass!!"})
        assert res.status_code == 400


class TestAdminTwoFactor:
    def _challenge(self, admin):
        return post(APIClient(), "/api/admin/login/", {"email": admin.email, "password": PASSWORD}).json()["data"]

    def test_admin_login_asks_for_the_emailed_code(self, admin):
        data = self._challenge(admin)
        assert data["requires_two_factor"] and data["two_factor_method"] == "email_otp"
        assert "tokens" not in data and "two_factor_setup_required" not in data

    def test_admin_login_wrong_password(self, admin):
        res = post(APIClient(), "/api/admin/login/", {"email": admin.email, "password": "bad"})
        assert res.status_code == 401

    def test_student_cannot_use_admin_login(self, student):
        res = post(APIClient(), "/api/admin/login/", {"email": student.email, "password": PASSWORD})
        assert res.status_code == 401

    def test_verify_with_the_emailed_code(self, admin_client, admin):
        data = self._challenge(admin)
        assert data["two_factor_method"] == "email_otp"
        res = post(APIClient(), "/api/admin/login/2fa/verify/", {"challenge_token": data["challenge_token"], "otp": admin_otp_from_outbox(admin.email)})
        assert res.status_code == 200 and "access" in res.json()["data"]["tokens"]

    def test_verify_wrong_code(self, admin_client, admin):
        data = self._challenge(admin)
        res = post(APIClient(), "/api/admin/login/2fa/verify/", {"challenge_token": data["challenge_token"], "otp": "000000" if admin_otp_from_outbox(admin.email) != "000000" else "000001"})
        assert res.status_code == 401 and res.json()["error"]["code"] == "INVALID_TWO_FACTOR_CODE"

    def test_2fa_rate_limited(self, admin_client, admin, settings):
        data = self._challenge(admin)
        for _ in range(settings.LOGIN_MAX_ATTEMPTS):
            post(APIClient(), "/api/admin/login/2fa/verify/", {"challenge_token": data["challenge_token"], "otp": "000000"})
        res = post(APIClient(), "/api/admin/login/2fa/verify/", {"challenge_token": data["challenge_token"], "otp": admin_otp_from_outbox(admin.email)})
        assert res.status_code == 429

    def test_invalid_challenge(self, db):
        res = post(APIClient(), "/api/admin/login/2fa/verify/", {"challenge_token": "junk", "otp": "123456"})
        assert res.status_code == 401 and res.json()["error"]["code"] == "INVALID_CHALLENGE"

    def test_removed_totp_routes_are_gone(self, admin):
        for name in ("setup", "confirm"):
            assert post(APIClient(), f"/api/admin/login/2fa/{name}/", {}).status_code == 404


class TestUserAdminAPI:
    def test_student_forbidden(self, student_client, other_student):
        assert student_client.get("/api/admin/students/").status_code == 403
        assert student_client.post(f"/api/admin/students/{other_student.id}/suspend/").status_code == 403
        assert student_client.delete(f"/api/admin/students/{other_student.id}/").status_code == 403

    def test_unauthenticated(self, client):
        assert client.get("/api/admin/students/").status_code == 401

    def test_admin_lists_with_pagination_and_case_insensitive_filter(self, admin_client, student):
        res = admin_client.get("/api/admin/students/?role=student&status=ACTIVE")
        body = res.json()
        assert res.status_code == 200 and body["meta"]["count"] == 1 and body["data"][0]["email"] == student.email
        assert admin_client.get("/api/admin/students/?q=nobody").json()["meta"]["count"] == 0

    def test_suspend_revokes_sessions_and_reactivate(self, admin_client, client, student):
        tokens = login_student(client).json()["data"]["tokens"]
        res = admin_client.post(f"/api/admin/students/{student.id}/suspend/")
        assert res.status_code == 200 and res.json()["data"]["status"] == "suspended"
        assert post(APIClient(), "/api/accounts/refresh/", {"refresh": tokens["refresh"]}).status_code == 401
        assert login_student(APIClient()).status_code == 403
        assert admin_client.post(f"/api/admin/students/{student.id}/suspend/").status_code == 409
        again = admin_client.post(f"/api/admin/students/{student.id}/reinstate/")
        assert again.status_code == 200 and again.json()["data"]["status"] == "active"
        assert login_student(APIClient()).status_code == 200
        actions = set(AuditEvent.objects.values_list("action", flat=True))
        assert {"user.suspended", "user.reactivated"} <= actions

    def test_reactivate_requires_suspended(self, admin_client, student):
        assert admin_client.post(f"/api/admin/students/{student.id}/reinstate/").status_code == 409

    def test_admin_cannot_suspend_or_delete_self(self, admin_client, admin):
        res = admin_client.post(f"/api/admin/students/{admin.id}/suspend/")
        assert res.status_code == 400 and res.json()["error"]["code"] == "CANNOT_MODIFY_SELF"
        assert admin_client.delete(f"/api/admin/students/{admin.id}/").status_code == 400

    def test_patch_and_delete_user(self, admin_client, student):
        res = admin_client.patch(f"/api/admin/students/{student.id}/", {"full_name": "Edited"}, format="json")
        assert res.status_code == 200 and res.json()["data"]["full_name"] == "Edited"
        assert admin_client.patch(f"/api/admin/students/{student.id}/", {"full_name": ""}, format="json").status_code == 400
        assert admin_client.delete(f"/api/admin/students/{student.id}/").status_code == 200
        assert admin_client.get(f"/api/admin/students/{student.id}/").status_code == 404
        assert AuditEvent.objects.filter(action="user.deleted").exists()

    def test_patch_cannot_change_role_or_status(self, admin_client, student):
        admin_client.patch(f"/api/admin/students/{student.id}/", {"full_name": "X", "role": "admin", "status": "rejected"}, format="json")
        student.refresh_from_db()
        assert student.role == "student" and student.status == "active"

    def test_unknown_user_404(self, admin_client):
        res = admin_client.get("/api/admin/students/00000000-0000-0000-0000-000000000000/")
        assert res.status_code == 404 and res.json()["error"]["code"] == "NOT_FOUND"


class TestRegistrationApproval:
    def register(self, email="pending@example.com"):
        c = APIClient()
        res = register_via_api(c, email, password=PASSWORD)
        uid = res.json()["data"]["student"]["id"]
        # a pending student cannot sign in, so mint tokens to show what the server does with such a token
        tokens = services.issue_tokens(User.objects.get(pk=uid))
        return c, uid, tokens

    def test_pending_student_can_see_status_but_not_content(self, db):
        c, uid, tokens = self.register()
        auth_client(c, tokens)
        assert c.get("/api/accounts/me/").json()["data"]["status"] == "pending"
        res = c.get("/api/student/course/")
        assert res.status_code == 403 and res.json()["error"]["code"] == "REGISTRATION_PENDING"
        assert c.get("/api/student/access/").status_code == 403

    def test_pending_student_cannot_log_in(self, db):
        self.register()
        res = login_student(APIClient(), "pending@example.com")
        assert res.status_code == 403 and res.json()["error"]["code"] == "REGISTRATION_PENDING"

    def test_admin_approves(self, admin_client, admin):
        c, uid, tokens = self.register()
        res = admin_client.post(f"/api/admin/students/approval-requests/{uid}/approve/")
        body = res.json()["data"]
        assert res.status_code == 200 and body["status"] == "active"
        assert body["reviewed_by"] == str(admin.id) and body["reviewed_at"] is not None
        auth_client(c, tokens)
        assert c.get("/api/student/course/").status_code == 200
        assert AuditEvent.objects.filter(action="user.approved", target_id=uid).exists()

    def test_admin_rejects_with_reason(self, admin_client):
        c, uid, tokens = self.register()
        res = admin_client.post(f"/api/admin/students/approval-requests/{uid}/reject/", {"reason": "Incomplete details"}, format="json")
        assert res.status_code == 200 and res.json()["data"]["status"] == "rejected"
        assert res.json()["data"]["rejection_reason"] == "Incomplete details"
        auth_client(c, tokens)
        me = c.get("/api/accounts/me/").json()["data"]
        assert me["status"] == "rejected" and me["rejection_reason"] == "Incomplete details"
        denied = c.get("/api/student/course/")
        assert denied.status_code == 403 and denied.json()["error"]["code"] == "REGISTRATION_REJECTED"
        assert AuditEvent.objects.filter(action="user.rejected", target_id=uid).exists()

    def test_decision_only_from_pending(self, admin_client):
        _, uid, _ = self.register()
        assert admin_client.post(f"/api/admin/students/approval-requests/{uid}/approve/").status_code == 200
        assert admin_client.post(f"/api/admin/students/approval-requests/{uid}/approve/").status_code == 409
        assert admin_client.post(f"/api/admin/students/approval-requests/{uid}/reject/", {}, format="json").status_code == 409

    def test_list_and_filter_registrations(self, admin_client, student):
        self.register("a@example.com")
        self.register("b@example.com")
        assert admin_client.get("/api/admin/students/approval-requests/?status=PENDING").json()["meta"]["count"] == 2
        assert admin_client.get("/api/admin/students/approval-requests/").json()["meta"]["count"] == 2  # pending by default
        assert admin_client.get("/api/admin/students/approval-requests/?status=all").json()["meta"]["count"] == 3
        uid = admin_client.get("/api/admin/students/approval-requests/?status=pending").json()["data"][0]["id"]
        assert admin_client.get(f"/api/admin/students/approval-requests/{uid}/").status_code == 200

    def test_registrations_exclude_admins(self, admin_client, admin):
        assert admin_client.get(f"/api/admin/students/approval-requests/{admin.id}/").status_code == 404

    def test_student_cannot_review(self, student_client, db):
        _, uid, _ = self.register()
        assert student_client.post(f"/api/admin/students/approval-requests/{uid}/approve/").status_code == 403
        assert student_client.get("/api/admin/students/approval-requests/").status_code == 403

    def test_suspended_pending_flow_unchanged_for_unknown(self, admin_client):
        res = admin_client.post("/api/admin/students/approval-requests/00000000-0000-0000-0000-000000000000/approve/")
        assert res.status_code == 404


class TestSecretsAtRest:
    def test_migration_encrypts_legacy_plaintext(self, db):
        import importlib

        from django.apps import apps as django_apps

        from accounts import crypto

        migration = importlib.import_module("accounts.migrations.0002_encrypt_totp_secret")
        legacy = User.objects.create_superuser("legacy@example.com", PASSWORD, full_name="L", totp_secret="JBSWY3DPEHPK3PXP")
        done = User.objects.create_superuser("done@example.com", PASSWORD, full_name="D", totp_secret=crypto.encrypt("ABCDEFGHIJKLMNOP"))
        migration.encrypt_existing_secrets(django_apps, None)
        legacy.refresh_from_db()
        done.refresh_from_db()
        assert crypto.decrypt(legacy.totp_secret) == "JBSWY3DPEHPK3PXP"
        assert crypto.decrypt(done.totp_secret) == "ABCDEFGHIJKLMNOP"


class TestRateLimitingAndDocs:
    def test_global_throttle_applies_to_unscoped_endpoints(self, student_client, settings):
        from rest_framework.throttling import UserRateThrottle

        assert "rest_framework.throttling.UserRateThrottle" in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]
        assert UserRateThrottle.scope == "user" and "user" in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]

    def test_login_endpoint_is_throttled(self, db, monkeypatch):
        from rest_framework.throttling import ScopedRateThrottle

        monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"login": "2/minute"})
        c = APIClient()
        codes = [login_student(c, "ghost@example.com").status_code for _ in range(4)]
        assert codes[:2] == [401, 401] and 429 in codes
        assert login_student(c, "ghost@example.com").json()["error"]["code"] == "RATE_LIMITED"
