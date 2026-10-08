import uuid
from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from access import services as access_services
from access.models import CourseAccess
from audit.models import AuditEvent
from courses.models import Course

from .conftest import auth_client, login_student

pytestmark = pytest.mark.django_db


def make_course(admin=None, **kw):
    defaults = dict(
        title="Algebra", slug=f"algebra-{uuid.uuid4().hex[:8]}", status="published",
        access_mode="manual_approval", created_by=admin,
    )
    defaults.update(kw)
    return Course.objects.create(**defaults)


def client_for(user):
    c = APIClient()
    tokens = login_student(c, user.email).json()["data"]["tokens"]
    return auth_client(c, tokens)


class TestCourseCRUD:
    def payload(self, **kw):
        base = {"title": "Physics", "description": "d", "access_mode": "immediate"}
        base.update(kw)
        return base

    def test_admin_creates_updates_deletes(self, admin_client):
        res = admin_client.post("/api/admin/course/", self.payload(), format="json")
        assert res.status_code == 201
        assert res.json()["data"]["status"] == "draft" and res.json()["data"]["slug"] == "physics"
        cid = res.json()["data"]["id"]
        up = admin_client.patch(f"/api/admin/course/{cid}/", {"title": "Physics II"}, format="json")
        assert up.status_code == 200 and up.json()["data"]["title"] == "Physics II"
        assert admin_client.delete(f"/api/admin/course/{cid}/").status_code == 200
        assert admin_client.get(f"/api/admin/course/{cid}/").status_code == 404
        actions = set(AuditEvent.objects.values_list("action", flat=True))
        assert {"course.created", "course.updated", "course.deleted"} <= actions

    def test_student_cannot_write(self, student_client):
        assert student_client.post("/api/admin/course/", self.payload(), format="json").status_code == 403

    def test_student_cannot_update_or_delete(self, student_client, admin):
        c = make_course(admin)
        assert student_client.patch(f"/api/admin/course/{c.id}/", {"title": "x"}, format="json").status_code == 403
        assert student_client.delete(f"/api/admin/course/{c.id}/").status_code == 403

    def test_unauthenticated(self, client):
        assert client.get("/api/student/course/").status_code == 401

    def test_students_only_see_published(self, student_client, admin):
        make_course(admin, title="Live")
        draft = make_course(admin, title="Hidden", status="draft")
        body = student_client.get("/api/student/course/").json()
        assert [c["title"] for c in body["data"]] == ["Live"]
        assert student_client.get(f"/api/student/course/{draft.id}/").status_code == 404

    def test_admin_sees_drafts_and_filters(self, admin_client, admin):
        make_course(admin, title="Live")
        make_course(admin, title="Hidden", status="draft")
        assert admin_client.get("/api/admin/course/").json()["meta"]["count"] == 2
        assert admin_client.get("/api/admin/course/?status=draft").json()["meta"]["count"] == 1
        assert admin_client.get("/api/admin/course/?status=DRAFT").json()["meta"]["count"] == 1

    def test_slug_unique_and_stable(self, admin_client):
        a = admin_client.post("/api/admin/course/", self.payload(), format="json").json()["data"]
        b = admin_client.post("/api/admin/course/", self.payload(), format="json").json()["data"]
        assert a["slug"] == "physics" and b["slug"].startswith("physics-") and a["slug"] != b["slug"]
        renamed = admin_client.patch(f"/api/admin/course/{a['id']}/", {"title": "Other"}, format="json")
        assert renamed.json()["data"]["slug"] == "physics"

    def test_status_not_writable_via_patch(self, admin_client, admin):
        c = make_course(admin, status="draft")
        admin_client.patch(f"/api/admin/course/{c.id}/", {"status": "published"}, format="json")
        c.refresh_from_db()
        assert c.status == "draft"

    def test_publish_and_archive_workflow(self, admin_client, student_client, admin):
        c = make_course(admin, status="draft")
        assert student_client.get(f"/api/student/course/{c.id}/").status_code == 404
        pub = admin_client.post(f"/api/admin/course/{c.id}/publish/")
        assert pub.status_code == 200 and pub.json()["data"]["status"] == "published"
        assert pub.json()["data"]["published_at"] is not None
        assert admin_client.post(f"/api/admin/course/{c.id}/publish/").status_code == 409
        assert student_client.get(f"/api/student/course/{c.id}/").status_code == 200
        arch = admin_client.post(f"/api/admin/course/{c.id}/archive/")
        assert arch.json()["data"]["status"] == "archived"
        assert admin_client.post(f"/api/admin/course/{c.id}/archive/").status_code == 409
        assert student_client.get(f"/api/student/course/{c.id}/").status_code == 404
        actions = set(AuditEvent.objects.values_list("action", flat=True))
        assert {"course.published", "course.archived"} <= actions

    def test_student_cannot_publish(self, student_client, admin):
        c = make_course(admin, status="draft")
        assert student_client.post(f"/api/admin/course/{c.id}/publish/").status_code == 403

    def test_archived_course_gives_no_new_access(self, student_client, admin):
        c = make_course(admin, status="archived", access_mode="immediate")
        res = student_client.post("/api/student/access/", {"course": str(c.id)}, format="json")
        assert res.status_code == 404

    def test_paid_course_requires_price(self, admin_client):
        res = admin_client.post("/api/admin/course/", self.payload(access_mode="payment_required"), format="json")
        assert res.status_code == 400 and "price_amount" in res.json()["error"]["details"]["fields"]
        ok = admin_client.post(
            "/api/admin/course/", self.payload(access_mode="payment_required", price_amount="49.00"), format="json"
        )
        assert ok.status_code == 201

    def test_price_on_free_course_rejected(self, admin_client):
        res = admin_client.post("/api/admin/course/", self.payload(price_amount="5.00"), format="json")
        assert res.status_code == 400

    def test_db_constraint_on_paid_price(self, admin):
        with pytest.raises(IntegrityError), transaction.atomic():
            Course.objects.create(title="Bad", access_mode="payment_required", price_amount=None)

    def test_invalid_input(self, admin_client):
        assert admin_client.post("/api/admin/course/", {"title": ""}, format="json").status_code == 400
        assert admin_client.post("/api/admin/course/", self.payload(currency="DOLLARS"), format="json").status_code == 400

    def test_cannot_delete_course_with_access(self, admin_client, admin, student):
        c = make_course(admin, access_mode="immediate")
        access_services.request_course_access(student=student, course=c)
        res = admin_client.delete(f"/api/admin/course/{c.id}/")
        assert res.status_code == 409 and res.json()["error"]["code"] == "COURSE_IN_USE"
        assert Course.objects.filter(pk=c.pk).exists()

    def test_changing_to_free_clears_price(self, admin_client, admin):
        c = make_course(admin, access_mode="payment_required", price_amount="10.00")
        res = admin_client.patch(f"/api/admin/course/{c.id}/", {"access_mode": "immediate"}, format="json")
        assert res.status_code == 200 and res.json()["data"]["price_amount"] is None

    def test_list_includes_access_state_without_n_plus_one(self, student_client, student, admin, django_assert_max_num_queries):
        for i in range(5):
            make_course(admin, title=f"C{i}")
        with django_assert_max_num_queries(6):
            body = student_client.get("/api/student/course/").json()
        assert all(c["access"]["state"] == "requestable" for c in body["data"])


