import io
import os

import pypdfium2 as pdfium
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from audit.models import AuditEvent
from courses.models import Course
from resources.models import Resource
from resources.storage import get_private_storage

pytestmark = pytest.mark.django_db


def make_pdf_bytes(pages=2):
    document = pdfium.PdfDocument.new()
    for _ in range(pages):
        document.new_page(200, 300)
    buffer = io.BytesIO()
    document.save(buffer)
    document.close()
    return buffer.getvalue()


@pytest.fixture
def course(admin):
    return Course.objects.create(title="Chem", slug="chem", status="published", created_by=admin)


def upload(client, course, data=None, name="notes.pdf", content_type="application/pdf", **extra):
    payload = {"course": str(course.id), "title": "Notes", "file": SimpleUploadedFile(name, make_pdf_bytes() if data is None else data, content_type)}
    payload.update(extra)
    return client.post("/api/admin/course/resources/", payload, format="multipart")


class TestUploadValidation:
    def test_valid_upload(self, admin_client, course):
        res = upload(admin_client, course)
        body = res.json()["data"]
        assert res.status_code == 201
        assert body["status"] == "draft" and body["page_count"] == 2 and body["original_filename"] == "notes.pdf"
        assert "storage_key" not in body
        stored = Resource.objects.get(pk=body["id"])
        assert get_private_storage().exists(stored.storage_key)
        assert AuditEvent.objects.filter(action="resource.uploaded").exists()

    def test_rejects_wrong_extension(self, admin_client, course):
        res = upload(admin_client, course, name="notes.txt")
        assert res.status_code == 400 and res.json()["error"]["code"] == "INVALID_PDF"

    def test_rejects_fake_pdf_with_pdf_extension(self, admin_client, course):
        res = upload(admin_client, course, data=b"MZ\x90\x00 not really a pdf" * 10)
        assert res.status_code == 400 and res.json()["error"]["code"] == "INVALID_PDF"
        assert Resource.objects.count() == 0

    def test_rejects_wrong_declared_mime(self, admin_client, course):
        res = upload(admin_client, course, content_type="image/png")
        assert res.status_code == 400

    def test_rejects_truncated_pdf(self, admin_client, course):
        res = upload(admin_client, course, data=make_pdf_bytes()[:-3000] if len(make_pdf_bytes()) > 3500 else b"%PDF-1.4\n1 0 obj\n")
        assert res.status_code == 400

    def test_rejects_corrupt_body_with_valid_markers(self, admin_client, course):
        res = upload(admin_client, course, data=b"%PDF-1.4\ngarbage garbage\n%%EOF\n")
        assert res.status_code == 400 and res.json()["error"]["code"] == "INVALID_PDF"

    def test_rejects_empty_file(self, admin_client, course):
        res = upload(admin_client, course, data=b"")
        assert res.status_code == 400

    def test_rejects_oversized_file(self, admin_client, course, settings):
        settings.RESOURCE_MAX_BYTES = 100
        res = upload(admin_client, course)
        assert res.status_code == 413 and res.json()["error"]["code"] == "FILE_TOO_LARGE"

    def test_rejects_too_many_pages(self, admin_client, course, settings):
        settings.RESOURCE_MAX_PAGES = 1
        res = upload(admin_client, course)
        assert res.status_code == 400

    def test_path_traversal_filename_is_sanitised(self, admin_client, course):
        res = upload(admin_client, course, name="../../etc/evil.pdf")
        assert res.status_code == 201 and res.json()["data"]["original_filename"] == "evil.pdf"
        key = Resource.objects.get().storage_key
        assert key.startswith("resources/") and ".." not in key

    def test_archived_course_rejected(self, admin_client, course):
        course.status = "archived"
        course.save()
        assert upload(admin_client, course).status_code == 409

    def test_unknown_course_and_missing_file(self, admin_client, course):
        bad = admin_client.post(
            "/api/admin/course/resources/", {"course": "00000000-0000-0000-0000-000000000000", "title": "x"}, format="multipart"
        )
        assert bad.status_code == 400

    def test_student_and_anonymous_cannot_upload(self, student_client, client, course):
        assert upload(student_client, course).status_code == 403
        assert upload(APIClient(), course).status_code == 401


