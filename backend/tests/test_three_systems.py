"""Acceptance checks for the three separate interfaces: Django admin (/admin/), admin application (/api/admin/) and
student application (/api/student/). Each has its own login and none accepts another's credential."""
import pytest
from django.test import Client
from rest_framework.test import APIClient

from accounts.models import User

from .conftest import PASSWORD, admin_login_step, admin_otp_from_outbox, minted_client, register_via_api

pytestmark = pytest.mark.django_db


def bearer(token):
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


@pytest.fixture
def tokens(admin, student):
    """A real admin JWT (password + e-mailed code) and a real student JWT (password), plus a Django admin session."""
    c = APIClient()
    challenge = admin_login_step(c, admin.email).json()["data"]["challenge_token"]
    admin_jwt = c.post(
        "/api/admin/login/2fa/verify/", {"challenge_token": challenge, "otp": admin_otp_from_outbox(admin.email)}, format="json"
    ).json()["data"]["tokens"]["access"]
    student_jwt = APIClient().post(
        "/api/student/login/", {"email": student.email, "password": PASSWORD}, format="json"
    ).json()["data"]["tokens"]["access"]
    django = Client()
    assert django.post("/admin/login/?next=/admin/", {"username": admin.email, "password": PASSWORD}).status_code == 302
    return {"admin": admin_jwt, "student": student_jwt, "django": django, "challenge": challenge}


class TestEachSystemHasItsOwnCredential:
    def test_the_three_logins(self, tokens):
        assert tokens["django"].get("/admin/").status_code == 200  # A. e-mail + password -> Django session
        assert APIClient().get("/api/admin/reports/dashboard/", **bearer(tokens["admin"])).status_code == 200  # B. + e-mailed code -> JWT
        assert APIClient().get("/api/student/dashboard/", **bearer(tokens["student"])).status_code == 200  # C. password -> JWT

    def test_a_django_session_is_not_an_api_credential(self, tokens):
        for url in ("/api/admin/reports/dashboard/", "/api/student/dashboard/"):
            assert tokens["django"].get(url).status_code == 401

    def test_no_jwt_opens_the_django_admin(self, tokens):
        for jwt in (tokens["admin"], tokens["student"]):
            res = Client().get("/admin/", **bearer(jwt))
            assert res.status_code == 302 and res["Location"].startswith("/admin/login/")

    def test_the_two_jwts_do_not_cross(self, tokens):
        assert APIClient().get("/api/admin/students/", **bearer(tokens["student"])).status_code == 403
        assert APIClient().get("/api/student/dashboard/", **bearer(tokens["admin"])).status_code == 403
        assert APIClient().get("/api/student/profile/", **bearer(tokens["admin"])).status_code == 403

    def test_the_admin_challenge_is_not_a_bearer_token(self, tokens):
        for url in ("/api/admin/students/", "/api/student/dashboard/", "/api/accounts/me/"):
            assert APIClient().get(url, **bearer(tokens["challenge"])).status_code == 401

    def test_each_login_rejects_the_other_roles_credentials(self, admin, student):
        assert APIClient().post("/api/student/login/", {"email": admin.email, "password": PASSWORD}, format="json").status_code == 401
        assert APIClient().post("/api/admin/login/", {"email": student.email, "password": PASSWORD}, format="json").status_code == 401
        assert Client().post("/admin/login/", {"username": student.email, "password": PASSWORD}).status_code == 200  # form again
        assert "_auth_user_id" not in Client().session

    def test_only_the_admin_application_asks_for_a_code(self, admin, student):
        import django.core.mail as mail

        mail.outbox.clear()
        APIClient().post("/api/student/login/", {"email": student.email, "password": PASSWORD}, format="json")
        Client().post("/admin/login/", {"username": admin.email, "password": PASSWORD})
        assert not mail.outbox  # no code for the student login or the Django admin
        admin_login_step(APIClient(), admin.email)
        assert len(mail.outbox) == 1  # exactly one, for /api/admin/login/


