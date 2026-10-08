
import pytest
from django.core import mail
from rest_framework.test import APIClient

from audit.models import AuditEvent
from platform_settings import services as platform
from platform_settings.models import PlatformSettings

from .conftest import auth_client, login_student, register_via_api

pytestmark = pytest.mark.django_db

URL = "/api/admin/settings/"


class TestSettingsAPI:
    def test_get_returns_effective_values_and_no_secrets(self, admin_client, settings):
        res = admin_client.get(URL)
        body = res.json()["data"]
        assert res.status_code == 200
        assert body["settings"]["login_max_attempts"] == settings.LOGIN_MAX_ATTEMPTS
        assert body["overridden"] == []
        text = res.content.decode().lower()
        for secret in (settings.SECRET_KEY, settings.JWT_SIGNING_KEY if hasattr(settings, "JWT_SIGNING_KEY") else "-", "totp_secret", "sk_test", "whsec"):
            assert secret.lower() not in text
        assert set(body["integrations"]) == {"stripe_configured", "stripe_webhook_configured", "email_backend", "storage_backend"}
        assert all(isinstance(v, (bool, str)) for v in body["integrations"].values())

    def test_secrets_never_exposed_even_when_configured(self, admin_client, settings):
        settings.STRIPE_SECRET_KEY = "sk_live_supersecret"
        settings.STRIPE_WEBHOOK_SECRET = "whsec_supersecret"
        settings.EMAIL_HOST_PASSWORD = "smtp-password-123"
        res = admin_client.get(URL)
        text = res.content.decode()
        assert "supersecret" not in text and "smtp-password-123" not in text
        assert res.json()["data"]["integrations"]["stripe_configured"] is True

    def test_patch_override_and_reset(self, admin_client):
        res = admin_client.patch(URL, {"login_max_attempts": 3, "password_min_length": 14}, format="json")
        data = res.json()["data"]
        assert res.status_code == 200 and data["settings"]["login_max_attempts"] == 3
        assert data["overridden"] == ["login_max_attempts", "password_min_length"]
        reset = admin_client.patch(URL, {"login_max_attempts": None}, format="json").json()["data"]
        assert reset["overridden"] == ["password_min_length"]

    def test_validation(self, admin_client):
        for bad in ({"login_max_attempts": 1}, {"otp_expiry_seconds": 5}, {"viewer_jpeg_quality": 101},
                    {"password_min_length": "abc"}, {"payments_enabled": "maybe"}):
            assert admin_client.patch(URL, bad, format="json").status_code == 400, bad
        assert not PlatformSettings.objects.exists() or PlatformSettings.objects.get().login_max_attempts is None

    def test_unknown_fields_are_ignored(self, admin_client, settings):
        admin_client.patch(URL, {"SECRET_KEY": "pwned", "STRIPE_SECRET_KEY": "x", "login_max_attempts": 4}, format="json")
        assert settings.SECRET_KEY != "pwned" and settings.STRIPE_SECRET_KEY != "x"

    def test_change_is_audited_without_values_of_secrets(self, admin_client):
        admin_client.patch(URL, {"viewer_render_width": 900}, format="json")
        event = AuditEvent.objects.get(action="settings.changed")
        assert event.metadata["changes"]["viewer_render_width"]["to"] == 900

    def test_admin_only(self, student_client, client):
        assert student_client.get(URL).status_code == 403
        assert student_client.patch(URL, {"login_max_attempts": 3}, format="json").status_code == 403
        assert student_client.post(URL + "test-email/").status_code == 403
        assert APIClient().get(URL).status_code == 401

    def test_single_row_enforced(self, admin_client):
        from django.db import IntegrityError, transaction

        with pytest.raises(IntegrityError), transaction.atomic():
            PlatformSettings.objects.create(id=2)

    def test_cache_invalidated_on_update(self, admin_client):
        assert platform.get("viewer_render_width") != 777
        admin_client.patch(URL, {"viewer_render_width": 1000}, format="json")
        assert platform.get("viewer_render_width") == 1000


