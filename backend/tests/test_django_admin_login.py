"""Django admin site (/admin/): e-mail + password and a normal Django session. Admin API (/api/admin/): password + code + JWT.

The two surfaces are independent: no OTP, TOTP, backup code, challenge token or JWT is involved in /admin/, and a Django
session is never an API credential. The AdminUser / StudentUser sections (one User table) are covered here as well.
"""
import re

import pytest
from django.contrib import admin
from django.core import mail
from django.db import connection
from django.test import Client
from rest_framework.test import APIClient

from accounts.models import AdminUser, StudentUser, User
from audit.models import AuditEvent

from .conftest import PASSWORD, admin_otp_from_outbox, django_admin_login

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_client(admin):
    c = Client()
    res = django_admin_login(c, admin.email)
    assert res.status_code == 302 and res["Location"] == "/admin/"
    return c


def authenticated(client):
    return "_auth_user_id" in client.session


class TestDjangoAdminLogin:
    """The behaviour from the screenshot: e-mail + password must open /admin/, with no second factor of any kind."""

    def test_email_and_password_open_the_admin(self, admin):
        c = Client()
        res = django_admin_login(c, admin.email)
        assert res.status_code == 302 and res["Location"] == "/admin/"
        assert authenticated(c) and c.get("/admin/").status_code == 200

    def test_no_second_factor_page_or_error_exists(self, admin):
        c = Client()
        res = c.post("/admin/login/", {"username": admin.email, "password": PASSWORD}, follow=True)
        body = res.content.decode().lower()
        assert res.redirect_chain[-1][0] == "/admin/" and res.status_code == 200
        for word in ("two-factor", "verification code", "authenticator", "backup code", "otp"):
            assert word not in body, word
        assert "/admin/login/2fa/" not in res.redirect_chain[-1][0]

    def test_it_needs_no_otp_totp_backup_code_or_jwt(self, admin):
        assert not admin.two_factor_enabled and not admin.totp_secret  # never enrolled anything
        mail.outbox.clear()
        c = Client()
        res = django_admin_login(c, admin.email)
        assert res.status_code == 302 and res["Location"] == "/admin/"
        assert not mail.outbox  # no code was generated or e-mailed
        assert "Authorization" not in c.defaults and not any("jwt" in k.lower() for k in c.cookies)

    def test_the_django_admin_never_calls_the_api_flow(self, admin):
        from accounts import services

        c = Client()
        before = AuditEvent.objects.filter(action__startswith="auth.admin_otp").count()
        django_admin_login(c, admin.email)
        assert AuditEvent.objects.filter(action__startswith="auth.admin_otp").count() == before
        assert not hasattr(services, "two_factor_setup") and not hasattr(services, "verify_second_factor")

    def test_next_is_honoured_only_for_local_urls(self, admin):
        assert django_admin_login(Client(), admin.email, next_url="/admin/accounts/studentuser/")["Location"] == "/admin/accounts/studentuser/"
        assert django_admin_login(Client(), admin.email, next_url="https://evil.example/x")["Location"] == "/admin/"

    def test_anonymous_visitors_are_sent_to_the_login(self):
        for path in ("/admin/", "/admin/accounts/adminuser/", "/admin/accounts/users/students/"):
            res = Client().get(path)
            assert res.status_code == 302 and res["Location"].startswith("/admin/login/"), path

    def test_wrong_password_is_refused(self, admin):
        c = Client()
        res = django_admin_login(c, admin.email, password="wrong-Password-1")
        assert res.status_code == 200 and b"Please enter the correct" in res.content and not authenticated(c)

    def test_unknown_account_looks_like_a_wrong_password(self, admin):
        a = django_admin_login(Client(), "nobody@example.com").content.decode()
        b = django_admin_login(Client(), admin.email, password="wrong-Password-1").content.decode()
        strip = lambda html: re.sub(r'csrfmiddlewaretoken" value="[^"]+"|value="[^"]*"', "", html)
        assert strip(a) == strip(b)

    def test_the_shared_login_lockout_applies(self, admin, settings):
        for _ in range(settings.LOGIN_MAX_ATTEMPTS):
            django_admin_login(Client(), admin.email, password="wrong-Password-1")
        res = django_admin_login(Client(), admin.email)  # right password, but locked out
        assert res.status_code == 200 and b"Too many failed attempts" in res.content

    def test_sign_in_is_audited_and_failures_too(self, admin):
        django_admin_login(Client(), admin.email, password="wrong-Password-1")
        django_admin_login(Client(), admin.email)
        assert AuditEvent.objects.filter(action="auth.login.failed").exists()
        event = AuditEvent.objects.filter(action="auth.login.success").latest("created_at")
        assert event.metadata.get("via") == "django_admin"
        assert PASSWORD not in str(list(AuditEvent.objects.values_list("metadata", flat=True)))

    def test_a_valid_session_opens_protected_pages(self, staff_client, admin, student):
        for path in ("/admin/", "/admin/accounts/adminuser/", "/admin/accounts/studentuser/", "/admin/audit/auditevent/"):
            assert staff_client.get(path).status_code == 200, path

    def test_logging_out_ends_access(self, staff_client):
        staff_client.post("/admin/logout/")
        assert staff_client.get("/admin/")["Location"].startswith("/admin/login/")

    def test_the_session_key_changes_on_login(self, admin):
        c = Client()
        c.get("/admin/login/")
        before = c.cookies["sessionid"].value if "sessionid" in c.cookies else None
        django_admin_login(c, admin.email)
        assert c.cookies["sessionid"].value != before  # session fixation protection

    def test_session_cookie_settings(self, settings):
        assert settings.SESSION_COOKIE_AGE == 8 * 60 * 60 or settings.SESSION_COOKIE_AGE > 0
        assert settings.SESSION_COOKIE_HTTPONLY is True and settings.CSRF_COOKIE_SECURE == (not settings.DEBUG)
        assert settings.SESSION_COOKIE_SECURE == (not settings.DEBUG)