class TestAdminApiChecksTheAccountOnEveryRequest:
    @pytest.mark.parametrize("status", ["pending", "rejected", "suspended"])
    def test_an_admin_token_stops_working_when_the_account_is_not_active(self, tokens, admin, status):
        assert APIClient().get("/api/admin/students/", **bearer(tokens["admin"])).status_code == 200
        User.objects.filter(pk=admin.pk).update(status=status)
        assert APIClient().get("/api/admin/students/", **bearer(tokens["admin"])).status_code in (401, 403)

    def test_a_demoted_admin_loses_the_api_at_once(self, tokens, admin):
        User.objects.filter(pk=admin.pk).update(role="student")
        assert APIClient().get("/api/admin/students/", **bearer(tokens["admin"])).status_code == 403

    def test_the_role_in_a_request_is_never_trusted(self, tokens):
        res = APIClient().get("/api/admin/students/?role=admin", **bearer(tokens["student"]), HTTP_X_ROLE="admin")
        assert res.status_code == 403


class TestStudentIsolationAndBlacklist:
    @pytest.fixture
    def two(self, admin_client, db):
        out = {}
        for first in ("Ravi", "Rahul"):
            register_via_api(APIClient(), f"{first.lower()}@example.com", first_name=first, last_name="Kumar")
            user = User.objects.get(email=f"{first.lower()}@example.com")
            admin_client.post(f"/api/admin/students/approval-requests/{user.id}/approve/")
            res = APIClient().post("/api/student/login/", {"email": user.email, "password": PASSWORD}, format="json")
            out[first] = (user, res.json()["data"]["tokens"])
        return out

    def test_ravi_and_rahul(self, two):
        ravi, rahul = two["Ravi"][1]["access"], two["Rahul"][1]["access"]
        c = APIClient()
        assert c.get("/api/student/Ravi/dashboard/", **bearer(ravi)).status_code == 200  # own: allow
        assert c.get("/api/student/Rahul/dashboard/", **bearer(ravi)).status_code == 403  # other: deny
        assert c.get("/api/student/Ravi/dashboard/", **bearer(rahul)).status_code == 403
        assert c.get("/api/student/Rahul/dashboard/", **bearer(rahul)).status_code == 200

    def test_ravi_cannot_reach_rahuls_records_by_id(self, two):
        from access.models import CourseAccess
        from courses.models import Course
        from notifications.models import Notification
        from payments.models import Payment

        rahul_user, _ = two["Rahul"]
        ravi = bearer(two["Ravi"][1]["access"])
        course = Course.objects.create(title="C", slug="c", status="published", access_mode="manual_approval", created_by=User.objects.filter(role="admin").first())
        access = CourseAccess.objects.create(student=rahul_user, course=course)
        payment = Payment.objects.create(student=rahul_user, course=course, amount="49.00", currency="USD")
        note = Notification.objects.filter(user=rahul_user).first()
        c = APIClient()
        assert c.get(f"/api/student/access/{access.id}/", **ravi).status_code == 404
        assert c.get(f"/api/student/payments/{payment.id}/", **ravi).status_code == 404
        assert c.get(f"/api/student/notifications/{note.id}/", **ravi).status_code == 404
        assert c.get("/api/student/learning-history/", **ravi).json()["meta"]["count"] == 0

    def test_a_logged_out_token_pair_is_dead(self, two):
        tokens = two["Ravi"][1]
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        assert c.post("/api/accounts/logout/", {"refresh": tokens["refresh"]}, format="json").status_code == 200
        assert APIClient().get("/api/student/Ravi/dashboard/", **bearer(tokens["access"])).status_code == 401
        assert APIClient().post("/api/accounts/refresh/", {"refresh": tokens["refresh"]}, format="json").status_code == 401


class TestDjangoAdminSections:
    def test_the_sidebar_groups_accounts_into_admin_and_student_users(self, admin):
        c = Client()
        c.post("/admin/login/?next=/admin/", {"username": admin.email, "password": PASSWORD})
        page = c.get("/admin/").content.decode()
        accounts = page[page.index("Accounts"):]
        assert accounts.index("Admin users") < accounts.index("Student users")
        for model in ("Courses", "Resources", "Course access", "Payments", "Notifications", "Audit events", "Platform settings", "Stripe events", "View activit"):
            assert model in page, model
        assert "/admin/accounts/user/" not in page  # no combined generic User listing