class TestEvaluateAccess:
    def test_states(self, student, admin):
        manual = make_course(admin)
        paid = make_course(admin, access_mode="payment_required", price_amount="10.00")
        draft = make_course(admin, status="draft")
        ev = access_services.evaluate_access
        assert ev(student, manual).state == "requestable"
        assert ev(student, paid).state == "requestable"  # payment starts only after an admin approves the request
        assert ev(student, draft).state == "unavailable"

    def test_grant_expiry_and_revocation(self, student, admin):
        c = make_course(admin, access_duration_days=30)
        rec = access_services.grant_course_access(student=student, course=c, source="admin_approval", actor=admin)
        assert access_services.evaluate_access(student, c).allowed
        CourseAccess.objects.filter(pk=rec.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        assert access_services.evaluate_access(student, c).state == "expired"
        CourseAccess.objects.filter(pk=rec.pk).update(status="revoked")
        assert access_services.evaluate_access(student, c).state == "revoked"

    def test_suspended_student_denied(self, student, admin):
        c = make_course(admin)
        access_services.grant_course_access(student=student, course=c, source="admin_approval", actor=admin)
        student.status = "suspended"
        assert access_services.evaluate_access(student, c).allowed is False

    def test_admin_role_never_allowed_as_student(self, admin):
        assert access_services.evaluate_access(admin, make_course(admin)).allowed is False


class TestAccessAPI:
    def test_immediate_access(self, student_client, admin):
        c = make_course(admin, access_mode="immediate")
        res = student_client.post("/api/student/access/", {"course": str(c.id)}, format="json")
        assert res.status_code == 201 and res.json()["data"]["state"] == "granted"

    def test_manual_approval_flow(self, student_client, admin_client, admin, student):
        c = make_course(admin)
        res = student_client.post("/api/student/access/", {"course": str(c.id)}, format="json")
        assert res.json()["data"]["state"] == "pending"
        aid = res.json()["data"]["id"]
        # idempotent re-request
        again = student_client.post("/api/student/access/", {"course": str(c.id)}, format="json")
        assert again.json()["data"]["id"] == aid and CourseAccess.objects.count() == 1
        approve = admin_client.patch(f"/api/admin/students/access/{aid}/", {"action": "approve"}, format="json")
        assert approve.status_code == 200 and approve.json()["data"]["state"] == "granted"
        assert AuditEvent.objects.filter(action="access.granted").exists()
        revoke = admin_client.patch(f"/api/admin/students/access/{aid}/", {"action": "revoke"}, format="json")
        assert revoke.json()["data"]["state"] == "revoked"
        retry = student_client.post("/api/student/access/", {"course": str(c.id)}, format="json")
        assert retry.status_code == 403 and retry.json()["error"]["code"] == "ACCESS_REVOKED"

    def test_reject_then_rerequest(self, student_client, admin_client, admin):
        c = make_course(admin)
        aid = student_client.post("/api/student/access/", {"course": str(c.id)}, format="json").json()["data"]["id"]
        assert admin_client.patch(f"/api/admin/students/access/{aid}/", {"action": "reject", "note": "no"}, format="json").status_code == 200
        res = student_client.post("/api/student/access/", {"course": str(c.id)}, format="json")
        assert res.status_code == 201 and res.json()["data"]["state"] == "pending"

    def test_invalid_transitions(self, student_client, admin_client, admin):
        c = make_course(admin)
        aid = student_client.post("/api/student/access/", {"course": str(c.id)}, format="json").json()["data"]["id"]
        res = admin_client.patch(f"/api/admin/students/access/{aid}/", {"action": "revoke"}, format="json")
        assert res.status_code == 409 and res.json()["error"]["code"] == "INVALID_STATE"
        assert admin_client.patch(f"/api/admin/students/access/{aid}/", {"action": "explode"}, format="json").status_code == 400

    def test_paid_course_cannot_be_requested_for_free(self, student_client, admin):
        c = make_course(admin, access_mode="payment_required", price_amount="10.00")
        res = student_client.post("/api/student/access/", {"course": str(c.id)}, format="json")
        assert res.status_code == 201 and res.json()["data"]["status"] == "pending"  # a request for the admin, not access
        record = CourseAccess.objects.get()
        assert record.status == "pending" and record.payment_required is False

    def test_cannot_request_draft_or_missing_course(self, student_client, admin):
        d = make_course(admin, status="draft")
        assert student_client.post("/api/student/access/", {"course": str(d.id)}, format="json").status_code == 404
        bad = student_client.post("/api/student/access/", {"course": "nope"}, format="json")
        assert bad.status_code == 400

    def test_student_cannot_decide(self, student_client, admin, student):
        c = make_course(admin)
        rec = CourseAccess.objects.create(student=student, course=c)
        assert student_client.patch(f"/api/admin/students/access/{rec.id}/", {"action": "approve"}, format="json").status_code == 403

    def test_idor_on_access_records(self, student_client, other_student, admin):
        c = make_course(admin)
        theirs = CourseAccess.objects.create(student=other_student, course=c)
        assert student_client.get(f"/api/student/access/{theirs.id}/").status_code == 404
        assert student_client.get("/api/student/access/").json()["meta"]["count"] == 0

    def test_student_lists_only_own(self, student_client, student, other_student, admin):
        c = make_course(admin)
        CourseAccess.objects.create(student=student, course=c)
        CourseAccess.objects.create(student=other_student, course=c)
        assert student_client.get("/api/student/access/").json()["meta"]["count"] == 1

    def test_admin_lists_and_filters(self, admin_client, student, other_student, admin):
        c = make_course(admin)
        CourseAccess.objects.create(student=student, course=c)
        CourseAccess.objects.create(student=other_student, course=c, status="active")
        assert admin_client.get("/api/admin/students/access/").json()["meta"]["count"] == 2
        assert admin_client.get("/api/admin/students/access/?status=pending").json()["meta"]["count"] == 1

    def test_admin_grant_and_validation(self, admin_client, student, admin):
        c = make_course(admin)
        res = admin_client.post("/api/admin/students/access/grant/", {"course": str(c.id), "student": str(student.id)}, format="json")
        assert res.status_code == 201 and res.json()["data"]["source"] == "admin_approval"
        bad = admin_client.post("/api/admin/students/access/grant/", {"course": str(c.id), "student": str(admin.id)}, format="json")
        assert bad.status_code == 400

    def test_student_cannot_grant(self, student_client, student, admin):
        c = make_course(admin)
        res = student_client.post("/api/admin/students/access/grant/", {"course": str(c.id), "student": str(student.id)}, format="json")
        assert res.status_code == 403

    def test_unique_constraint(self, student, admin):
        c = make_course(admin)
        CourseAccess.objects.create(student=student, course=c)
        with pytest.raises(IntegrityError), transaction.atomic():
            CourseAccess.objects.create(student=student, course=c)

    def test_admin_cannot_request_access(self, admin_client, admin):
        c = make_course(admin)
        assert admin_client.post("/api/student/access/", {"course": str(c.id)}, format="json").status_code == 403