class TestWhoMayUseTheDjangoAdmin:
    def test_a_student_is_rejected(self, student):
        c = Client()
        res = django_admin_login(c, student.email)
        assert res.status_code == 200 and not authenticated(c)

    def test_a_student_flagged_is_staff_is_still_rejected(self, student):
        User.objects.filter(pk=student.pk).update(is_staff=True)
        c = Client()
        assert django_admin_login(c, student.email).status_code == 200 and not authenticated(c)
        c.force_login(student)  # even an existing session cannot open the site
        assert c.get("/admin/")["Location"].startswith("/admin/login/")

    def test_an_admin_without_the_staff_flag_is_rejected(self, db):
        user = User.objects.create_user("api-admin@example.com", PASSWORD, full_name="API Admin", role="admin")
        c = Client()
        assert django_admin_login(c, user.email).status_code == 200 and not authenticated(c)

    @pytest.mark.parametrize("status", ["suspended", "rejected", "pending"])
    def test_non_active_admins_are_rejected(self, admin, status):
        User.objects.filter(pk=admin.pk).update(status=status)
        c = Client()
        assert django_admin_login(c, admin.email).status_code == 200 and not authenticated(c)

    @pytest.mark.parametrize("status", ["suspended", "rejected", "pending"])
    def test_an_open_session_ends_when_the_admin_stops_being_active(self, staff_client, admin, status):
        assert staff_client.get("/admin/").status_code == 200
        User.objects.filter(pk=admin.pk).update(status=status)
        assert staff_client.get("/admin/")["Location"].startswith("/admin/login/")

    def test_an_open_session_ends_when_the_role_or_staff_flag_goes(self, staff_client, admin):
        User.objects.filter(pk=admin.pk).update(is_staff=False)
        assert staff_client.get("/admin/")["Location"].startswith("/admin/login/")
        User.objects.filter(pk=admin.pk).update(is_staff=True, role="student")
        assert staff_client.get("/admin/")["Location"].startswith("/admin/login/")


class TestHostGuardAndSeparation:
    def test_the_host_guard_still_covers_every_admin_page(self, settings, staff_client):
        settings.ALLOWED_HOSTS = ["testserver", "abc.trycloudflare.com"]
        for path in ("/admin/", "/admin/login/", "/admin/accounts/users/admin/", "/admin/accounts/adminuser/"):
            assert staff_client.get(path, HTTP_HOST="abc.trycloudflare.com").status_code == 404, path
            assert Client().post(path, HTTP_HOST="abc.trycloudflare.com").status_code == 404, path

    def test_a_django_session_is_not_an_api_credential(self, staff_client):
        assert staff_client.get("/api/admin/students/").status_code == 401
        assert staff_client.get("/api/admin/reports/dashboard/").status_code == 401

    def test_an_api_jwt_does_not_open_the_django_admin(self, admin_client):
        token = admin_client._credentials["HTTP_AUTHORIZATION"]
        c = Client()
        assert c.get("/admin/", HTTP_AUTHORIZATION=token)["Location"].startswith("/admin/login/")

    def test_no_totp_or_otp_routes_exist_under_the_django_admin(self, staff_client):
        for path in ("/admin/login/2fa/", "/admin/login/otp/"):
            assert staff_client.get(path).status_code == 404, path


