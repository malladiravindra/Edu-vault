"""The whole student workflow through the real API: register -> admin approval -> login -> dashboard -> courses,
access, resources, notifications, activity, profile, logout. Everything is read from the database; the student is always
identified by the JWT, and the student flow is separate from the admin e-mail-code flow and from the Django admin."""
import pytest
from django.core import mail
from django.test import Client
from rest_framework.test import APIClient

from accounts.models import User
from courses.models import Course
from notifications.models import Notification
from resources.models import Resource

from .conftest import PASSWORD, admin_otp_from_outbox, auth_client, login_student, minted_client, register_via_api
from .test_resources import make_pdf_bytes, upload

pytestmark = pytest.mark.django_db

EMAIL = "new.student@example.com"
DASHBOARD = "/api/student/dashboard/"


@pytest.fixture
def pending():
    """A student who registered through the real 3-step flow and is awaiting approval."""
    res = register_via_api(APIClient(), EMAIL, first_name="Asha", last_name="Rao")
    assert res.status_code == 201
    return User.objects.get(email=EMAIL)


def approve(admin_client, user):
    return admin_client.post(f"/api/admin/students/approval-requests/{user.id}/approve/")


def signed_in(email, password=PASSWORD):
    c = APIClient()
    res = login_student(c, email, password)
    assert res.status_code == 200, res.content
    return auth_client(c, res.json()["data"]["tokens"])


class TestRegistration:
    def test_register_creates_one_pending_student_and_no_tokens(self, db):
        c = APIClient()
        res = register_via_api(c, EMAIL, first_name="Asha", last_name="Rao", role="admin", status="active", is_staff=True)
        assert res.status_code == 201
        body = res.json()["data"]
        assert "tokens" not in res.content.decode() and body["student"]["status"] == "pending"
        user = User.objects.get(email=EMAIL)
        assert User.objects.filter(email=EMAIL).count() == 1
        assert (user.role, user.status, user.is_staff, user.is_superuser) == ("student", "pending", False, False)
        assert user.check_password(PASSWORD) and user.password != PASSWORD

    def test_registration_needs_a_verified_email_and_is_not_repeatable(self, db, pending):
        res = APIClient().post("/api/student/register/", {
            "first_name": "X", "last_name": "Y", "phone_number": "9876543210", "email": "unverified@example.com",
            "password": PASSWORD, "confirm_password": PASSWORD}, format="json")
        assert res.status_code == 403 and res.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"
        again = register_via_api(APIClient(), EMAIL)
        assert again.status_code in (409, 400, 403) and User.objects.filter(email=EMAIL).count() == 1

    def test_required_details_are_validated(self, db):
        res = APIClient().post("/api/student/register/", {"email": EMAIL}, format="json")
        assert res.status_code == 400 and res.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_the_admin_is_told_and_sees_the_request(self, admin_client, pending):
        assert Notification.objects.filter(type="new_registration").exists()
        listing = admin_client.get("/api/admin/students/approval-requests/").json()
        assert listing["meta"]["count"] == 1 and listing["data"][0]["email"] == EMAIL

    def test_the_deprecated_accounts_alias_behaves_identically(self, db):
        c = APIClient()
        c.post("/api/accounts/register/send-otp/", {"email": "alias@example.com"}, format="json")
        from .conftest import otp_from_outbox

        c.post("/api/accounts/register/verify-otp/", {"email": "alias@example.com", "otp": otp_from_outbox("alias@example.com")}, format="json")
        res = c.post("/api/accounts/register/", {
            "first_name": "A", "last_name": "B", "phone_number": "9876543210", "email": "alias@example.com",
            "password": PASSWORD, "confirm_password": PASSWORD}, format="json")
        assert res.status_code == 201 and User.objects.get(email="alias@example.com").status == "pending"


