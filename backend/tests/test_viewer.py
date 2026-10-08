import base64
import io
from datetime import timedelta

import pytest
from django.utils import timezone
from PIL import Image, ImageChops
from rest_framework.test import APIClient

from access.models import CourseAccess
from access.services import grant_course_access
from courses.models import Course
from resources.models import Resource
from viewing.models import ViewActivity
from viewing.services import apply_watermark

from .conftest import register_via_api, PASSWORD, auth_client, login_student, minted_client
from .test_resources import make_pdf_bytes, upload

pytestmark = pytest.mark.django_db


@pytest.fixture
def course(admin):
    return Course.objects.create(title="Biology", slug="biology", status="published", access_mode="manual_approval", created_by=admin)


@pytest.fixture
def resource(admin_client, course):
    rid = upload(admin_client, course, data=make_pdf_bytes(pages=3)).json()["data"]["id"]
    admin_client.post(f"/api/admin/course/resources/{rid}/validate/")
    admin_client.post(f"/api/admin/course/resources/{rid}/publish/")
    return Resource.objects.get(pk=rid)


@pytest.fixture
def granted(student, course, admin):
    return grant_course_access(student=student, course=course, source="admin_approval", actor=admin)


def page_url(resource, page=1):
    return f"/api/student/viewing/resources/{resource.id}/pages/{page}/"


def decode(res):
    return Image.open(io.BytesIO(base64.b64decode(res.json()["data"]["image"])))