class TestApiAdminLoginStillNeedsTheEmailedCode:
    def test_password_step_gives_no_token_and_sends_a_code(self, admin):
        c = APIClient()
        data = c.post("/api/admin/login/", {"email": admin.email, "password": PASSWORD}, format="json").json()["data"]
        assert data["requires_two_factor"] and data["two_factor_method"] == "email_otp" and "tokens" not in data
        assert c.get("/api/admin/students/").status_code == 401
        assert admin_otp_from_outbox(admin.email)

    def test_code_then_jwt_then_protected_api(self, admin):
        c = APIClient()
        data = c.post("/api/admin/login/", {"email": admin.email, "password": PASSWORD}, format="json").json()["data"]
        res = c.post(
            "/api/admin/login/2fa/verify/",
            {"challenge_token": data["challenge_token"], "otp": admin_otp_from_outbox(admin.email)}, format="json",
        )
        tokens = res.json()["data"]["tokens"]
        assert res.status_code == 200 and {"access", "refresh"} <= set(tokens)
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        assert c.get("/api/admin/students/").status_code == 200


class TestUsersAreOneTableWithTwoSections:
    def test_proxies_share_the_user_table_and_create_none(self):
        assert AdminUser._meta.proxy and StudentUser._meta.proxy
        assert AdminUser._meta.db_table == StudentUser._meta.db_table == User._meta.db_table == "accounts_user"
        tables = connection.introspection.table_names()
        assert "accounts_adminuser" not in tables and "accounts_studentuser" not in tables

    def test_each_proxy_contains_only_its_role(self, admin, student, other_student):
        assert set(AdminUser.objects.values_list("email", flat=True)) == {admin.email}
        assert set(StudentUser.objects.values_list("email", flat=True)) == {student.email, other_student.email}
        assert AdminUser.objects.count() + StudentUser.objects.count() == User.objects.count()

    def test_sections_list_only_their_role(self, staff_client, admin, student):
        a = staff_client.get("/admin/accounts/adminuser/").content.decode()
        s = staff_client.get("/admin/accounts/studentuser/").content.decode()
        assert f"/adminuser/{admin.pk}/change/" in a and str(student.pk) not in a
        assert f"/studentuser/{student.pk}/change/" in s and str(admin.pk) not in s

    def test_a_user_cannot_be_opened_in_the_wrong_section(self, staff_client, admin, student):
        assert staff_client.get(f"/admin/accounts/adminuser/{student.pk}/change/").status_code == 302
        assert staff_client.get(f"/admin/accounts/studentuser/{admin.pk}/change/").status_code == 302
        assert staff_client.get(f"/admin/accounts/studentuser/{student.pk}/change/").status_code == 200

    def test_the_old_combined_admin_is_gone(self, staff_client, student):
        assert User not in admin.site._registry
        for path in ("/admin/accounts/user/", f"/admin/accounts/user/{student.pk}/change/", "/admin/accounts/user/add/"):
            assert staff_client.get(path).status_code == 404, path

    def test_the_required_paths_redirect(self, staff_client):
        res = staff_client.get("/admin/accounts/users/admin/")
        assert res.status_code == 302 and res["Location"] == "/admin/accounts/adminuser/"
        res = staff_client.get("/admin/accounts/users/students/?status__exact=active")
        assert res["Location"] == "/admin/accounts/studentuser/?status__exact=active"

    def test_edits_stay_limited_and_secrets_hidden(self, staff_client, student, admin):
        staff_client.post(
            f"/admin/accounts/studentuser/{student.pk}/change/",
            {"full_name": "Renamed", "first_name": "R", "middle_name": "", "last_name": "N", "phone_number": "",
             "email_notifications": "on", "role": "admin", "status": "suspended", "is_staff": "on", "is_superuser": "on"},
        )
        student.refresh_from_db()
        assert (student.full_name, student.role, student.status, student.is_staff, student.is_superuser) == (
            "Renamed", "student", "active", False, False,
        )
        page = staff_client.get(f"/admin/accounts/adminuser/{admin.pk}/change/").content.decode()
        for hidden in ("totp_secret", 'name="password"', admin.password[:20]):
            assert hidden not in page
        for model, obj in (("adminuser", admin), ("studentuser", student)):
            assert staff_client.get(f"/admin/accounts/{model}/add/").status_code == 403
            assert staff_client.get(f"/admin/accounts/{model}/{obj.pk}/delete/").status_code == 403
