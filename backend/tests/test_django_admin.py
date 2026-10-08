"""Django's built-in admin site at /admin/ is separate from the EduVault admin API at /api/admin/."""
import pytest
from django.contrib import admin
from django.test import Client
from django.urls import resolve, reverse
from rest_framework.test import APIClient

from accounts.models import User
from audit.models import AuditEvent
from courses.models import Course
from payments.models import Payment, StripeEvent

from .conftest import PASSWORD, django_admin_login, login_student

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff(admin):
    """A superuser with is_staff=True, created like `createsuperuser` (no TOTP enrolment needed)."""
    return admin


@pytest.fixture
def staff_client(staff):
    """A client signed in to the Django admin through the real password + e-mailed code flow."""
    c = Client()
    res = django_admin_login(c, staff.email)
    assert res.status_code == 302 and res["Location"] == "/admin/"
    return c


class TestRouting:
    def test_root_is_still_404(self, client):
        assert client.get("/").status_code == 404

    def test_admin_is_djangos_admin_site(self):
        assert reverse("admin:index") == "/admin/"
        assert resolve("/admin/").func.__module__.startswith("django.contrib.admin")
        assert resolve("/admin/login/").url_name == "login"

    def test_api_admin_is_still_the_eduvault_admin_api(self):
        view = resolve("/api/admin/students/").func.view_class
        assert view.__module__ == "accounts.views" and view.__name__ == "AdminUserListView"
        assert resolve("/api/admin/login/").func.view_class.__name__ == "AdminLoginView"
        assert resolve("/api/admin/course/").func.view_class.__name__ == "AdminCourseListCreateView"

    def test_anonymous_gets_the_django_login_page(self, client):
        res = client.get("/admin/")
        assert res.status_code == 302 and res["Location"].startswith("/admin/login/")
        login = client.get("/admin/login/")
        assert login.status_code == 200 and b"csrfmiddlewaretoken" in login.content and b"Log in" in login.content

    def test_api_admin_without_a_token_is_still_401_json(self, client):
        res = client.get("/api/admin/students/")
        assert res.status_code == 401 and res.json()["error"]["code"] == "NOT_AUTHENTICATED"


class TestLoginAndAccess:
    def test_superuser_signs_in_with_password_and_emailed_code(self, staff):
        c = Client()
        assert django_admin_login(c, staff.email)["Location"] == "/admin/"
        assert c.get("/admin/").status_code == 200

    def test_wrong_password_is_refused(self, client, staff):
        res = client.post("/admin/login/", {"username": staff.email, "password": "wrong-Password-1"})
        assert res.status_code == 200 and b"Please enter the correct" in res.content

    def test_a_student_cannot_use_the_admin_site(self, client, student):
        res = client.post("/admin/login/", {"username": student.email, "password": PASSWORD})
        assert res.status_code == 200  # form re-shown: not staff
        c = APIClient()
        c.force_login(student)
        assert c.get("/admin/").status_code == 302

    def test_an_admin_role_without_staff_flag_is_refused(self, db):
        user = User.objects.create_user("api-admin@example.com", PASSWORD, full_name="API Admin", role="admin")
        c = APIClient()
        c.force_login(user)
        assert user.role == "admin" and not user.is_staff
        assert c.get("/admin/").status_code == 302

    def test_a_suspended_superuser_is_refused(self, client, staff):
        staff.status = "suspended"
        staff.save()
        res = client.post("/admin/login/", {"username": staff.email, "password": PASSWORD})
        assert res.status_code == 200 and b"Please enter the correct" in res.content

    def test_the_index_lists_the_project_models(self, staff_client):
        page = staff_client.get("/admin/").content.decode()
        for label in ("Admin users", "Student users", "Courses", "Course accesss", "Resources", "Payments", "Stripe events", "Audit events", "Platform settingss"):
            assert label in page or label.rstrip("s") in page, label
        assert "Outstanding tokens" not in page and "Blacklisted tokens" not in page  # refresh tokens are never shown


class TestHostGuard:
    """The admin site is password-only, so it is only served on local hostnames."""

    def test_public_hostnames_get_404(self, settings, staff_client):
        settings.ALLOWED_HOSTS = ["testserver", "localhost", ".trycloudflare.com", ".ngrok-free.app", "api.example.com"]
        for host in ("abc.trycloudflare.com", "abc.ngrok-free.app", "api.example.com"):
            for path in ("/admin/", "/admin/login/", "/admin/accounts/users/admin/", "/admin/accounts/users/students/"):
                assert staff_client.get(path, HTTP_HOST=host).status_code == 404, (host, path)

    def test_local_hostnames_work(self, settings, staff_client):
        settings.ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1", "[::1]"]
        settings.DJANGO_ADMIN_ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]  # the shipped default
        for host in ("localhost", "localhost:8000", "127.0.0.1:8000", "[::1]:8000"):
            assert staff_client.get("/admin/", HTTP_HOST=host).status_code == 200, host

    def test_the_allow_list_is_configurable(self, settings, staff_client):
        settings.ALLOWED_HOSTS = ["testserver", "intranet.example.com"]
        assert staff_client.get("/admin/", HTTP_HOST="intranet.example.com").status_code == 404
        settings.DJANGO_ADMIN_ALLOWED_HOSTS = ["intranet.example.com"]
        assert staff_client.get("/admin/", HTTP_HOST="intranet.example.com").status_code == 200

    def test_the_api_is_reachable_on_public_hosts(self, settings, student):
        settings.ALLOWED_HOSTS = ["testserver", ".trycloudflare.com"]
        res = APIClient().post(
            "/api/accounts/login/", {"email": student.email, "password": PASSWORD}, format="json", HTTP_HOST="abc.trycloudflare.com"
        )
        assert res.status_code == 200
        assert APIClient().get("/api/student/profile/", HTTP_HOST="abc.trycloudflare.com").status_code == 401


