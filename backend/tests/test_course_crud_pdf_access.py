"""Course CRUD (admin only), course read rules, and course-PDF access states through the protected viewer.

The project intentionally has no raw PDF download: pages are served as server-rendered, watermarked images, so the
"download allowed" rule is tested on the viewer page endpoint (see PROJECT_ISSUES_AUDIT.md, section 11).
"""
import json
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from access.models import CourseAccess
from access.services import evaluate_access
from audit.models import AuditEvent
from courses.models import Course
from resources.models import Resource

from .test_resources import make_pdf_bytes, upload

pytestmark = pytest.mark.django_db


@pytest.fixture
def course(admin):
    return Course.objects.create(title="Chem", slug="chem", status="published", access_mode="manual_approval", created_by=admin)


@pytest.fixture
def rid(admin_client, course):
    rid = upload(admin_client, course, data=make_pdf_bytes(pages=2)).json()["data"]["id"]
    admin_client.post(f"/api/admin/course/resources/{rid}/validate/")
    admin_client.post(f"/api/admin/course/resources/{rid}/publish/")
    return rid


def pages(c, rid):
    return c.get(f"/api/student/viewing/resources/{rid}/pages/1/")


class TestCourseCrudStatuses:
    def test_create_read_update_archive_with_exact_statuses(self, admin_client):
        created = admin_client.post("/api/admin/course/", {"title": "Physics", "access_mode": "manual_approval"}, format="json")
        assert created.status_code == 201 and set(created.json()) >= {"success", "data"}
        cid = created.json()["data"]["id"]
        assert Course.objects.filter(pk=cid, title="Physics").exists()  # stored in the database
        assert admin_client.get(f"/api/admin/course/{cid}/").status_code == 200
        assert admin_client.patch(f"/api/admin/course/{cid}/", {"title": "Physics 2"}, format="json").status_code == 200
        assert admin_client.post(f"/api/admin/course/{cid}/archive/").status_code == 200
        assert Course.objects.get(pk=cid).status == "archived"
        assert [AuditEvent.objects.filter(action=a, target_id=cid).exists() for a in ("course.created", "course.updated", "course.archived")] == [True] * 3

    def test_invalid_course_is_rejected_by_the_existing_serializer(self, admin_client):
        res = admin_client.post("/api/admin/course/", {}, format="json")
        assert res.status_code == 400 and res.json()["success"] is False

    def test_archiving_keeps_access_records(self, admin_client, student, course):
        record = CourseAccess.objects.create(student=student, course=course, status="active")
        admin_client.post(f"/api/admin/course/{course.id}/archive/")
        assert CourseAccess.objects.filter(pk=record.pk).exists()
        assert evaluate_access(student, Course.objects.get(pk=course.pk)).allowed is False

    def test_delete_is_blocked_while_dependent_records_exist(self, admin_client, student, course):
        CourseAccess.objects.create(student=student, course=course, status="active")
        assert admin_client.delete(f"/api/admin/course/{course.id}/").status_code in (400, 409)
        assert Course.objects.filter(pk=course.pk).exists()


class TestCourseReadRules:
    def test_read_matrix(self, student_client, admin_client, course, student):
        client = APIClient()
        assert client.get(f"/api/student/course/{course.id}/").status_code == 401
        assert client.get(f"/api/admin/course/{course.id}/").status_code == 401
        assert admin_client.get(f"/api/admin/course/{course.id}/").status_code == 200
        assert student_client.get("/api/student/course/").status_code == 200
        assert student_client.get(f"/api/student/course/{course.id}/").status_code == 200
        assert student_client.get(f"/api/admin/course/{course.id}/").status_code == 403

    def test_student_sees_no_admin_only_fields_or_unpublished_courses(self, student_client, admin, course):
        Course.objects.create(title="Secret", slug="secret", status="draft", created_by=admin)
        listing = student_client.get("/api/student/course/").content.decode()
        detail = student_client.get(f"/api/student/course/{course.id}/").content.decode()
        assert "Secret" not in listing
        for body in (listing, detail):
            assert "created_by" not in body and "storage_key" not in body and "sha256" not in body

    def test_resources_appear_only_when_the_central_check_allows(self, student_client, student, course, rid):
        body = student_client.get(f"/api/student/course/{course.id}/").json()["data"]
        assert body["resources"] == [] and body["access"]["allowed"] is False
        CourseAccess.objects.create(student=student, course=course, status="active")
        body = student_client.get(f"/api/student/course/{course.id}/").json()["data"]
        assert [r["id"] for r in body["resources"]] == [rid] and body["access"]["allowed"] is True


