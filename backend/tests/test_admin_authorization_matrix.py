"""Only admins manage courses, resources and approvals. Students never can; anonymous callers are not even authenticated.

The matrix runs every operation three times (anonymous, student, admin) on freshly created data, so a denied call can be
shown to change nothing and an allowed call to leave exactly the expected state and audit event.
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from access.models import CourseAccess
from access.services import evaluate_access
from accounts.models import User
from audit.models import AuditEvent
from courses.models import Course
from resources.models import Resource

from .conftest import PASSWORD
from .test_resources import make_pdf_bytes

pytestmark = pytest.mark.django_db
NIL = "00000000-0000-0000-0000-000000000000"


def j(client, method, url, data=None):
    return getattr(client, method)(url, data if data is not None else {}, format="json")


def new_state(owner):
    """Fresh course (draft, deletable), a published course with a pending access request, and a pending registration."""
    n = User.objects.count()
    student = User.objects.create_user(f"matrix{n}@example.com", PASSWORD, full_name="Matrix Student", status="active")
    draft = Course.objects.create(title=f"Draft {n}", slug=f"draft-{n}", status="draft", created_by=owner)
    live = Course.objects.create(title=f"Live {n}", slug=f"live-{n}", status="published", access_mode="manual_approval", created_by=owner)
    request = CourseAccess.objects.create(student=student, course=live, status="pending")
    pending_user = User.objects.create_user(f"pending{n}@example.com", PASSWORD, full_name="Pending Person", status="pending")
    return {"student": student, "draft": draft, "live": live, "request": request, "pending": pending_user}


def upload_pdf(client, course):
    payload = {"course": str(course.id), "title": "Notes", "file": SimpleUploadedFile("notes.pdf", make_pdf_bytes(), "application/pdf")}
    return client.post("/api/admin/course/resources/", payload, format="multipart")


# name -> (callable(client, state) -> response, status expected for an admin)
OPERATIONS = {
    "create course": (lambda c, s: j(c, "post", "/api/admin/course/", {"title": "New Course", "access_mode": "manual_approval"}), 201),
    "update course (PATCH)": (lambda c, s: j(c, "patch", f"/api/admin/course/{s['draft'].id}/", {"title": "Edited"}), 200),
    "replace course (PUT)": (lambda c, s: j(c, "put", f"/api/admin/course/{s['draft'].id}/", {"title": "Replaced"}), 200),
    "publish course": (lambda c, s: j(c, "post", f"/api/admin/course/{s['draft'].id}/publish/"), 200),
    "unpublish course": (lambda c, s: j(c, "post", f"/api/admin/course/{s['live'].id}/unpublish/"), 200),
    "archive course": (lambda c, s: j(c, "post", f"/api/admin/course/{s['live'].id}/archive/"), 200),
    "delete course": (lambda c, s: c.delete(f"/api/admin/course/{s['draft'].id}/"), 200),
    "upload course PDF": (lambda c, s: upload_pdf(c, s["live"]), 201),
    "approve course access": (lambda c, s: j(c, "patch", f"/api/admin/students/access/{s['request'].id}/", {"action": "approve"}), 200),
    "reject course access": (lambda c, s: j(c, "patch", f"/api/admin/students/access/{s['request'].id}/", {"action": "reject"}), 200),
    "grant course access": (lambda c, s: j(c, "post", "/api/admin/students/access/grant/", {"course": str(s["live"].id), "student": str(s["student"].id)}), 201),
    "access decision": (lambda c, s: j(c, "post", f"/api/admin/students/{s['student'].id}/decision/", {"decision": "immediate", "course": str(s["live"].id)}), 200),
    "approve registration": (lambda c, s: c.post(f"/api/admin/students/approval-requests/{s['pending'].id}/approve/"), 200),
    "reject registration": (lambda c, s: j(c, "post", f"/api/admin/students/approval-requests/{s['pending'].id}/reject/", {"reason": "no"}), 200),
    "list pending access requests": (lambda c, s: c.get("/api/admin/students/access/?status=pending"), 200),
    "list pending registrations": (lambda c, s: c.get("/api/admin/students/approval-requests/"), 200),
    "admin course list": (lambda c, s: c.get("/api/admin/course/"), 200),
    "admin reports": (lambda c, s: c.get("/api/admin/reports/dashboard/"), 200),
    "admin audit logs": (lambda c, s: c.get("/api/admin/audit-logs/"), 200),
}


@pytest.fixture
def clients(admin_client, student_client):
    return {"anonymous": APIClient(), "student": student_client, "admin": admin_client}


class TestAuthorizationMatrix:
    @pytest.mark.parametrize("name", OPERATIONS)
    def test_anonymous_gets_401(self, name, admin):
        call, _ = OPERATIONS[name]
        res = call(APIClient(), new_state(admin))
        assert res.status_code == 401 and res.json()["error"]["code"] == "NOT_AUTHENTICATED"

    @pytest.mark.parametrize("name", OPERATIONS)
    def test_student_gets_403_and_nothing_changes(self, name, student_client, admin):
        call, _ = OPERATIONS[name]
        state = new_state(admin)
        before = (Course.objects.count(), Resource.objects.count(), AuditEvent.objects.count(),
                  list(CourseAccess.objects.values_list("id", "status")), list(User.objects.values_list("id", "status")),
                  list(Course.objects.values_list("id", "title", "status")))
        res = call(student_client, state)
        assert res.status_code == 403 and res.json()["error"]["code"] == "PERMISSION_DENIED", res.content
        after = (Course.objects.count(), Resource.objects.count(), AuditEvent.objects.count(),
                 list(CourseAccess.objects.values_list("id", "status")), list(User.objects.values_list("id", "status")),
                 list(Course.objects.values_list("id", "title", "status")))
        assert before == after  # no data changed and no audit event was written

    @pytest.mark.parametrize("name", OPERATIONS)
    def test_admin_is_allowed(self, name, admin_client, admin):
        call, expected = OPERATIONS[name]
        res = call(admin_client, new_state(admin))
        assert res.status_code == expected, res.content
        assert res.json()["success"] is True

    def test_student_side_reads_for_the_matrix_rows_that_exist_for_students(self, clients, admin):
        # "view allowed courses" / "view own access status" are student-portal reads: admins are walled off from them
        for url in ("/api/student/course/", "/api/student/courses/", "/api/student/access/"):
            assert clients["anonymous"].get(url).status_code == 401
            assert clients["student"].get(url).status_code == 200
            assert clients["admin"].get(url).status_code == 403


class TestAuditTrailNamesTheAdmin:
    def actor_of(self, action):
        event = AuditEvent.objects.filter(action=action).order_by("-created_at").first()
        assert event is not None, action
        return event

    def test_course_and_resource_operations(self, admin_client, admin):
        created = j(admin_client, "post", "/api/admin/course/", {"title": "Audited", "access_mode": "manual_approval"}).json()["data"]
        url = f"/api/admin/course/{created['id']}/"
        j(admin_client, "patch", url, {"title": "Audited 2"})
        j(admin_client, "post", url + "publish/")
        rid = upload_pdf(admin_client, Course.objects.get(pk=created["id"])).json()["data"]["id"]
        j(admin_client, "patch", f"/api/admin/course/resources/{rid}/", {"title": "Renamed"})
        j(admin_client, "post", url + "archive/")
        other = Course.objects.create(title="Gone", slug="gone", status="draft")
        admin_client.delete(f"/api/admin/course/{other.id}/")
        for action in ("course.created", "course.updated", "course.published", "course.archived", "course.deleted",
                       "resource.uploaded", "resource.updated"):
            event = self.actor_of(action)
            assert event.actor_id == admin.id and event.actor_email == admin.email, action
        assert self.actor_of("course.created").target_id == created["id"]
        assert "title" in self.actor_of("course.updated").metadata["changed_fields"]

    def test_approve_and_reject_name_the_admin(self, admin_client, admin):
        approve, reject = new_state(admin), new_state(admin)
        j(admin_client, "patch", f"/api/admin/students/access/{approve['request'].id}/", {"action": "approve"})
        j(admin_client, "patch", f"/api/admin/students/access/{reject['request'].id}/", {"action": "reject"})
        granted, rejected = self.actor_of("access.granted"), self.actor_of("access.rejected")
        assert granted.actor_id == admin.id and granted.target_id == str(approve["request"].id)
        assert rejected.actor_id == admin.id and rejected.target_id == str(reject["request"].id)
        j(admin_client, "post", f"/api/admin/students/approval-requests/{approve['pending'].id}/approve/")
        j(admin_client, "post", f"/api/admin/students/approval-requests/{reject['pending'].id}/reject/", {"reason": "x"})
        assert self.actor_of("user.approved").actor_id == admin.id and self.actor_of("user.rejected").actor_id == admin.id

    def test_a_denied_attempt_leaves_no_audit_event(self, student_client, admin):
        state = new_state(admin)
        before = AuditEvent.objects.count()
        j(student_client, "patch", f"/api/admin/students/access/{state['request'].id}/", {"action": "approve"})
        j(student_client, "post", "/api/admin/course/", {"title": "Sneaky"})
        assert AuditEvent.objects.count() == before


class TestRequestThenApproveWorkflow:
    def test_full_cycle_with_the_central_access_check(self, admin_client, admin, student, student_client):
        course = Course.objects.create(title="Algebra", slug="algebra", status="published", access_mode="manual_approval", created_by=admin)
        # 1. the student asks; the request is stored as pending and access is still denied
        res = j(student_client, "post", "/api/student/access/", {"course": str(course.id)})
        assert res.status_code == 201 and res.json()["data"]["status"] == "pending"
        record = CourseAccess.objects.get(student=student, course=course)
        assert evaluate_access(student, course).allowed is False
        assert student_client.get(f"/api/student/viewing/courses/{course.id}/resources/").status_code == 403
        # 2. the admin sees it as pending
        pending = admin_client.get("/api/admin/students/access/?status=pending").json()["data"]
        assert [r["id"] for r in pending] == [str(record.id)]
        # 3. the admin approves; the central evaluator now allows it
        assert j(admin_client, "patch", f"/api/admin/students/access/{record.id}/", {"action": "approve"}).status_code == 200
        record.refresh_from_db()
        assert record.status == "active" and record.decided_by_id == admin.id
        assert evaluate_access(student, course).allowed is True
        # 4. the student sees the new status and may now use the viewer
        mine = student_client.get(f"/api/student/access/{record.id}/").json()["data"]
        assert mine["status"] == "active" and mine["state"] == "granted"
        assert student_client.get(f"/api/student/viewing/courses/{course.id}/resources/").status_code == 200
        # 5. the trail
        actions = list(AuditEvent.objects.filter(target_id=str(record.id)).values_list("action", flat=True))
        assert "access.requested" in actions and "access.granted" in actions

    def test_rejection_is_visible_to_the_student_and_denies_access(self, admin_client, admin, student, student_client):
        course = Course.objects.create(title="Biology", slug="biology", status="published", access_mode="manual_approval")
        record = CourseAccess.objects.get(pk=j(student_client, "post", "/api/student/access/", {"course": str(course.id)}).json()["data"]["id"])
        j(admin_client, "patch", f"/api/admin/students/access/{record.id}/", {"action": "reject", "note": "full"})
        mine = student_client.get(f"/api/student/access/{record.id}/").json()["data"]
        assert mine["status"] == "rejected" and mine["state"] == "rejected"
        assert evaluate_access(student, course).allowed is False
        assert student_client.get(f"/api/student/viewing/courses/{course.id}/resources/").status_code == 403

    def test_approving_never_bypasses_the_evaluator(self, admin_client, admin, student):
        draft = Course.objects.create(title="Hidden", slug="hidden", status="draft")
        record = CourseAccess.objects.create(student=student, course=draft, status="pending")
        res = j(admin_client, "patch", f"/api/admin/students/access/{record.id}/", {"action": "approve"})
        assert res.status_code == 409 and res.json()["error"]["code"] == "COURSE_UNAVAILABLE"  # unpublished course: no usable access
        record.refresh_from_db()
        assert record.status == "pending" and evaluate_access(student, draft).allowed is False


class TestStudentCannotManipulateIds:
    def test_cannot_approve_their_own_request(self, student_client, student, admin):
        course = Course.objects.create(title="C", slug="c", status="published", access_mode="manual_approval")
        record = CourseAccess.objects.create(student=student, course=course, status="pending")
        res = j(student_client, "patch", f"/api/admin/students/access/{record.id}/", {"action": "approve"})
        assert res.status_code == 403
        record.refresh_from_db()
        assert record.status == "pending"

    def test_cannot_grant_access_to_themselves_or_others(self, student_client, student, other_student):
        course = Course.objects.create(title="C", slug="c", status="published")
        for target in (student, other_student):
            res = j(student_client, "post", "/api/admin/students/access/grant/", {"course": str(course.id), "student": str(target.id)})
            assert res.status_code == 403
        assert not CourseAccess.objects.exists()

    def test_the_request_endpoint_ignores_a_student_id_in_the_body(self, student_client, student, other_student):
        course = Course.objects.create(title="C", slug="c", status="published", access_mode="manual_approval")
        res = j(student_client, "post", "/api/student/access/", {"course": str(course.id), "student": str(other_student.id), "student_id": str(other_student.id), "status": "active"})
        assert res.status_code == 201
        record = CourseAccess.objects.get()
        assert record.student_id == student.id and record.status == "pending"  # own request, still pending

    def test_cannot_read_or_change_another_students_access_by_id(self, student_client, other_student):
        course = Course.objects.create(title="C", slug="c", status="published")
        theirs = CourseAccess.objects.create(student=other_student, course=course, status="active")
        assert student_client.get(f"/api/student/access/{theirs.id}/").status_code == 404
        assert j(student_client, "patch", f"/api/admin/students/access/{theirs.id}/", {"action": "revoke"}).status_code == 403
        theirs.refresh_from_db()
        assert theirs.status == "active"

    def test_course_id_in_the_url_does_not_help(self, student_client):
        course = Course.objects.create(title="Other", slug="other", status="published")
        for method in ("get", "patch", "put", "delete"):
            assert j(student_client, method, f"/api/admin/course/{course.id}/", {"title": "x"}).status_code == 403
            assert j(student_client, method, f"/api/admin/course/{NIL}/", {"title": "x"}).status_code == 403  # even unknown ids: 403, not 404
        assert Course.objects.get(pk=course.pk).title == "Other"

    def test_cannot_decide_for_another_student(self, student_client, other_student):
        course = Course.objects.create(title="C", slug="c", status="published", access_mode="manual_approval")
        res = j(student_client, "post", f"/api/admin/students/{other_student.id}/decision/", {"decision": "immediate", "course": str(course.id)})
        assert res.status_code == 403 and not CourseAccess.objects.exists()


class TestResourcesStayAdminOnly:
    def test_students_cannot_touch_resources(self, student_client, admin_client, admin):
        course = Course.objects.create(title="C", slug="c", status="published", created_by=admin)
        rid = upload_pdf(admin_client, course).json()["data"]["id"]
        base = f"/api/admin/course/resources/{rid}/"
        assert upload_pdf(student_client, course).status_code == 403
        for method, url, body in (("patch", base, {"title": "x"}), ("delete", base, None), ("post", base + "publish/", None),
                                  ("post", base + "validate/", None), ("post", base + "archive/", None)):
            assert j(student_client, method, url, body).status_code == 403, (method, url)
        replace = student_client.post(base + "replace/", {"file": SimpleUploadedFile("n.pdf", make_pdf_bytes(), "application/pdf")}, format="multipart")
        assert replace.status_code == 403
        assert Resource.objects.get(pk=rid).title == "Notes" and Resource.objects.count() == 1

    def test_there_is_no_student_write_route_for_resources(self, student_client):
        for url in ("/api/student/course/resources/", "/api/student/viewing/resources/", "/api/student/resources/"):
            assert student_client.post(url, {}, format="json").status_code in (404, 405)

    def test_no_raw_file_url_is_exposed(self, student_client, student, admin_client, admin):
        course = Course.objects.create(title="C", slug="c", status="published", created_by=admin)
        rid = upload_pdf(admin_client, course).json()["data"]["id"]
        admin_client.post(f"/api/admin/course/resources/{rid}/validate/")
        admin_client.post(f"/api/admin/course/resources/{rid}/publish/")
        CourseAccess.objects.create(student=student, course=course, status="active")
        listing = student_client.get(f"/api/student/viewing/courses/{course.id}/resources/").content.decode()
        detail = student_client.get(f"/api/student/course/{course.id}/").content.decode()
        for body in (listing, detail):
            assert "storage_key" not in body and ".pdf" not in body and "/media/" not in body and "private_media" not in body


class TestRolesAreReadFromTheServer:
    def test_a_token_cannot_carry_its_own_role(self, student, student_client):
        # the role lives in the database: changing a student into an "admin" in a request body does nothing
        j(student_client, "patch", "/api/student/profile/", {"role": "admin", "is_staff": True, "full_name": "Hacker"})
        student.refresh_from_db()
        assert student.role == "student" and not student.is_staff
        assert j(student_client, "post", "/api/admin/course/", {"title": "Still no"}).status_code == 403

    def test_a_suspended_admin_loses_access_immediately(self, admin_client, admin):
        assert admin_client.get("/api/admin/course/").status_code == 200
        admin.status = "suspended"
        admin.save()
        assert admin_client.get("/api/admin/course/").status_code == 401
