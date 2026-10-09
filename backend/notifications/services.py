import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from core.exceptions import ServiceError
from platform_settings import services as platform

from .models import Notification

logger = logging.getLogger(__name__)
T = Notification.Type

# E-mail copies the student may switch off (Settings -> email_notifications). Everything else that is e-mailed -
# security notices, registration decisions, payment requests/results, access rejected/revoked - is mandatory.
OPTIONAL_EMAIL_TYPES = frozenset({T.ACCESS_GRANTED, T.ACCESS_PENDING, T.RESOURCE_AVAILABLE, T.COURSE_PUBLISHED})

# type -> (title, message); the single place where user-facing notification wording lives.
_TEMPLATES = {
    T.REGISTRATION_APPROVED: ("Registration approved", "Your EduVault registration has been approved. You can now browse courses."),
    T.REGISTRATION_REJECTED: ("Registration not approved", "Your EduVault registration was not approved. {reason}"),
    T.ACCESS_GRANTED: ("Course access granted", "You now have access to \"{course}\"."),
    T.ACCESS_REVOKED: ("Course access revoked", "Your access to \"{course}\" has been revoked."),
    T.PAYMENT_SUCCESSFUL: ("Payment received", "Your payment for \"{course}\" was successful and your access is active."),
    T.COURSE_PUBLISHED: ("New course available", "\"{course}\" has been published."),
    T.SECURITY: ("Security notice", "{detail}"),
    # Admin-facing events
    T.NEW_REGISTRATION: ("New registration", "{student} registered and is awaiting approval."),
    T.ACCESS_REQUESTED: ("Access requested", "{student} requested access to \"{course}\"."),
    T.PAYMENT_RECEIVED: ("Payment received", "{student} paid for \"{course}\"."),
    T.PAYMENT_REQUESTED: (
        "Payment required",
        "Payment of {amount} {currency} is required to get access to \"{course}\". Open your payment requests to pay.",
    ),
    T.ACCESS_REJECTED: ("Access request rejected", "Your access request for \"{course}\" was not approved."),
    T.ACCESS_PENDING: ("Access under review", "Your access to \"{course}\" is pending manual review."),
    T.PAYMENT_FAILED: ("Payment unsuccessful", "Your payment for \"{course}\" was not completed. You can try again."),
    T.RESOURCE_AVAILABLE: ("New material available", "\"{resource}\" is now available in \"{course}\"."),
    T.PAYMENT_ATTENTION: ("Payment needs attention", "{student}: {detail} (\"{course}\")."),
}


# ---------------------------------------------------------------- email

def send_email(*, to, subject, body, after_commit=True):
    """Send through the configured Django e-mail backend (SMTP or console).

    By default it is sent after the surrounding transaction commits. E-mail failures never break the business
    operation and never log the message body (it may contain a one-time code).
    """
    subject = subject if subject.startswith("EduVault") else f"EduVault: {subject}"

    def _send():
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)
        except Exception:  # noqa: BLE001 - delivery problems must not surface to API clients
            logger.exception("Failed to send email %r", subject)

    if after_commit:
        transaction.on_commit(_send)
    else:
        _send()


_OTP_EMAILS = {
    "registration": ("EduVault Email Verification OTP", "verification"),
    "password reset": ("EduVault Password Reset OTP", "password reset"),
}

from core.utils import send_otp_via_smtp


def send_otp_email(*, to, otp, purpose="password reset", after_commit=True):
    subject, noun = _OTP_EMAILS.get(purpose, ("EduVault OTP Verification", purpose))
    body = (
        f"Hello,\n\n"
        f"Your EduVault {noun} OTP is: {otp}\n\n"
        f"This code will expire in 10 minutes.\n"
        f"If you did not request this OTP, please ignore this email.\n\n"
        f"— EduVault Security"
    )
    send_email(
        to=to,
        subject=subject,
        body=body,
        after_commit=after_commit,
    )
    # Direct SMTP dispatch with live console debug output
    send_otp_via_smtp(to_email=to, otp=otp, purpose=noun.capitalize())


def send_admin_login_otp_email(*, to, otp, seconds):
    """The admin sign-in code. Sent immediately; uses direct SMTP and prints to console for debugging."""
    send_email(
        to=to,
        subject="EduVault Admin Login Verification Code",
        body=f"Your admin sign-in verification code is: {otp}\nValid for {seconds} seconds.",
        after_commit=False,
    )
    send_otp_via_smtp(to_email=to, otp=otp, purpose="Admin Login 2FA")


# ---------------------------------------------------------------- in-app + email notifications

def _render(ntype, ctx):
    title, message = _TEMPLATES[ntype]
    return title, message.format(**{k: ctx.get(k, "") for k in ("reason", "course", "detail", "student", "amount", "currency", "resource")}).strip()


def send_notification(user, ntype, *, data=None, email=True, **ctx):
    """Create an in-app notification (inside the caller's transaction) and optionally email the user."""
    title, message = _render(ntype, ctx)
    notification = Notification.objects.create(user=user, type=ntype, title=title, message=message, data=data or {})
    wants_email = user.email_notifications or ntype not in OPTIONAL_EMAIL_TYPES
    if email and wants_email and platform.get("email_notifications_enabled"):
        send_email(to=user.email, subject=title, body=f"Hello {user.full_name},\n\n{message}\n")
    return notification


def notify_many(users, ntype, *, data=None, **ctx):
    """In-app only fan-out (e.g. a course was published). One bulk insert, no per-user emails."""
    title, message = _render(ntype, ctx)
    Notification.objects.bulk_create(
        [Notification(user=u, type=ntype, title=title, message=message, data=data or {}) for u in users],
        batch_size=500,
    )


def notify_admins(ntype, *, data=None, **ctx):
    """In-app notification for every active admin (never e-mailed, never sent to students)."""
    from accounts.models import User

    admins = User.objects.filter(role=User.Role.ADMIN, status=User.Status.ACTIVE)
    notify_many(admins.iterator(), ntype, data=data, **ctx)


# ---------------------------------------------------------------- reading / state changes

def mark_read(*, user, notification):
    if notification.user_id != user.id:
        raise ServiceError("NOT_FOUND", "The requested resource was not found.", 404)
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    return notification


def mark_all_read(*, user):
    return Notification.objects.filter(user=user, read_at__isnull=True).update(read_at=timezone.now())
