import pytest
from django.core import mail
from rest_framework.test import APIClient

from courses.models import Course
from notifications import services as notifications
from notifications.models import Notification

from .conftest import register_via_api, PASSWORD

pytestmark = pytest.mark.django_db


def make(user, ntype="security", **kw):
    return Notification.objects.create(user=user, type=ntype, title="T", message="M", **kw)


class TestNotificationAPI:
    def test_list_own_with_unread_count(self, student_client, student, other_student):
        make(student)
        make(student, read_at="2026-01-01T00:00:00Z")
        make(other_student)
        res = student_client.get("/api/student/notifications/")
        body = res.json()
        assert res.status_code == 200 and body["meta"]["count"] == 2 and body["meta"]["unread_count"] == 1
        assert student_client.get("/api/student/notifications/?unread=true").json()["meta"]["count"] == 1
        assert student_client.get("/api/student/notifications/?type=access_granted").json()["meta"]["count"] == 0

    def test_requires_authentication(self, client):
        assert client.get("/api/student/notifications/").status_code == 401
        assert client.post("/api/student/notifications/read-all/").status_code == 401

    def test_mark_read(self, student_client, student):
        n = make(student)
        res = student_client.post(f"/api/student/notifications/{n.id}/read/")
        assert res.status_code == 200 and res.json()["data"]["is_read"] is True
        n.refresh_from_db()
        assert n.read_at is not None
        again = student_client.post(f"/api/student/notifications/{n.id}/read/")
        assert again.status_code == 200

    def test_read_all_only_touches_own(self, student_client, student, other_student):
        make(student), make(student)
        theirs = make(other_student)
        res = student_client.post("/api/student/notifications/read-all/")
        assert res.json()["data"]["updated"] == 2
        theirs.refresh_from_db()
        assert theirs.read_at is None

    def test_delete(self, student_client, student):
        n = make(student)
        assert student_client.delete(f"/api/student/notifications/{n.id}/").status_code == 200
        assert not Notification.objects.filter(pk=n.pk).exists()

    def test_idor_on_read_and_delete(self, student_client, other_student):
        theirs = make(other_student)
        assert student_client.post(f"/api/student/notifications/{theirs.id}/read/").status_code == 404
        assert student_client.delete(f"/api/student/notifications/{theirs.id}/").status_code == 404
        theirs.refresh_from_db()
        assert theirs.read_at is None and Notification.objects.filter(pk=theirs.pk).exists()

    def test_admin_has_own_notifications(self, admin_client, admin):
        make(admin)
        assert admin_client.get("/api/admin/notifications/").json()["meta"]["count"] >= 1
        assert admin_client.get("/api/student/notifications/").status_code == 403

    def test_unknown_id(self, student_client):
        assert student_client.post("/api/student/notifications/00000000-0000-0000-0000-000000000000/read/").status_code == 404


class TestServices:
    def test_email_sent_only_after_commit(self, student, django_capture_on_commit_callbacks):
        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            notifications.send_notification(student, Notification.Type.SECURITY, detail="Hello there")
        assert len(mail.outbox) == 0 and len(callbacks) == 1
        callbacks[0]()
        assert len(mail.outbox) == 1 and "Hello there" in mail.outbox[0].body

    def test_email_failure_does_not_raise(self, student, django_capture_on_commit_callbacks, settings):
        from unittest import mock

        with mock.patch("notifications.services.send_mail", side_effect=OSError("smtp down")):
            with django_capture_on_commit_callbacks(execute=True):
                notifications.send_notification(student, Notification.Type.SECURITY, detail="x")
        assert Notification.objects.filter(user=student).count() == 1

    def test_in_app_only(self, student, django_capture_on_commit_callbacks):
        with django_capture_on_commit_callbacks(execute=True):
            notifications.send_notification(student, Notification.Type.COURSE_PUBLISHED, email=False, course="X")
        assert len(mail.outbox) == 0 and Notification.objects.count() == 1


class TestWorkflowNotifications:
    def types(self, user):
        return set(Notification.objects.filter(user=user).values_list("type", flat=True))

    def test_registration_approved_and_rejected(self, admin_client, django_capture_on_commit_callbacks):
        a, b = APIClient(), APIClient()
        ids = []
        for c, email in ((a, "a@example.com"), (b, "b@example.com")):
            res = register_via_api(c, email, password=PASSWORD)
            ids.append(res.json()["data"]["student"]["id"])
        with django_capture_on_commit_callbacks(execute=True):
            admin_client.post(f"/api/admin/students/approval-requests/{ids[0]}/approve/")
            admin_client.post(f"/api/admin/students/approval-requests/{ids[1]}/reject/", {"reason": "Not eligible"}, format="json")
        n1 = Notification.objects.get(user_id=ids[0])
        n2 = Notification.objects.get(user_id=ids[1])
        assert n1.type == "registration_approved" and n2.type == "registration_rejected"
        assert "Not eligible" in n2.message
        assert {m.to[0] for m in mail.outbox} == {"a@example.com", "b@example.com"}

    def test_course_publish_notifies_active_students_once(self, admin_client, admin, student, other_student):
        pending = APIClient()
        register_via_api(pending, "p@example.com", password=PASSWORD)
        c = Course.objects.create(title="New", slug="new", status="draft", created_by=admin)
        admin_client.post(f"/api/admin/course/{c.id}/publish/")
        assert "course_published" in self.types(student) and "course_published" in self.types(other_student)
        assert Notification.objects.filter(user__email="p@example.com").count() == 0
        assert not Notification.objects.filter(user=admin, type="course_published").exists()
        admin_client.post(f"/api/admin/course/{c.id}/archive/")
        admin_client.post(f"/api/admin/course/{c.id}/publish/")  # republish: no second broadcast
        assert Notification.objects.filter(user=student, type="course_published").count() == 1

    def test_admin_grant_and_revoke(self, admin_client, student, admin):
        c = Course.objects.create(title="Algebra", slug="algebra", status="published", created_by=admin)
        res = admin_client.post("/api/admin/students/access/grant/", {"course": str(c.id), "student": str(student.id)}, format="json")
        assert "access_granted" in self.types(student)
        admin_client.patch(f"/api/admin/students/access/{res.json()['data']['id']}/", {"action": "revoke"}, format="json")
        assert "access_revoked" in self.types(student)

    def test_immediate_access_sends_no_notification(self, student_client, student, admin):
        c = Course.objects.create(title="Free", slug="free", status="published", access_mode="immediate", created_by=admin)
        student_client.post("/api/student/access/", {"course": str(c.id)}, format="json")
        assert Notification.objects.filter(user=student).count() == 0

    def test_password_change_is_a_security_notice(self, student_client, student):
        student_client.post(
            "/api/accounts/password-change/", {"current_password": PASSWORD, "new_password": "An0ther-Str0ng-Pass!"}, format="json"
        )
        assert "security" in self.types(student)
