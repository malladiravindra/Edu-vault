import pytest

from audit.models import AuditEvent
from audit.services import create_audit_event

pytestmark = pytest.mark.django_db


def test_audit_event_is_immutable(student):
    event = create_audit_event("test.action", actor=student)
    event.action = "tampered"
    with pytest.raises(PermissionError):
        event.save()
    with pytest.raises(PermissionError):
        event.delete()
    with pytest.raises(PermissionError):
        AuditEvent.objects.all().update(action="x")
    with pytest.raises(PermissionError):
        AuditEvent.objects.all().delete()
    assert AuditEvent.objects.get(pk=event.pk).action == "test.action"


def test_sensitive_metadata_is_scrubbed(student):
    event = create_audit_event("test.action", actor=student, metadata={"password": "x", "refresh_token": "y", "note": "ok"})
    assert event.metadata == {"note": "ok"}


def test_audit_api_admin_only(student_client, admin_client, student):
    create_audit_event("test.action", actor=student, target_type="thing", target_id="1")
    assert student_client.get("/api/admin/audit-logs/").status_code == 403
    res = admin_client.get("/api/admin/audit-logs/?action=test.action")
    body = res.json()
    assert res.status_code == 200 and body["meta"]["count"] == 1
    detail = admin_client.get(f"/api/admin/audit-logs/{body['data'][0]['id']}/")
    assert detail.status_code == 200 and detail.json()["data"]["target_type"] == "thing"


def test_audit_api_has_no_write_methods(admin_client):
    assert admin_client.post("/api/admin/audit-logs/", {}, format="json").status_code == 405
    assert admin_client.delete("/api/admin/audit-logs/").status_code == 405


def test_audit_invalid_filter_is_400_not_500(admin_client):
    assert admin_client.get("/api/admin/audit-logs/?actor=not-a-uuid").status_code == 400


def test_login_events_recorded(client, student):
    client.post("/api/accounts/login/", {"email": student.email, "password": "bad"}, format="json")
    client.post("/api/accounts/login/", {"email": student.email, "password": "Str0ng-Passw0rd!x"}, format="json")
    actions = set(AuditEvent.objects.values_list("action", flat=True))
    assert {"auth.login.failed", "auth.login.success"} <= actions


def test_production_default_hasher_is_argon2():
    """pytest.ini swaps in a fast hasher; make sure Argon2 itself works and is the declared default."""
    from django.contrib.auth.hashers import Argon2PasswordHasher

    hasher = Argon2PasswordHasher()
    hashed = hasher.encode("Some-Passw0rd!", hasher.salt())
    assert hashed.startswith("argon2") and hasher.verify("Some-Passw0rd!", hashed)
    source = open("config/settings.py").read()
    assert 'default="django.contrib.auth.hashers.Argon2PasswordHasher"' in source