class TestPdfAccessStates:
    def test_active_access_is_served_a_protected_page(self, student_client, student, course, rid):
        CourseAccess.objects.create(student=student, course=course, status="active")
        res = pages(student_client, rid)
        assert res.status_code == 200 and res["Content-Type"].startswith("application/json")
        assert res.json()["data"]["image"]  # server-rendered page; the source PDF bytes are never sent
        assert "no-store" in res["Cache-Control"]
        assert b"%PDF" not in res.content

    @pytest.mark.parametrize("state,kwargs", [
        ("pending", {"status": "pending"}),
        ("payment_required", {"status": "pending", "payment_required": True}),
        ("rejected", {"status": "rejected"}),
        ("revoked", {"status": "revoked"}),
        ("expired", {"status": "active", "expires_at": "past"}),
    ])
    def test_not_active_states_are_denied(self, state, kwargs, student_client, student, course, rid):
        if kwargs.get("expires_at") == "past":
            kwargs = {**kwargs, "expires_at": timezone.now() - timedelta(minutes=1)}
        CourseAccess.objects.create(student=student, course=course, **kwargs)
        res = pages(student_client, rid)
        assert res.status_code == 403 and res.json()["success"] is False
        assert student_client.get(f"/api/student/viewing/courses/{course.id}/resources/").status_code == 403

    def test_suspended_student_is_denied_even_with_active_access(self, student_client, student, course, rid):
        CourseAccess.objects.create(student=student, course=course, status="active")
        student.status = "suspended"
        student.save()
        assert pages(student_client, rid).status_code in (401, 403)

    def test_anonymous_is_401_and_admin_is_not_a_viewer(self, admin_client, rid):
        client = APIClient()
        assert pages(client, rid).status_code == 401
        assert pages(admin_client, rid).status_code == 403

    def test_there_is_no_download_or_public_file_route(self, student_client, student, course, rid):
        CourseAccess.objects.create(student=student, course=course, status="active")
        for url in (f"/api/student/viewing/resources/{rid}/download/", f"/api/student/course/{course.id}/resources/{rid}/download/",
                    f"/media/{rid}.pdf", f"/public/{rid}.pdf"):
            assert student_client.get(url).status_code == 404
        every_body = [student_client.get(u).content.decode() for u in
                      (f"/api/student/viewing/resources/{rid}/", f"/api/student/viewing/courses/{course.id}/resources/")]
        assert all("storage_key" not in b and "http" not in b for b in every_body)


class TestIdManipulation:
    def test_student_a_cannot_reach_course_b_resource(self, student_client, student, other_student, admin, admin_client, course, rid):
        other = Course.objects.create(title="Other", slug="other", status="published", created_by=admin)
        other_rid = upload(admin_client, other, data=make_pdf_bytes()).json()["data"]["id"]
        admin_client.post(f"/api/admin/course/resources/{other_rid}/validate/")
        admin_client.post(f"/api/admin/course/resources/{other_rid}/publish/")
        CourseAccess.objects.create(student=student, course=course, status="active")  # access to course A only
        CourseAccess.objects.create(student=other_student, course=other, status="active")
        assert pages(student_client, rid).status_code == 200
        assert pages(student_client, other_rid).status_code == 403
        assert student_client.get(f"/api/student/viewing/courses/{other.id}/resources/").status_code == 403
        assert student_client.get(f"/api/student/course/{other.id}/").json()["data"]["resources"] == []

    def test_student_cannot_use_another_students_access_record(self, student_client, other_student, course):
        theirs = CourseAccess.objects.create(student=other_student, course=course, status="active")
        assert student_client.get(f"/api/student/access/{theirs.id}/").status_code == 404
        assert student_client.patch(f"/api/admin/students/access/{theirs.id}/", {"action": "revoke"}, format="json").status_code == 403


class TestAdminPdfLifecycle:
    def test_upload_update_replace_publish_archive_with_audit_and_student_denial(self, admin_client, student_client, admin, course):
        client = APIClient()
        file = lambda: {"course": str(course.id), "title": "Notes", "file": __import__("django").core.files.uploadedfile.SimpleUploadedFile("n.pdf", make_pdf_bytes(), "application/pdf")}
        assert client.post("/api/admin/course/resources/", file(), format="multipart").status_code == 401
        assert student_client.post("/api/admin/course/resources/", file(), format="multipart").status_code == 403
        up = admin_client.post("/api/admin/course/resources/", file(), format="multipart")
        assert up.status_code == 201
        rid = up.json()["data"]["id"]
        base = f"/api/admin/course/resources/{rid}/"
        assert admin_client.patch(base, {"title": "Renamed"}, format="json").status_code == 200
        replace = admin_client.post(base + "replace/", {"file": file()["file"]}, format="multipart")
        assert replace.status_code == 200
        assert admin_client.post(base + "validate/").status_code == 200
        assert admin_client.post(base + "publish/").status_code == 200
        assert admin_client.post(base + "archive/").status_code == 200
        assert Resource.objects.get(pk=rid).status == "archived"
        for action in ("resource.uploaded", "resource.updated", "resource.replaced", "resource.published", "resource.archived"):
            event = AuditEvent.objects.filter(action=action, target_id=rid).first()
            assert event is not None and event.actor_id == admin.id, action
        for method, url in (("patch", base), ("post", base + "replace/"), ("post", base + "publish/"), ("post", base + "archive/"), ("delete", base)):
            assert getattr(student_client, method)(url, {}, format="json").status_code == 403
        assert json.dumps(Resource.objects.get(pk=rid).title) == '"Renamed"'