class TestLifecycle:
    def test_validate_publish_archive(self, admin_client, course):
        rid = upload(admin_client, course).json()["data"]["id"]
        early = admin_client.post(f"/api/admin/course/resources/{rid}/publish/")
        assert early.status_code == 409 and early.json()["error"]["code"] == "RESOURCE_NOT_VALIDATED"
        val = admin_client.post(f"/api/admin/course/resources/{rid}/validate/")
        assert val.status_code == 200 and val.json()["data"]["status"] == "validated"
        pub = admin_client.post(f"/api/admin/course/resources/{rid}/publish/")
        assert pub.json()["data"]["status"] == "published" and pub.json()["data"]["published_at"]
        assert admin_client.post(f"/api/admin/course/resources/{rid}/publish/").status_code == 409
        assert admin_client.post(f"/api/admin/course/resources/{rid}/validate/").status_code == 409
        arch = admin_client.post(f"/api/admin/course/resources/{rid}/archive/")
        assert arch.json()["data"]["status"] == "archived"
        actions = set(AuditEvent.objects.values_list("action", flat=True))
        assert {"resource.validated", "resource.published", "resource.archived"} <= actions

    def test_validate_detects_tampered_storage(self, admin_client, course):
        rid = upload(admin_client, course).json()["data"]["id"]
        key = Resource.objects.get(pk=rid).storage_key
        path = get_private_storage().path(key)
        with open(path, "wb") as handle:
            handle.write(make_pdf_bytes(pages=5))  # valid PDF, different bytes
        res = admin_client.post(f"/api/admin/course/resources/{rid}/validate/")
        assert res.status_code == 400 and "checksum" in res.json()["error"]["message"]
        assert Resource.objects.get(pk=rid).status == "draft"

    def test_validate_detects_missing_file(self, admin_client, course):
        rid = upload(admin_client, course).json()["data"]["id"]
        os.remove(get_private_storage().path(Resource.objects.get(pk=rid).storage_key))
        assert admin_client.post(f"/api/admin/course/resources/{rid}/validate/").status_code == 500

    def test_patch_and_filters(self, admin_client, course):
        rid = upload(admin_client, course).json()["data"]["id"]
        res = admin_client.patch(f"/api/admin/course/resources/{rid}/", {"title": "Renamed"}, format="json")
        assert res.json()["data"]["title"] == "Renamed"
        assert admin_client.get(f"/api/admin/course/resources/?course={course.id}&status=DRAFT").json()["meta"]["count"] == 1
        assert admin_client.get("/api/admin/course/resources/?status=published").json()["meta"]["count"] == 0
        assert admin_client.get(f"/api/admin/course/resources/{rid}/").status_code == 200

    def test_delete_removes_file_after_commit(self, admin_client, course, django_capture_on_commit_callbacks):
        rid = upload(admin_client, course).json()["data"]["id"]
        key = Resource.objects.get(pk=rid).storage_key
        with django_capture_on_commit_callbacks(execute=True):
            assert admin_client.delete(f"/api/admin/course/resources/{rid}/").status_code == 200
        assert not get_private_storage().exists(key)
        assert not Resource.objects.filter(pk=rid).exists()
        assert AuditEvent.objects.filter(action="resource.deleted").exists()

    def test_cannot_delete_course_with_resources(self, admin_client, course):
        upload(admin_client, course)
        res = admin_client.delete(f"/api/admin/course/{course.id}/")
        assert res.status_code == 409

    def test_students_cannot_manage(self, student_client, admin_client, course):
        rid = upload(admin_client, course).json()["data"]["id"]
        for method, url in [
            ("get", "/api/admin/course/resources/"),
            ("get", f"/api/admin/course/resources/{rid}/"),
            ("patch", f"/api/admin/course/resources/{rid}/"),
            ("delete", f"/api/admin/course/resources/{rid}/"),
            ("post", f"/api/admin/course/resources/{rid}/validate/"),
            ("post", f"/api/admin/course/resources/{rid}/publish/"),
            ("post", f"/api/admin/course/resources/{rid}/archive/"),
        ]:
            assert getattr(student_client, method)(url).status_code == 403, (method, url)

    def test_db_constraints(self, course):
        from django.db import IntegrityError, transaction

        with pytest.raises(IntegrityError), transaction.atomic():
            Resource.objects.create(
                course=course, title="x", storage_key="k", original_filename="x.pdf", file_size=0, page_count=1, sha256="a"
            )