class TestApprovalAndLogin:
    def test_pending_student_cannot_log_in_on_either_route(self, pending):
        for url in ("/api/student/login/", "/api/accounts/login/"):
            res = APIClient().post(url, {"email": EMAIL, "password": PASSWORD}, format="json")
            assert res.status_code == 403 and res.json()["error"]["code"] == "REGISTRATION_PENDING", url
            assert "tokens" not in res.content.decode()

    def test_approval_then_login_gives_a_jwt_without_any_otp(self, admin_client, pending):
        assert approve(admin_client, pending).status_code == 200
        pending.refresh_from_db()
        assert pending.status == "active" and pending.reviewed_at is not None
        mail.outbox.clear()
        res = APIClient().post("/api/student/login/", {"email": EMAIL, "password": PASSWORD}, format="json")
        data = res.json()["data"]
        assert res.status_code == 200 and {"access", "refresh"} <= set(data["tokens"])
        assert "challenge_token" not in data and "requires_two_factor" not in data and not mail.outbox
        assert data["user"]["role"] == "student" and data["user"]["status"] == "active"

    def test_rejection_blocks_login_and_notifies(self, admin_client, pending):
        res = admin_client.post(f"/api/admin/students/approval-requests/{pending.id}/reject/", {"reason": "Incomplete"}, format="json")
        assert res.status_code == 200
        denied = login_student(APIClient(), EMAIL)
        assert denied.status_code == 403 and denied.json()["error"]["code"] == "REGISTRATION_REJECTED"
        assert Notification.objects.filter(user=pending, type="registration_rejected").exists()
        assert approve(admin_client, pending).status_code == 409  # rejected is final: only pending can be approved

    def test_approval_notifies_the_student(self, admin_client, pending):
        approve(admin_client, pending)
        assert Notification.objects.filter(user=pending, type="registration_approved").exists()

    def test_lifecycle_only_allows_the_documented_transitions(self, admin_client, pending):
        assert admin_client.post(f"/api/admin/students/{pending.id}/suspend/").status_code == 409  # pending -> suspended: no
        approve(admin_client, pending)
        assert approve(admin_client, pending).status_code == 409  # active -> active: no
        assert admin_client.post(f"/api/admin/students/{pending.id}/suspend/").status_code == 200  # active -> suspended

    def test_suspension_blocks_login_and_kills_existing_sessions(self, admin_client, pending):
        approve(admin_client, pending)
        res = APIClient().post("/api/student/login/", {"email": EMAIL, "password": PASSWORD}, format="json")
        tokens = res.json()["data"]["tokens"]
        admin_client.post(f"/api/admin/students/{pending.id}/suspend/")
        denied = login_student(APIClient(), EMAIL)
        assert denied.status_code == 403 and denied.json()["error"]["code"] == "ACCOUNT_SUSPENDED"
        assert APIClient().post("/api/accounts/refresh/", {"refresh": tokens["refresh"]}, format="json").status_code == 401
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        assert c.get(DASHBOARD).status_code == 401

    def test_wrong_password_and_unknown_email_reveal_nothing(self, pending):
        a = login_student(APIClient(), EMAIL, "Wrong-Passw0rd!x")
        b = login_student(APIClient(), "ghost@example.com", "Wrong-Passw0rd!x")
        assert a.status_code == b.status_code == 401 and a.json() == b.json()

    def test_student_credentials_do_not_open_the_admin_surfaces(self, admin_client, pending):
        approve(admin_client, pending)
        assert APIClient().post("/api/admin/login/", {"email": EMAIL, "password": PASSWORD}, format="json").status_code == 401
        c = signed_in(EMAIL)
        assert c.get("/api/admin/students/").status_code == 403
        assert c.get("/api/admin/reports/dashboard/").status_code == 403
        django = Client()
        assert django.post("/admin/login/", {"username": EMAIL, "password": PASSWORD}).status_code == 200
        assert "_auth_user_id" not in django.session

    def test_admin_credentials_do_not_open_the_student_login(self, admin):
        res = APIClient().post("/api/student/login/", {"email": admin.email, "password": PASSWORD}, format="json")
        assert res.status_code == 401 and "tokens" not in res.content.decode()
        assert not admin_otp_from_outbox(admin.email)

    def test_a_token_of_a_non_approved_student_is_still_refused(self, pending):
        c = minted_client(pending)
        assert c.get("/api/student/course/").json()["error"]["code"] == "REGISTRATION_PENDING"
        assert c.get("/api/student/access/").status_code == 403