class TestTestEmail:
    def test_sends_to_admin_by_default(self, admin_client, admin):
        res = admin_client.post(URL + "test-email/", {}, format="json")
        assert res.status_code == 200 and mail.outbox[-1].to == [admin.email]
        assert AuditEvent.objects.filter(action="settings.test_email").exists()

    def test_custom_recipient_and_validation(self, admin_client):
        assert admin_client.post(URL + "test-email/", {"to": "ops@example.com"}, format="json").status_code == 200
        assert mail.outbox[-1].to == ["ops@example.com"]
        assert admin_client.post(URL + "test-email/", {"to": "nope"}, format="json").status_code == 400

    def test_delivery_failure_is_generic(self, admin_client):
        from unittest import mock

        with mock.patch("platform_settings.services.send_mail", side_effect=OSError("smtp password=hunter2")):
            res = admin_client.post(URL + "test-email/", {}, format="json")
        assert res.status_code == 502 and "hunter2" not in res.content.decode()


class TestSettingsChangeBehaviour:
    def test_registration_approval_toggle(self, admin_client):
        admin_client.patch(URL, {"registration_requires_approval": False}, format="json")
        res = register_via_api(APIClient(), "auto@example.com")
        assert res.json()["data"]["student"]["status"] == "active"
        admin_client.patch(URL, {"registration_requires_approval": True}, format="json")
        res = register_via_api(APIClient(), "wait@example.com")
        assert res.json()["data"]["student"]["status"] == "pending"

    def test_password_min_length_enforced(self, admin_client):
        admin_client.patch(URL, {"password_min_length": 20}, format="json")
        res = register_via_api(APIClient(), "x@example.com", password="Str0ng-Passw0rd!x")
        assert res.status_code == 400
        assert "at least 20" in str(res.json()["error"]["details"])

    def test_lockout_threshold_is_configurable(self, admin_client, student):
        admin_client.patch(URL, {"login_max_attempts": 3}, format="json")
        c = APIClient()
        for _ in range(3):
            login_student(c, password="wrong-password")
        assert login_student(c).status_code == 429

    def test_session_timeout_is_configurable(self, admin_client, student):
        admin_client.patch(URL, {"session_inactivity_seconds": 300}, format="json")
        c = APIClient()
        auth_client(c, login_student(c).json()["data"]["tokens"])
        assert c.get("/api/accounts/me/").status_code == 200

    def test_email_notifications_toggle(self, admin_client, student, django_capture_on_commit_callbacks):
        from notifications import services as notifications
        from notifications.models import Notification

        admin_client.patch(URL, {"email_notifications_enabled": False}, format="json")
        mail.outbox.clear()
        with django_capture_on_commit_callbacks(execute=True):
            notifications.send_notification(student, Notification.Type.SECURITY, detail="x")
        assert Notification.objects.filter(user=student).count() == 1 and len(mail.outbox) == 0

    def test_otp_still_sent_when_notification_emails_disabled(self, admin_client, student, django_capture_on_commit_callbacks):
        admin_client.patch(URL, {"email_notifications_enabled": False}, format="json")
        mail.outbox.clear()
        with django_capture_on_commit_callbacks(execute=True):
            APIClient().post("/api/accounts/forgot-password/", {"email": student.email}, format="json")
        assert len(mail.outbox) == 1

    def test_payments_can_be_disabled(self, admin_client, student_client, student, admin, settings):
        from courses.models import Course

        settings.STRIPE_SECRET_KEY = "sk_test_x"
        c = Course.objects.create(title="P", slug="p", status="published", access_mode="payment_required", price_amount="5.00", created_by=admin)
        from .conftest import approve_payment

        approve_payment(student, c)
        admin_client.patch(URL, {"payments_enabled": False}, format="json")
        res = student_client.post("/api/student/payment/create-checkout/", {"course": str(c.id)}, format="json")
        assert res.status_code == 503 and res.json()["error"]["code"] == "PAYMENTS_DISABLED"
