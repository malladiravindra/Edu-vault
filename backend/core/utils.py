import logging
from pathlib import Path
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from django.conf import settings
import environ

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Client IP. X-Forwarded-For is honoured only when TRUST_PROXY_HEADERS is enabled."""
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def query_value(request, name):
    """Query-string filter value, normalised to lower case (so ?status=ACTIVE and ?status=active match)."""
    value = request.query_params.get(name)
    return value.strip().lower() if value else None


def generate_otp(length=6) -> str:
    """Generate a cryptographically secure random numeric OTP string."""
    return f"{secrets.randbelow(10**length):0{length}d}"


def send_otp_via_smtp(to_email: str, otp: str, purpose: str = "Verification") -> bool:
    """
    Directly connects to Gmail SMTP and sends an OTP email.
    Freshly reads credentials from settings / .env so it works regardless of Django reloader state.
    Also logs the code to console so development is never blocked.
    """
    to_email = (to_email or "").strip().lower()
    
    # Always log OTP in console for local developer debugging
    print(f"\n=======================================================")
    print(f" [EduVault OTP] Purpose : {purpose}")
    print(f" [EduVault OTP] To Email: {to_email}")
    print(f" [EduVault OTP] Code    : {otp}")
    print(f"=======================================================\n", flush=True)

    if getattr(settings, "EMAIL_BACKEND", "").endswith("locmem.EmailBackend"):
        return True

    # Read latest credentials dynamically from .env / settings
    base_dir = Path(__file__).resolve().parent.parent
    env = environ.Env()
    environ.Env.read_env(base_dir / ".env", overwrite=True)

    email_host = env("EMAIL_HOST", default=getattr(settings, "EMAIL_HOST", "smtp.gmail.com"))
    email_port = env.int("EMAIL_PORT", default=getattr(settings, "EMAIL_PORT", 587))
    email_use_tls = env.bool("EMAIL_USE_TLS", default=getattr(settings, "EMAIL_USE_TLS", True))
    email_user = env("EMAIL_HOST_USER", default=getattr(settings, "EMAIL_HOST_USER", ""))
    email_pass = env("EMAIL_HOST_PASSWORD", default=getattr(settings, "EMAIL_HOST_PASSWORD", "")).replace(" ", "")
    from_email = env("DEFAULT_FROM_EMAIL", default=getattr(settings, "DEFAULT_FROM_EMAIL", email_user))

    if not email_user or not email_pass:
        logger.warning("SMTP credentials not fully configured; skipped sending to %s", to_email)
        return False

    subject = f"EduVault: Your {purpose} OTP Code"
    body = (
        f"Hello,\n\n"
        f"Your EduVault {purpose} verification code is: {otp}\n\n"
        f"This code will expire in 10 minutes.\n"
        f"If you did not request this OTP, please ignore this email.\n\n"
        f"— EduVault Security"
    )

    try:
        server = smtplib.SMTP(email_host, email_port, timeout=12)
        if email_use_tls:
            server.ehlo()
            server.starttls()
            server.ehlo()
        server.login(email_user, email_pass)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email
        msg.attach(MIMEText(body, "plain"))

        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
        logger.info("Successfully dispatched OTP email via SMTP to %s", to_email)
        return True
    except Exception as exc:
        logger.exception("Failed to send OTP email via SMTP to %s: %s", to_email, exc)
        return False