class TestDashboard:
    SECTIONS = {
        "profile", "registration", "active_courses", "pending_requests", "payment_requests", "recent_payments",
        "recent_activity", "notifications", "learning_stats",
    }

    @pytest.fixture
    def two_students(self, admin_client, db):
        users = []
        for email in ("alice@example.com", "bob@example.com"):
            register_via_api(APIClient(), email)
            user = User.objects.get(email=email)
            approve(admin_client, user)
            users.append(user)
        return users

    def test_dashboard_has_every_section_and_needs_a_token(self, two_students):
        alice, _ = two_students
        assert APIClient().get(DASHBOARD).status_code == 401
        data = signed_in(alice.email).get(DASHBOARD).json()["data"]
        assert self.SECTIONS <= set(data)
        assert data["profile"]["email"] == alice.email and data["registration"]["status"] == "active"
        assert data["learning_stats"]["total_courses"] == 0 and data["recent_payments"] == []

    def test_each_student_sees_only_their_own_data(self, admin_client, admin, two_students):
        alice, bob = two_students
        course = Course.objects.create(title="Maths", slug="maths", status="published", access_mode="manual_approval", created_by=admin)
        ca, cb = signed_in(alice.email), signed_in(bob.email)
        assert ca.post("/api/student/access/", {"course": str(course.id)}, format="json").status_code == 201
        a, b = ca.get(DASHBOARD).json()["data"], cb.get(DASHBOARD).json()["data"]
        assert [r["title"] for r in a["pending_requests"]] == ["Maths"] and b["pending_requests"] == []
        assert a["profile"]["email"] == alice.email and b["profile"]["email"] == bob.email
        # nothing in the request can address another student
        assert cb.get(f"{DASHBOARD}?student={alice.id}").json()["data"]["profile"]["email"] == bob.email

    def test_admin_decision_moves_the_course_to_active(self, admin_client, admin, two_students):
        alice, _ = two_students
        course = Course.objects.create(title="Physics", slug="physics", status="published", access_mode="manual_approval", created_by=admin)
        c = signed_in(alice.email)
        c.post("/api/student/access/", {"course": str(course.id)}, format="json")
        res = admin_client.post(f"/api/admin/students/{alice.id}/decision/", {"decision": "immediate", "course": str(course.id)}, format="json")
        assert res.status_code == 200
        data = c.get(DASHBOARD).json()["data"]
        assert [r["title"] for r in data["active_courses"]] == ["Physics"] and data["pending_requests"] == []
        assert Notification.objects.filter(user=alice, type="access_granted").exists()
        states = {row["slug"]: row for row in c.get("/api/student/course/").json()["data"]}
        assert states["physics"]["access"]["state"] == "granted"  # the API calls an active, unexpired access "granted"

    def test_course_states_come_from_the_database(self, admin, two_students):
        alice, _ = two_students
        Course.objects.create(title="Draft", slug="draft", status="draft", created_by=admin)
        Course.objects.create(title="Open", slug="open", status="published", access_mode="manual_approval", created_by=admin)
        rows = signed_in(alice.email).get("/api/student/course/").json()["data"]
        assert [r["slug"] for r in rows] == ["open"]  # drafts are never listed
        assert rows[0]["access"]["state"] == "requestable"  # manual course, nothing requested yet


class TestResourcesActivityAndNotifications:
    @pytest.fixture
    def setup(self, admin_client, admin, db):
        register_via_api(APIClient(), EMAIL)
        user = User.objects.get(email=EMAIL)
        approve(admin_client, user)
        course = Course.objects.create(title="Biology", slug="biology", status="published", access_mode="manual_approval", created_by=admin)
        rid = upload(admin_client, course, data=make_pdf_bytes(pages=2)).json()["data"]["id"]
        admin_client.post(f"/api/admin/course/resources/{rid}/validate/")
        admin_client.post(f"/api/admin/course/resources/{rid}/publish/")
        return user, course, Resource.objects.get(pk=rid)

    def test_resources_need_an_active_course_access(self, admin_client, setup):
        user, course, resource = setup
        c = signed_in(user.email)
        page = f"/api/student/viewing/resources/{resource.id}/pages/1/"
        assert c.get(page).status_code == 403  # no access yet
        c.post("/api/student/access/", {"course": str(course.id)}, format="json")
        assert c.get(page).status_code == 403  # still only pending
        admin_client.post(f"/api/admin/students/{user.id}/decision/", {"decision": "immediate", "course": str(course.id)}, format="json")
        res = c.get(page)
        assert res.status_code == 200 and res.json()["data"]["image"]

    def test_no_raw_storage_urls_or_downloads(self, admin_client, setup):
        user, course, resource = setup
        admin_client.post(f"/api/admin/students/{user.id}/decision/", {"decision": "immediate", "course": str(course.id)}, format="json")
        c = signed_in(user.email)
        listing = c.get(f"/api/student/viewing/courses/{course.id}/resources/").content.decode()
        assert resource.storage_key not in listing and "storage_key" not in listing and "http" not in listing
        assert c.get(f"/api/student/viewing/resources/{resource.id}/download/").status_code == 404

    def test_activity_is_recorded_and_private(self, admin_client, setup, admin):
        user, course, resource = setup
        admin_client.post(f"/api/admin/students/{user.id}/decision/", {"decision": "immediate", "course": str(course.id)}, format="json")
        c = signed_in(user.email)
        c.get(f"/api/student/viewing/resources/{resource.id}/pages/1/")
        mine = c.get("/api/student/learning-history/").json()
        assert mine["meta"]["count"] >= 1
        register_via_api(APIClient(), "other@example.com")
        other = User.objects.get(email="other@example.com")
        approve(admin_client, other)
        assert signed_in(other.email).get("/api/student/learning-history/").json()["meta"]["count"] == 0
        assert c.get(DASHBOARD).json()["data"]["recent_activity"]

    def test_notifications_belong_to_the_student(self, admin_client, setup):
        user, _, _ = setup
        c = signed_in(user.email)
        rows = c.get("/api/student/notifications/").json()["data"]
        assert {r["type"] for r in rows} >= {"registration_approved"}
        other_note = Notification.objects.exclude(user=user).first()
        if other_note:
            assert c.get(f"/api/student/notifications/{other_note.id}/").status_code == 404


