"""Create / read / update / delete on the existing endpoints, valid and invalid, with the response envelope."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from access.models import CourseAccess
from accounts.models import User
from courses.models import Course
from notifications.models import Notification
from platform_settings.models import PlatformSettings
from resources.models import Resource
from resources.storage import get_private_storage

from .conftest import PASSWORD
from .test_resources import make_pdf_bytes

pytestmark = pytest.mark.django_db
NIL = "00000000-0000-0000-0000-000000000000"


def ok(res, status=200):
    body = res.json()
    assert res.status_code == status, body
    assert body["success"] is True and "data" in body and "meta" in body and "error" not in body
    return body["data"]


def err(res, status, code=None):
    body = res.json()
    assert res.status_code == status, body
    assert body["success"] is False and set(body["error"]) == {"code", "message", "details"} and "data" not in body
    if code:
        assert body["error"]["code"] == code
    return body["error"]


def send(client, method, url, data=None):
    return getattr(client, method)(url, data if data is not None else {}, format="json")


COURSE = {"title": "Algebra", "description": "d", "category": "math", "access_mode": "manual_approval"}


class TestCourseCrud:
    def test_create_read_update_delete(self, admin_client):
        created = ok(send(admin_client, "post", "/api/admin/course/", COURSE), 201)
        url = f"/api/admin/course/{created['id']}/"
        assert created["status"] == "draft" and Course.objects.filter(pk=created["id"]).exists()
        assert ok(admin_client.get(url))["title"] == "Algebra"
        assert any(c["id"] == created["id"] for c in ok(admin_client.get("/api/admin/course/")))
        assert ok(send(admin_client, "patch", url, {"title": "Algebra II"}))["title"] == "Algebra II"
        replaced = ok(send(admin_client, "put", url, {"title": "Geometry", "access_mode": "payment_required", "price_amount": "10.00"}))
        assert replaced["title"] == "Geometry" and replaced["description"] == "" and replaced["price_amount"] == "10.00"
        ok(admin_client.delete(url))
        assert not Course.objects.filter(pk=created["id"]).exists()
        err(admin_client.get(url), 404, "NOT_FOUND")

    @pytest.mark.parametrize("method", ["post", "put", "patch"])
    def test_invalid_input_is_a_validation_error(self, method, admin_client):
        course = Course.objects.create(title="C", slug="c")
        url = "/api/admin/course/" if method == "post" else f"/api/admin/course/{course.id}/"
        bad = {"title": "x", "access_mode": "payment_required"}  # paid course without a price
        details = err(send(admin_client, method, url, bad), 400, "VALIDATION_ERROR")["details"]
        assert "price_amount" in details["fields"]
        err(send(admin_client, method, url, {"title": ""}), 400, "VALIDATION_ERROR")

    def test_nothing_changed_by_invalid_requests(self, admin_client):
        course = Course.objects.create(title="Keep", slug="keep")
        send(admin_client, "patch", f"/api/admin/course/{course.id}/", {"access_mode": "nope"})
        course.refresh_from_db()
        assert course.title == "Keep" and course.access_mode == "manual_approval"

    def test_delete_is_blocked_when_the_course_is_in_use(self, admin_client, student):
        course = Course.objects.create(title="Used", slug="used", status="published")
        CourseAccess.objects.create(student=student, course=course, status="active")
        err(admin_client.delete(f"/api/admin/course/{course.id}/"), 409, "COURSE_IN_USE")
        assert Course.objects.filter(pk=course.pk).exists()

    def test_only_admins(self, student_client, admin_client):
        course = Course.objects.create(title="C", slug="c")
        url = f"/api/admin/course/{course.id}/"
        for method in ("get", "patch", "put", "delete"):
            err(send(student_client, method, url, {"title": "x"}), 403)
            err(send(APIClient(), method, url, {"title": "x"}), 401)
        err(send(student_client, "post", "/api/admin/course/", COURSE), 403)
        assert Course.objects.filter(pk=course.pk, title="C").exists()


class TestResourceCrud:
    def upload(self, client, course, name="notes.pdf", data=None, ctype="application/pdf"):
        payload = {"course": str(course.id), "title": "Notes", "file": SimpleUploadedFile(name, make_pdf_bytes() if data is None else data, ctype)}
        return client.post("/api/admin/course/resources/", payload, format="multipart")

    def test_create_read_update_delete_removes_the_file(self, admin_client, django_capture_on_commit_callbacks):
        course = Course.objects.create(title="C", slug="c", status="published")
        created = ok(self.upload(admin_client, course), 201)
        url = f"/api/admin/course/resources/{created['id']}/"
        key = Resource.objects.get(pk=created["id"]).storage_key
        assert created["status"] == "draft" and "storage_key" not in created and get_private_storage().exists(key)
        assert ok(admin_client.get(url))["title"] == "Notes"
        assert ok(send(admin_client, "patch", url, {"title": "Renamed"}))["title"] == "Renamed"
        with django_capture_on_commit_callbacks(execute=True):
            ok(admin_client.delete(url))
        assert not Resource.objects.filter(pk=created["id"]).exists() and not get_private_storage().exists(key)

    def test_invalid_uploads_and_updates(self, admin_client):
        course = Course.objects.create(title="C", slug="c", status="published")
        err(self.upload(admin_client, course, name="a.txt", ctype="text/plain"), 400, "INVALID_PDF")
        err(self.upload(admin_client, course, data=b"%PDF-not really"), 400)
        err(admin_client.post("/api/admin/course/resources/", {"title": "no file"}, format="multipart"), 400, "VALIDATION_ERROR")
        rid = ok(self.upload(admin_client, course), 201)["id"]
        err(send(admin_client, "patch", f"/api/admin/course/resources/{rid}/", {"title": "x" * 201}), 400, "VALIDATION_ERROR")
        assert Resource.objects.get(pk=rid).title == "Notes"

    def test_only_admins(self, admin_client, student_client):
        course = Course.objects.create(title="C", slug="c", status="published")
        rid = ok(self.upload(admin_client, course), 201)["id"]
        url = f"/api/admin/course/resources/{rid}/"
        for method in ("get", "patch", "delete"):
            err(send(student_client, method, url, {"title": "x"}), 403)
            err(send(APIClient(), method, url, {"title": "x"}), 401)
        err(self.upload(student_client, course), 403)
        assert Resource.objects.filter(pk=rid).exists()


class TestStudentManagementCrud:
    def test_admin_reads_updates_and_deletes_a_student(self, admin_client, student):
        url = f"/api/admin/students/{student.id}/"
        assert ok(admin_client.get(url))["email"] == student.email
        assert ok(send(admin_client, "patch", url, {"full_name": "Renamed"}))["full_name"] == "Renamed"
        err(send(admin_client, "patch", url, {"full_name": ""}), 400, "VALIDATION_ERROR")
        ok(admin_client.delete(url))
        assert not User.objects.filter(pk=student.pk).exists()

    def test_delete_guards(self, admin_client, admin, student_client, other_student):
        err(admin_client.delete(f"/api/admin/students/{admin.id}/"), 400)
        assert User.objects.filter(pk=admin.pk).exists()
        err(student_client.delete(f"/api/admin/students/{other_student.id}/"), 403)
        err(APIClient().delete(f"/api/admin/students/{other_student.id}/"), 401)
        assert User.objects.filter(pk=other_student.pk).exists()
        err(admin_client.delete(f"/api/admin/students/{NIL}/"), 404, "NOT_FOUND")


class TestNotificationDelete:
    def test_delete_own_only(self, student_client, student, other_student):
        mine = Notification.objects.create(user=student, type="security", title="t", message="m")
        theirs = Notification.objects.create(user=other_student, type="security", title="t", message="m")
        err(student_client.delete(f"/api/student/notifications/{theirs.id}/"), 404)
        assert Notification.objects.filter(pk=theirs.pk).exists()
        ok(student_client.delete(f"/api/student/notifications/{mine.id}/"))
        assert not Notification.objects.filter(pk=mine.pk).exists()
        err(APIClient().delete(f"/api/student/notifications/{theirs.id}/"), 401)


class TestOtherWriteEndpoints:
    def test_student_profile_and_settings(self, student_client, student):
        assert ok(send(student_client, "patch", "/api/student/profile/", {"first_name": "Ann", "last_name": "Lee"}))["full_name"] == "Ann Lee"
        err(send(student_client, "patch", "/api/student/profile/", {"phone_number": "abc"}), 400, "VALIDATION_ERROR")
        assert ok(send(student_client, "patch", "/api/student/settings/", {"email_notifications": False}))["email_notifications"] is False
        err(send(student_client, "patch", "/api/student/settings/", {"email_notifications": "maybe"}), 400, "VALIDATION_ERROR")

    def test_student_access_request(self, student_client, student):
        course = Course.objects.create(title="Free", slug="free", status="published", access_mode="immediate")
        data = ok(send(student_client, "post", "/api/student/access/", {"course": str(course.id)}), 201)
        assert data["status"] == "active" and CourseAccess.objects.filter(student=student, course=course).exists()
        err(send(student_client, "post", "/api/student/access/", {}), 400, "VALIDATION_ERROR")
        err(send(student_client, "post", "/api/student/access/", {"course": "not-a-uuid"}), 400, "VALIDATION_ERROR")
        err(send(student_client, "post", "/api/student/access/", {"course": NIL}), 404)

    def test_admin_access_grant_and_decision(self, admin_client, student):
        course = Course.objects.create(title="C", slug="c", status="published")
        granted = ok(send(admin_client, "post", "/api/admin/students/access/grant/", {"course": str(course.id), "student": str(student.id)}), 201)
        err(send(admin_client, "post", "/api/admin/students/access/grant/", {"course": str(course.id)}), 400, "VALIDATION_ERROR")
        url = f"/api/admin/students/access/{granted['id']}/"
        assert ok(send(admin_client, "patch", url, {"action": "revoke"}))["status"] == "revoked"
        err(send(admin_client, "patch", url, {"action": "explode"}), 400, "VALIDATION_ERROR")
        err(send(admin_client, "patch", url, {"action": "revoke"}), 409, "INVALID_STATE")

    def test_admin_settings_and_profile(self, admin_client):
        assert ok(send(admin_client, "patch", "/api/admin/settings/", {"login_max_attempts": 7}))["settings"]["login_max_attempts"] == 7
        assert PlatformSettings.objects.get(pk=1).login_max_attempts == 7
        err(send(admin_client, "patch", "/api/admin/settings/", {"login_max_attempts": 0}), 400, "VALIDATION_ERROR")
        assert ok(send(admin_client, "patch", "/api/admin/profile/", {"first_name": "A", "last_name": "B"}))["full_name"] == "A B"
        err(send(admin_client, "patch", "/api/admin/profile/", {}), 400, "VALIDATION_ERROR")

    def test_login_valid_and_invalid(self, student):
        good = ok(send(APIClient(), "post", "/api/accounts/login/", {"email": student.email, "password": PASSWORD}))
        assert set(good["tokens"]) == {"access", "refresh"}
        err(send(APIClient(), "post", "/api/accounts/login/", {"email": student.email, "password": "nope"}), 401, "INVALID_CREDENTIALS")
        err(send(APIClient(), "post", "/api/accounts/login/", {}), 400, "VALIDATION_ERROR")