class TestAccessEnforcement:
    def test_unauthenticated(self, client, resource):
        assert client.get(page_url(resource)).status_code == 401

    def test_no_access_record(self, student_client, resource):
        res = student_client.get(page_url(resource))
        assert res.status_code == 403 and res.json()["error"]["code"] == "ACCESS_REQUESTABLE"
        assert ViewActivity.objects.count() == 0

    def test_pending_access_denied(self, student_client, student, course, resource):
        CourseAccess.objects.create(student=student, course=course, status="pending")
        assert student_client.get(page_url(resource)).json()["error"]["code"] == "ACCESS_PENDING"

    def test_revoked_and_expired_denied(self, student_client, granted, resource):
        CourseAccess.objects.filter(pk=granted.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        assert student_client.get(page_url(resource)).json()["error"]["code"] == "ACCESS_EXPIRED"
        CourseAccess.objects.filter(pk=granted.pk).update(status="revoked")
        assert student_client.get(page_url(resource)).json()["error"]["code"] == "ACCESS_REVOKED"

    def test_other_students_access_does_not_help(self, other_student, granted, resource):
        c = APIClient()
        auth_client(c, login_student(c, other_student.email).json()["data"]["tokens"])
        assert c.get(page_url(resource)).status_code == 403
        assert c.get(f"/api/student/viewing/courses/{resource.course_id}/resources/").status_code == 403

    def test_pending_registration_denied(self, db, resource):
        c = APIClient()
        res = register_via_api(c, "p@example.com", password=PASSWORD)
        assert login_student(APIClient(), "p@example.com").status_code == 403  # no sign-in while pending
        from accounts.models import User

        c = minted_client(User.objects.get(email="p@example.com"))
        assert c.get(page_url(resource)).json()["error"]["code"] == "REGISTRATION_PENDING"

    def test_suspended_student_blocked(self, student_client, student, granted, resource):
        student.status = "suspended"
        student.save()
        assert student_client.get(page_url(resource)).status_code == 401

    def test_admin_is_not_a_viewer(self, admin_client, resource):
        assert admin_client.get(page_url(resource)).status_code == 403

    def test_unpublished_resource_is_404(self, student_client, granted, resource):
        Resource.objects.filter(pk=resource.pk).update(status="archived")
        assert student_client.get(page_url(resource)).status_code == 404

    def test_draft_course_resource_is_404(self, student_client, granted, resource, course):
        Course.objects.filter(pk=course.pk).update(status="archived")
        assert student_client.get(page_url(resource)).status_code == 404

    def test_resource_from_other_course_not_reachable_via_course_access(self, student_client, granted, admin_client, admin):
        other = Course.objects.create(title="Other", slug="other", status="published", created_by=admin)
        rid = upload(admin_client, other).json()["data"]["id"]
        admin_client.post(f"/api/admin/course/resources/{rid}/validate/")
        admin_client.post(f"/api/admin/course/resources/{rid}/publish/")
        assert student_client.get(f"/api/student/viewing/resources/{rid}/pages/1/").status_code == 403


class TestProtectedPages:
    def test_list_and_metadata(self, student_client, granted, resource):
        res = student_client.get(f"/api/student/viewing/courses/{resource.course_id}/resources/")
        assert res.status_code == 200 and res.json()["meta"]["count"] == 1
        item = res.json()["data"][0]
        assert item["page_count"] == 3
        assert not {"storage_key", "sha256", "file_size", "original_filename"} & set(item)
        meta = student_client.get(f"/api/student/viewing/resources/{resource.id}/").json()["data"]
        assert meta["id"] == str(resource.id)

    def test_unpublished_resources_not_listed(self, student_client, granted, resource, admin_client, course):
        draft = upload(admin_client, course).json()["data"]["id"]
        ids = [r["id"] for r in student_client.get(f"/api/student/viewing/courses/{course.id}/resources/").json()["data"]]
        assert ids == [str(resource.id)] and draft not in ids

    def test_page_is_rendered_image_not_pdf(self, student_client, granted, resource):
        res = student_client.get(page_url(resource, 2))
        assert res.status_code == 200
        assert res["Cache-Control"].startswith("no-store")
        body = res.json()["data"]
        assert body["page"] == 2 and body["page_count"] == 3 and body["content_type"] == "image/jpeg"
        raw = base64.b64decode(body["image"])
        assert raw[:2] == b"\xff\xd8" and b"%PDF" not in raw
        assert decode(res).width > 100
        assert "storage_key" not in str(body)

    def test_invalid_pages(self, student_client, granted, resource):
        for page in (0, 4, 999):
            res = student_client.get(page_url(resource, page))
            assert res.status_code == 404 and res.json()["error"]["code"] == "INVALID_PAGE"
        assert student_client.get(f"/api/student/viewing/resources/{resource.id}/pages/abc/").status_code == 404

    def test_watermark_comes_from_server_identity(self, student, other_student, granted, resource, course, admin):
        grant_course_access(student=other_student, course=course, source="admin_approval", actor=admin)
        images = []
        for user in (student, other_student):
            c = APIClient()
            auth_client(c, login_student(c, user.email).json()["data"]["tokens"])
            # client-supplied identity must be ignored
            res = c.get(page_url(resource) + "?student=hacker&name=hacker&watermark=none")
            assert res.status_code == 200
            images.append(res)
        assert images[0].json()["data"]["watermark_id"] != images[1].json()["data"]["watermark_id"]
        assert images[0].json()["data"]["image"] != images[1].json()["data"]["image"]

    def test_watermark_marks_a_blank_page(self, student, course):
        blank = Image.new("RGB", (900, 1200), "white")
        marked = apply_watermark(blank, f"{student.full_name} abc", [f"{student.full_name} <{student.email}>", f"ID {str(student.id)[:8]} | {course.title}", "2026-01-01 00:00:00 UTC | abc"])
        assert marked.size == blank.size
        assert marked.getbbox() is not None
        def changed_pixels(image, reference):
            """Pixels that differ from `reference`; uses only APIs that exist in every supported Pillow version."""
            diff = ImageChops.difference(image, reference).convert("L")
            return diff.width * diff.height - diff.histogram()[0]

        assert changed_pixels(marked, blank) > 2000
        # footer band is across the bottom
        assert changed_pixels(marked.crop((0, 1100, 900, 1200)), blank.crop((0, 1100, 900, 1200))) > 200

    def test_cannot_render_other_resource_without_access(self, student_client, resource):
        assert student_client.get(page_url(resource)).status_code == 403


class TestActivityAndHistory:
    def test_page_view_recorded(self, student_client, student, granted, resource):
        res = student_client.get(page_url(resource, 1))
        view = ViewActivity.objects.get()
        assert view.student == student and view.resource == resource and view.course == resource.course
        assert view.page_number == 1 and str(view.id) == res.json()["data"]["view_id"]
        assert view.watermark_id == res.json()["data"]["watermark_id"]

    def test_denied_access_records_nothing(self, student_client, resource):
        student_client.get(page_url(resource))
        assert ViewActivity.objects.count() == 0

    def test_duration_reporting(self, student_client, granted, resource):
        view_id = student_client.get(page_url(resource)).json()["data"]["view_id"]
        url = f"/api/student/viewing/resources/{resource.id}/activity/"
        res = student_client.post(url, {"view_id": view_id, "duration_seconds": 30}, format="json")
        assert res.status_code == 200 and res.json()["data"]["duration_seconds"] == 30
        again = student_client.post(url, {"view_id": view_id, "duration_seconds": 45}, format="json")
        assert again.json()["data"]["duration_seconds"] == 75

    def test_duration_validation(self, student_client, granted, resource):
        view_id = student_client.get(page_url(resource)).json()["data"]["view_id"]
        url = f"/api/student/viewing/resources/{resource.id}/activity/"
        assert student_client.post(url, {"view_id": view_id, "duration_seconds": 999999}, format="json").status_code == 400
        assert student_client.post(url, {"view_id": view_id, "duration_seconds": -1}, format="json").status_code == 400
        assert student_client.post(url, {"view_id": "nope", "duration_seconds": 1}, format="json").status_code == 400

    def test_cannot_report_for_unknown_or_foreign_view(self, student_client, other_student, granted, resource, course, admin):
        url = f"/api/student/viewing/resources/{resource.id}/activity/"
        missing = student_client.post(url, {"view_id": "00000000-0000-0000-0000-000000000000", "duration_seconds": 5}, format="json")
        assert missing.status_code == 404
        grant_course_access(student=other_student, course=course, source="admin_approval", actor=admin)
        c = APIClient()
        auth_client(c, login_student(c, other_student.email).json()["data"]["tokens"])
        foreign = c.get(page_url(resource)).json()["data"]["view_id"]
        stolen = student_client.post(url, {"view_id": foreign, "duration_seconds": 5}, format="json")
        assert stolen.status_code == 404
        assert ViewActivity.objects.get(pk=foreign).duration_seconds == 0

    def test_activity_requires_access(self, student_client, resource):
        res = student_client.post(f"/api/student/viewing/resources/{resource.id}/activity/", {"view_id": "00000000-0000-0000-0000-000000000000", "duration_seconds": 1}, format="json")
        assert res.status_code == 403

    def test_learning_history_is_own_only(self, student_client, student, other_student, granted, resource, course, admin):
        student_client.get(page_url(resource, 1))
        student_client.get(page_url(resource, 2))
        grant_course_access(student=other_student, course=course, source="admin_approval", actor=admin)
        c = APIClient()
        auth_client(c, login_student(c, other_student.email).json()["data"]["tokens"])
        c.get(page_url(resource, 3))
        mine = student_client.get("/api/student/learning-history/").json()
        assert mine["meta"]["count"] == 2 and {r["page_number"] for r in mine["data"]} == {1, 2}
        assert mine["data"][0]["resource_title"] == "Notes" and mine["data"][0]["course_title"] == "Biology"
        theirs = c.get("/api/student/learning-history/").json()
        assert theirs["meta"]["count"] == 1 and theirs["data"][0]["page_number"] == 3
        filtered = student_client.get(f"/api/student/learning-history/?resource={resource.id}")
        assert filtered.json()["meta"]["count"] == 2

    def test_history_requires_login_and_student(self, client, admin_client):
        assert client.get("/api/student/learning-history/").status_code in (401, 403)
        assert admin_client.get("/api/student/learning-history/").status_code == 403

    def test_history_survives_archiving_but_blocks_deleting(self, student_client, admin_client, granted, resource):
        student_client.get(page_url(resource))
        assert admin_client.post(f"/api/admin/course/resources/{resource.id}/archive/").status_code == 200
        res = admin_client.delete(f"/api/admin/course/resources/{resource.id}/")
        assert res.status_code == 409 and res.json()["error"]["code"] == "RESOURCE_IN_USE"
