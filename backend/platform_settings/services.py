from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction

from audit.models import Actions
from audit.services import create_audit_event
from core.exceptions import ServiceError

from .models import PlatformSettings

_CACHE_KEY = "eduvault:platform_settings"
_CACHE_TTL = 60

# field -> Django setting that provides the environment default
DEFAULTS = {
    "otp_expiry_seconds": "OTP_EXPIRY_SECONDS",
    "session_inactivity_seconds": "SESSION_INACTIVITY_SECONDS",
    "login_max_attempts": "LOGIN_MAX_ATTEMPTS",
    "login_lockout_seconds": "LOGIN_LOCKOUT_SECONDS",
    "password_min_length": "PASSWORD_MIN_LENGTH",
    "registration_requires_approval": "REGISTRATION_REQUIRES_APPROVAL",
    "email_notifications_enabled": "EMAIL_NOTIFICATIONS_ENABLED",
    "viewer_render_width": "VIEWER_RENDER_WIDTH",
    "viewer_jpeg_quality": "VIEWER_JPEG_QUALITY",
    "payments_enabled": "PAYMENTS_ENABLED",
}


def _overrides():
    cached = cache.get(_CACHE_KEY)
    if cached is None:
        row = PlatformSettings.objects.filter(pk=1).first()
        cached = {name: getattr(row, name) for name in DEFAULTS} if row else {}
        cache.set(_CACHE_KEY, cached, _CACHE_TTL)
    return cached


def get(name):
    """Effective value: the admin override if set, otherwise the environment default."""
    value = _overrides().get(name)
    return getattr(settings, DEFAULTS[name]) if value is None else value


def effective():
    return {name: get(name) for name in DEFAULTS}


def overridden():
    return sorted(name for name, value in _overrides().items() if value is not None)


def integrations():
    """Booleans only: whether integrations are configured. Never any secret values."""
    return {
        "stripe_configured": bool(settings.STRIPE_SECRET_KEY),
        "stripe_webhook_configured": bool(settings.STRIPE_WEBHOOK_SECRET),
        "email_backend": settings.EMAIL_BACKEND.rsplit(".", 2)[-2],
        "storage_backend": settings.STORAGE_BACKEND,
    }


def update_settings(*, actor, data, ip=None):
    with transaction.atomic():
        row, _ = PlatformSettings.objects.select_for_update().get_or_create(pk=1)
        before = effective()
        for name, value in data.items():
            setattr(row, name, value)  # None resets a field to its environment default
        row.save()
        cache.delete(_CACHE_KEY)
        after = effective()
        changed = {n: {"from": before[n], "to": after[n]} for n in data if before[n] != after[n]}
        create_audit_event(
            Actions.SETTINGS_CHANGED, actor=actor, target_type="platform_settings", target_id="1", ip=ip,
            metadata={"changes": changed, "fields": sorted(data)},
        )
    return row


def send_test_email(*, actor, to, ip=None):
    try:
        send_mail(
            "EduVault: test email",
            "This is a test email from the EduVault platform settings page. Email delivery is working.",
            settings.DEFAULT_FROM_EMAIL,
            [to],
            fail_silently=False,
        )
    except Exception:  # noqa: BLE001 - never leak SMTP details to the client
        create_audit_event(Actions.SETTINGS_TEST_EMAIL, actor=actor, ip=ip, metadata={"ok": False})
        raise ServiceError("EMAIL_DELIVERY_FAILED", "The test email could not be delivered. Check the email configuration.", 502)
    create_audit_event(Actions.SETTINGS_TEST_EMAIL, actor=actor, ip=ip, metadata={"ok": True})