class TestProfileAndLogout:
    def test_profile_updates_only_allowed_fields(self, admin_client, pending):
        approve(admin_client, pending)
        c = signed_in(EMAIL)
        res = c.patch("/api/student/profile/", {"first_name": "Ashaa", "last_name": "Raoo", "phone_number": "9123456789",
                                                  "role": "admin", "status": "pending", "is_staff": True, "email": "x@example.com"}, format="json")
        assert res.status_code == 200
        pending.refresh_from_db()
        assert pending.first_name == "Ashaa" and pending.phone_number == "9123456789"
        assert (pending.role, pending.status, pending.is_staff, pending.email) == ("student", "active", False, EMAIL)

    def test_settings_only_change_the_students_own_preferences(self, admin_client, pending):
        approve(admin_client, pending)
        c = signed_in(EMAIL)
        assert c.patch("/api/student/settings/", {"email_notifications": False, "status": "pending"}, format="json").status_code == 200
        pending.refresh_from_db()
        assert pending.email_notifications is False and pending.status == "active"

    def test_logout_blacklists_the_refresh_token(self, admin_client, pending):
        approve(admin_client, pending)
        tokens = login_student(APIClient(), EMAIL).json()["data"]["tokens"]
        c = APIClient()
        auth_client(c, tokens)
        assert c.post("/api/accounts/logout/", {"refresh": tokens["refresh"]}, format="json").status_code == 200
        assert APIClient().post("/api/accounts/refresh/", {"refresh": tokens["refresh"]}, format="json").status_code == 401
        assert c.get(DASHBOARD).status_code == 401  # the device session ended with it