class TestStateIsProtected:
    @pytest.mark.parametrize("model", [AuditEvent, Payment, StripeEvent])
    def test_read_only_models_have_no_write_permissions(self, model, staff_client, staff):
        model_admin = admin.site._registry[model]
        request = type("R", (), {"user": staff})()
        assert not model_admin.has_add_permission(request)
        assert not model_admin.has_change_permission(request)
        assert not model_admin.has_delete_permission(request)
        assert model_admin.has_view_permission(request)

    def test_payments_cannot_be_forged_through_the_admin(self, staff_client):
        assert staff_client.get("/admin/payments/payment/add/").status_code == 403
        assert staff_client.post("/admin/payments/payment/add/", {"amount": "1.00"}).status_code == 403

    def test_audit_log_is_view_only(self, staff_client, staff):
        from audit.services import create_audit_event

        create_audit_event("test.event", actor_email="someone@example.com")
        event = AuditEvent.objects.first()
        assert staff_client.get("/admin/audit/auditevent/").status_code == 200
        assert staff_client.get(f"/admin/audit/auditevent/{event.pk}/delete/").status_code == 403
        assert staff_client.post(f"/admin/audit/auditevent/{event.pk}/change/", {"action": "x"}).status_code == 403
        assert AuditEvent.objects.filter(pk=event.pk).exists()

    def test_user_secrets_are_not_shown_or_editable(self, staff_client, student):
        page = staff_client.get(f"/admin/accounts/studentuser/{student.pk}/change/").content.decode()
        assert student.email in page
        for hidden in ("totp_secret", 'name="password"', "user_permissions", student.password[:20]):
            assert hidden not in page, hidden
        assert staff_client.get("/admin/accounts/studentuser/add/").status_code == 403
        assert staff_client.get(f"/admin/accounts/studentuser/{student.pk}/delete/").status_code == 403

    def test_role_and_status_cannot_be_changed_here(self, staff_client, student):
        staff_client.post(
            f"/admin/accounts/studentuser/{student.pk}/change/",
            {"full_name": "Renamed", "first_name": "R", "middle_name": "", "last_name": "N", "phone_number": "", "email_notifications": "on",
             "role": "admin", "status": "suspended", "is_staff": "on", "is_superuser": "on"},
        )
        student.refresh_from_db()
        assert student.full_name == "Renamed"
        assert (student.role, student.status, student.is_staff, student.is_superuser) == ("student", "active", False, False)

    def test_resource_storage_key_is_never_displayed(self, staff_client, admin):
        from resources.models import Resource

        course = Course.objects.create(title="C", slug="c", status="published")
        resource = Resource.objects.create(
            course=course, title="R", storage_key="resources/secret-key-123.pdf", original_filename="a.pdf", file_size=10,
            page_count=1, sha256="0" * 64,
        )
        page = staff_client.get(f"/admin/resources/resource/{resource.pk}/change/").content.decode()
        assert "secret-key-123" not in page and "R" in page
        assert "secret-key-123" not in staff_client.get("/admin/resources/resource/").content.decode()

    def test_course_can_be_edited_but_not_deleted(self, staff_client):
        course = Course.objects.create(title="Old", slug="old", status="draft")
        assert staff_client.get(f"/admin/courses/course/{course.pk}/change/").status_code == 200
        assert staff_client.get(f"/admin/courses/course/{course.pk}/delete/").status_code == 403


class TestApiIsUntouched:
    def test_api_responses_set_no_cookies(self, student):
        res = APIClient().post("/api/accounts/login/", {"email": student.email, "password": PASSWORD}, format="json")
        assert res.status_code == 200 and not res.cookies
        assert not APIClient().get("/api/student/profile/").cookies

    def test_bearer_auth_ignores_admin_session_cookies(self, student, staff_client, staff):
        # An admin-site session must not authenticate anyone against the API.
        assert staff_client.get("/api/admin/students/").status_code == 401

    def test_api_post_works_without_a_csrf_token(self, student):
        c = APIClient(enforce_csrf_checks=True)
        res = c.post("/api/accounts/login/", {"email": student.email, "password": PASSWORD}, format="json")
        assert res.status_code == 200
        tokens = res.json()["data"]["tokens"]
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        assert c.patch("/api/student/profile/", {"first_name": "A", "last_name": "B"}, format="json").status_code == 200

    def test_login_still_works_end_to_end(self, student):
        assert login_student(APIClient(), student.email).status_code == 200