class TestNamedDashboard:
    """GET /api/student/<name>/dashboard/: the JWT is the identity, the name is only checked against it."""

    @pytest.fixture
    def students(self, admin_client, db):
        out = {}
        for first, email in (("Ravi", "ravi@example.com"), ("Rahul", "rahul@example.com")):
            register_via_api(APIClient(), email, first_name=first, last_name="Kumar")
            user = User.objects.get(email=email)
            approve(admin_client, user)
            out[first] = (user, signed_in(email))
        return out

    def test_login_tells_the_frontend_where_the_dashboard_is(self, students):
        user, _ = students["Ravi"]
        res = login_student(APIClient(), user.email)
        assert res.json()["data"]["user"]["dashboard_path"] == "/api/student/Ravi/dashboard/"

    def test_each_student_opens_their_own_named_dashboard(self, students):
        for first in ("Ravi", "Rahul"):
            user, client = students[first]
            res = client.get(f"/api/student/{first}/dashboard/")
            assert res.status_code == 200 and res.json()["data"]["profile"]["email"] == user.email

    def test_a_valid_token_with_another_students_name_gets_nothing(self, students):
        (_, ravi), (_, rahul) = students["Ravi"], students["Rahul"]
        for client, wrong in ((ravi, "Rahul"), (rahul, "Ravi")):
            res = client.get(f"/api/student/{wrong}/dashboard/")
            assert res.status_code == 403 and res.json()["error"]["code"] == "STUDENT_MISMATCH"
            assert "profile" not in res.content.decode() and "@example.com" not in res.content.decode()

    def test_unknown_odd_and_injected_names_are_refused_safely(self, students):
        _, ravi = students["Ravi"]
        for name in ("Nobody", "ravi%2F..", "Ravi%20Kumar", "..", "%27%20OR%201=1", "R"):
            res = ravi.get(f"/api/student/{name}/dashboard/")
            assert res.status_code in (403, 404), (name, res.status_code)

    def test_the_name_is_case_insensitive_but_still_bound_to_the_token(self, students):
        _, ravi = students["Ravi"]
        assert ravi.get("/api/student/ravi/dashboard/").status_code == 200
        assert ravi.get("/api/student/RAVI/dashboard/").status_code == 200
        assert ravi.get("/api/student/rahul/dashboard/").status_code == 403

    def test_the_name_alone_is_not_authentication(self, students):
        assert APIClient().get("/api/student/Ravi/dashboard/").status_code == 401
        assert APIClient().get("/api/student/Ravi/dashboard/", HTTP_AUTHORIZATION="Bearer not-a-token").status_code == 401

    def test_query_parameters_and_ids_cannot_change_whose_dashboard_it_is(self, students):
        (rahul_user, _), (_, ravi) = students["Rahul"], students["Ravi"]
        res = ravi.get(f"/api/student/Ravi/dashboard/?student={rahul_user.id}&email={rahul_user.email}")
        assert res.json()["data"]["profile"]["email"] == "ravi@example.com"

    def test_two_students_with_the_same_first_name_each_see_only_their_own(self, admin_client, students):
        register_via_api(APIClient(), "ravi2@example.com", first_name="Ravi", last_name="Sharma")
        other = User.objects.get(email="ravi2@example.com")
        approve(admin_client, other)
        second = signed_in(other.email)
        first = students["Ravi"][1]
        assert second.get("/api/student/Ravi/dashboard/").json()["data"]["profile"]["last_name"] == "Sharma"
        assert first.get("/api/student/Ravi/dashboard/").json()["data"]["profile"]["last_name"] == "Kumar"

    def test_names_with_spaces_and_non_ascii_letters(self, admin_client, db):
        for first, email in (("Mary Ann", "mary@example.com"), ("José", "jose@example.com")):
            register_via_api(APIClient(), email, first_name=first, last_name="Lee")
            user = User.objects.get(email=email)
            approve(admin_client, user)
            c = signed_in(email)
            path = login_student(APIClient(), email).json()["data"]["user"]["dashboard_path"]
            assert c.get(path).status_code == 200, path
            assert c.get("/api/student/Somebody/dashboard/").status_code == 403

    def test_admins_and_non_approved_students_do_not_get_a_dashboard(self, admin_client, pending):
        assert admin_client.get("/api/student/Admin/dashboard/").status_code == 403
        c = minted_client(pending)  # a pending student cannot sign in; even a minted token gets nothing
        for url in ("/api/student/Asha/dashboard/", "/api/student/dashboard/"):
            res = c.get(url)
            assert res.status_code == 403 and res.json()["error"]["code"] == "REGISTRATION_PENDING", url

    def test_suspension_closes_the_named_dashboard_too(self, admin_client, students):
        user, client = students["Ravi"]
        admin_client.post(f"/api/admin/students/{user.id}/suspend/")
        assert client.get("/api/student/Ravi/dashboard/").status_code == 401

    def test_the_plain_dashboard_and_every_fixed_student_route_still_work(self, students):
        _, ravi = students["Ravi"]
        assert ravi.get("/api/student/dashboard/").status_code == 200
        for path in ("course/", "access/", "payments/", "payment-requests/", "notifications/", "profile/", "settings/", "learning-history/"):
            assert ravi.get(f"/api/student/{path}").status_code == 200, path

    def test_a_student_first_named_like_a_route_does_not_shadow_it(self, admin_client, db):
        register_via_api(APIClient(), "access@example.com", first_name="Access", last_name="Rao")
        user = User.objects.get(email="access@example.com")
        approve(admin_client, user)
        c = signed_in(user.email)
        assert c.get("/api/student/Access/dashboard/").status_code == 200
        assert c.get("/api/student/access/").status_code == 200  # the fixed route is untouched
