import hashlib
import hmac
import secrets
import time
import uuid

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.state import token_backend
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

from audit.models import Actions
from audit.services import create_audit_event
from core.exceptions import ServiceError
from notifications import services as notifications
from notifications.models import Notification
from platform_settings import services as platform

from .models import User


def password_policy_errors(password, user=None):
    """Django's validators plus the admin-configurable minimum length."""
    errors = []
    minimum = platform.get("password_min_length")
    if len(password) < minimum:
        errors.append(f"This password is too short. It must contain at least {minimum} characters.")
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        errors.extend(exc.messages)
    return errors
_CHALLENGE_SALT = "eduvault.2fa.challenge"
# A per-email counter (across all IPs) trips at this multiple of the per-(email, IP) limit.
EMAIL_WIDE_LOCK_FACTOR = 4


# ---------------------------------------------------------------- Redis-backed state

def _key(*parts):
    return "eduvault:" + ":".join(str(p) for p in parts)


def _ensure_not_locked(scope, ident):
    if cache.get(_key("locked", scope, ident)):
        raise ServiceError(
            "ACCOUNT_LOCKED",
            "Too many failed attempts. Please try again later.",
            429,
            {"retry_after": platform.get("login_lockout_seconds")},
        )


def _register_failure(scope, ident, factor=1):
    """Count a failure; returns True when this failure triggers a lockout."""
    counter = _key("fail", scope, ident)
    cache.add(counter, 0, timeout=platform.get("login_lockout_seconds"))
    if cache.incr(counter) >= platform.get("login_max_attempts") * factor:
        cache.set(_key("locked", scope, ident), 1, timeout=platform.get("login_lockout_seconds"))
        cache.delete(counter)
        return True
    return False


def _clear_failures(scope, ident):
    cache.delete(_key("fail", scope, ident))


# Every sign-in is its own session ("sid"), so logging out on one device leaves the others alone.
# Revoking everything (password change/reset, suspension) bumps a per-user epoch that every older token carries.

def current_epoch(user_id):
    return cache.get(_key("epoch", user_id)) or "0"


def _bump_epoch(user_id):
    cache.set(_key("epoch", user_id), uuid.uuid4().hex, timeout=None)


def start_session(user_id, sid):
    cache.set(_key("session", user_id, sid), 1, timeout=platform.get("session_inactivity_seconds"))


def touch_session(user_id, sid):
    """Refresh the inactivity window of one device session. False when it timed out or never existed."""
    if not sid or cache.get(_key("session", user_id, sid)) is None:
        return False
    cache.set(_key("session", user_id, sid), 1, timeout=platform.get("session_inactivity_seconds"))
    return True


def end_session(user_id, sid):
    if sid:
        cache.delete(_key("session", user_id, sid))


def token_session_is_live(user_id, claims):
    """True when the token's epoch is current and its device session is still within the inactivity window."""
    return claims.get("ep") == current_epoch(user_id) and touch_session(user_id, claims.get("sid"))


# ---------------------------------------------------------------- tokens

def issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    refresh["sid"] = uuid.uuid4().hex
    refresh["ep"] = current_epoch(user.id)
    start_session(user.id, refresh["sid"])
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def revoke_all_sessions(user):
    for outstanding in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=outstanding)
    _bump_epoch(user.id)


def _detect_refresh_reuse(refresh_str):
    """A refresh token that is validly signed and unexpired but already blacklisted was replayed: end its session."""
    try:
        payload = token_backend.decode(refresh_str, verify=True)
    except Exception:  # noqa: BLE001 - anything that does not decode is simply invalid
        return
    if payload.get("token_type") != "refresh" or not payload.get("sid"):
        return
    if BlacklistedToken.objects.filter(token__jti=payload.get("jti")).exists():
        end_session(payload.get("user_id"), payload["sid"])
        create_audit_event(
            Actions.REFRESH_REUSE_DETECTED, actor_email="", target_type="user", target_id=payload.get("user_id"),
            metadata={"sid": payload["sid"][:8]},
        )


def refresh_tokens(refresh_str):
    invalid = ServiceError("INVALID_REFRESH_TOKEN", "Refresh token is invalid or expired.", 401)
    try:
        token = RefreshToken(refresh_str)
        user = User.objects.filter(pk=token["user_id"]).first()
    except TokenError:
        _detect_refresh_reuse(refresh_str)
        raise invalid
    except (KeyError, DjangoValidationError):
        raise invalid
    if user is None or not user.is_active or token.get("ep") != current_epoch(user.id):
        raise invalid
    if not touch_session(user.id, token.get("sid")):
        raise ServiceError("SESSION_EXPIRED", "Session expired due to inactivity.", 401)
    with transaction.atomic():
        _, newly_blacklisted = token.blacklist()
        if newly_blacklisted:
            token.set_jti()
            token.set_exp()
            token.set_iat()
            token.outstand()
    if not newly_blacklisted:  # a concurrent request rotated the same token first: treat it as a replay
        _detect_refresh_reuse(refresh_str)
        raise invalid
    return {"access": str(token.access_token), "refresh": str(token)}


# ---------------------------------------------------------------- registration / login

def send_registration_otp(*, email, ip=None):
    """E-mail a verification code. Succeeds silently for an address that already has an account (no enumeration)."""
    email = (email or "").strip().lower()
    _enforce_resend_cooldown("register", email)
    if User.objects.filter(email=email).exists():
        if settings.DEBUG:
            print(f"[EduVault Notice] Registration OTP skipped: user with email '{email}' already exists in database.")
        return None
    otp = _store_otp("register", email)
    notifications.send_otp_email(to=email, otp=otp, purpose="registration", after_commit=False)
    create_audit_event(Actions.REGISTRATION_OTP_SENT, actor_email=email, ip=ip)
    return otp


def verify_registration_otp(*, email, otp, ip=None):
    email = (email or "").strip().lower()
    ok = _check_otp("register", email, otp)
    if not ok:
        if ok is False:
            create_audit_event(Actions.OTP_FAILED, actor_email=email, ip=ip, metadata={"purpose": "registration"})
        raise ServiceError("INVALID_OTP", "The verification code is invalid or has expired.", 400)
    cache.set(_key("reg_verified", email), 1, timeout=settings.REGISTRATION_VERIFICATION_SECONDS)
    create_audit_event(Actions.REGISTRATION_EMAIL_VERIFIED, actor_email=email, ip=ip)


def register_student(*, first_name, last_name, phone_number, email, password, middle_name="", ip=None):
    """Create the student account. Only possible for an e-mail whose OTP was verified, and only once."""
    verified_key = _key("reg_verified", email)
    if not cache.get(verified_key):
        raise ServiceError("EMAIL_NOT_VERIFIED", "Verify your e-mail address first.", 403)
    initial = User.Status.PENDING if platform.get("registration_requires_approval") else User.Status.ACTIVE
    full_name = " ".join(part for part in (first_name, middle_name, last_name) if part)
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                email=email, password=password, full_name=full_name, first_name=first_name,
                middle_name=middle_name, last_name=last_name, phone_number=phone_number, status=initial,
            )
            create_audit_event(Actions.REGISTER, actor=user, target_type="user", target_id=user.id, ip=ip)
            if initial == User.Status.PENDING:
                notifications.notify_admins(
                    Notification.Type.NEW_REGISTRATION, student=user.full_name, data={"user": str(user.id)}
                )
    except IntegrityError:
        raise ServiceError("EMAIL_ALREADY_REGISTERED", "An account with this email already exists.", 409)
    cache.delete(verified_key)  # the verification is single-use
    return user


def authenticate_credentials(*, email, password, role, ip=None):
    email = (email or "").strip().lower()
    # Failures are counted per (email, IP) so one client cannot lock a victim out from everywhere, plus a wider
    # per-email backstop (EMAIL_WIDE_LOCK_FACTOR x the limit) against distributed guessing.
    pair = f"{email}|{ip or '-'}"
    _ensure_not_locked("login", pair)
    _ensure_not_locked("login_email", email)
    user = User.objects.filter(email=email).first()
    if user is not None:
        valid = user.check_password(password) and user.role == role
    else:
        make_password(password)  # equalise timing with the existing-user path
        valid = False
    if not valid:
        locked = _register_failure("login", pair)
        locked = _register_failure("login_email", email, EMAIL_WIDE_LOCK_FACTOR) or locked
        create_audit_event(Actions.LOGIN_FAILED, actor_email=email, ip=ip, metadata={"role": role})
        if locked:
            create_audit_event(Actions.LOGIN_LOCKED, actor_email=email, ip=ip)
        raise ServiceError("INVALID_CREDENTIALS", "Invalid email or password.", 401)
    if not user.is_active:
        create_audit_event(Actions.LOGIN_FAILED, actor=user, ip=ip, metadata={"reason": "suspended"})
        raise ServiceError("ACCOUNT_SUSPENDED", "This account has been suspended.", 403)
    _clear_failures("login", pair)
    _clear_failures("login_email", email)
    return user


def login_student(*, email, password, ip=None):
    """Email + password only (no OTP/2FA, that is the admin API). Only an approved, active student gets tokens:
    pending and rejected registrations are told why (after the password was correct, so nothing is enumerable)."""
    user = authenticate_credentials(email=email, password=password, role=User.Role.STUDENT, ip=ip)  # suspended -> 403
    if user.status != User.Status.ACTIVE:
        create_audit_event(Actions.LOGIN_FAILED, actor=user, ip=ip, metadata={"reason": user.status})
        if user.status == User.Status.PENDING:
            raise ServiceError("REGISTRATION_PENDING", "Your registration is awaiting admin approval.", 403)
        raise ServiceError(
            "REGISTRATION_REJECTED", "Your registration was not approved.", 403,
            {"reason": user.rejection_reason} if user.rejection_reason else None,
        )
    create_audit_event(Actions.LOGIN_SUCCESS, actor=user, ip=ip)
    return user, issue_tokens(user)


def logout(*, user, refresh_str, access_sid=None, ip=None):
    try:
        token = RefreshToken(refresh_str)
        if str(token["user_id"]) == str(user.id):
            token.blacklist()
            end_session(user.id, token.get("sid"))
    except (TokenError, KeyError):
        pass
    end_session(user.id, access_sid)  # the access token in use always ends, even if the refresh token sent was bad
    create_audit_event(Actions.LOGOUT, actor=user, ip=ip)


# ---------------------------------------------------------------- profile / passwords

def update_profile(*, user, ip=None, **fields):
    """Names, phone. Name parts recompute the display name; a bare `full_name` only changes the display name."""
    parts = ("first_name", "middle_name", "last_name")
    for name in (*parts, "phone_number"):
        if name in fields:
            setattr(user, name, fields[name])
    if any(p in fields for p in parts):
        user.full_name = " ".join(v for v in (user.first_name, user.middle_name, user.last_name) if v)
    elif "full_name" in fields:
        user.full_name = fields["full_name"]
    changed = [n for n in (*parts, "phone_number") if n in fields]
    if any(p in fields for p in parts) or "full_name" in fields:
        changed.append("full_name")
    with transaction.atomic():
        user.save(update_fields=[*changed, "updated_at"])
        create_audit_event(Actions.PROFILE_UPDATED, actor=user, target_type="user", target_id=user.id, ip=ip)
    return user


def change_password(*, user, current_password, new_password, ip=None):
    if not user.check_password(current_password):
        raise ServiceError("INVALID_CREDENTIALS", "Current password is incorrect.", 400)
    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        revoke_all_sessions(user)
        create_audit_event(Actions.PASSWORD_CHANGED, actor=user, target_type="user", target_id=user.id, ip=ip)
        notifications.send_notification(
            user, Notification.Type.SECURITY, detail="Your password was changed and other sessions were signed out."
        )
    return issue_tokens(user)


_RESET_SALT = "eduvault.password.reset"


def _otp_keys(purpose, ident):
    return _key("otp", purpose, ident), _key("otp_attempts", purpose, ident)


def _hash_otp(purpose, ident, otp):
    return hmac.new(settings.SECRET_KEY.encode(), f"{purpose}:{ident}:{otp}".encode(), hashlib.sha256).hexdigest()


def _enforce_resend_cooldown(purpose, email):
    """One OTP e-mail per address per cooldown window. Applied before any account lookup so it reveals nothing."""
    seconds = settings.OTP_RESEND_COOLDOWN_SECONDS
    if seconds and not cache.add(_key("otp_cooldown", purpose, email), 1, timeout=seconds):
        raise ServiceError(
            "OTP_COOLDOWN", "Please wait before requesting another code.", 429, {"retry_after": seconds}
        )


def _store_otp(purpose, ident, ttl=None):
    """New random 6-digit code, kept only as a keyed hash with an expiry and a fresh attempt counter."""
    ttl = ttl or platform.get("otp_expiry_seconds")
    otp = f"{secrets.randbelow(10**6):06d}"
    code_key, attempts_key = _otp_keys(purpose, ident)
    cache.set(code_key, _hash_otp(purpose, ident, otp), timeout=ttl)
    cache.set(attempts_key, 0, timeout=ttl)
    return otp


def _check_otp(purpose, ident, otp, max_attempts=None, ttl=None):
    """True exactly once for a correct, unexpired code; False for a wrong guess (too many burn the code);
    None when there is no live code at all (never requested, expired, used or burned)."""
    code_key, attempts_key = _otp_keys(purpose, ident)
    expected = cache.get(code_key)
    if expected is None:
        return None
    if not hmac.compare_digest(expected, _hash_otp(purpose, ident, str(otp or "").strip())):
        cache.add(attempts_key, 0, timeout=ttl or platform.get("otp_expiry_seconds"))
        if cache.incr(attempts_key) >= (max_attempts or settings.OTP_MAX_ATTEMPTS):
            cache.delete(code_key)
        return False
    cache.delete_many([code_key, attempts_key])  # single use
    return True


def request_password_reset(*, email, ip=None):
    """Emails a one-time code. Always succeeds from the caller's perspective to avoid account enumeration."""
    email = (email or "").strip().lower()
    _enforce_resend_cooldown("reset", email)
    user = User.objects.filter(email=email).first()
    if user is None or not user.is_active:
        return
    otp = _store_otp("reset", str(user.id))
    with transaction.atomic():
        create_audit_event(
            Actions.PASSWORD_RESET_REQUESTED, actor=user, target_type="user", target_id=user.id, ip=ip
        )
        notifications.send_otp_email(to=user.email, otp=otp, purpose="password reset")


def verify_reset_otp(*, email, otp, ip=None):
    """Exchange a valid OTP for a short-lived, single-use reset token."""
    invalid = ServiceError("INVALID_OTP", "The verification code is invalid or has expired.", 400)
    user = User.objects.filter(email=(email or "").strip().lower()).first()
    if user is None or not user.is_active:
        raise invalid
    ok = _check_otp("reset", str(user.id), otp)
    if not ok:
        if ok is False:
            create_audit_event(Actions.OTP_FAILED, actor=user, ip=ip)
        raise invalid
    create_audit_event(Actions.PASSWORD_RESET_VERIFIED, actor=user, target_type="user", target_id=user.id, ip=ip)
    # Bound to the current password hash, so the token stops working once the password changes.
    return signing.dumps({"uid": str(user.id), "pw": user.password[-12:]}, salt=_RESET_SALT)


def confirm_password_reset(*, reset_token, new_password, ip=None):
    invalid = ServiceError("INVALID_RESET_TOKEN", "The reset session is invalid or has expired.", 400)
    try:
        payload = signing.loads(reset_token, salt=_RESET_SALT, max_age=settings.PASSWORD_RESET_TOKEN_SECONDS)
        user = User.objects.filter(pk=payload["uid"]).first()
    except (signing.BadSignature, KeyError, DjangoValidationError):
        raise invalid
    if user is None or not user.is_active or user.password[-12:] != payload["pw"]:
        raise invalid
    errors = password_policy_errors(new_password, user)
    if errors:
        raise serializers.ValidationError({"new_password": errors})
    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        revoke_all_sessions(user)
        create_audit_event(
            Actions.PASSWORD_RESET_COMPLETED, actor=user, target_type="user", target_id=user.id, ip=ip
        )
        notifications.send_notification(
            user, Notification.Type.SECURITY, detail="Your password was reset. If this was not you, contact support."
        )


# ---------------------------------------------------------------- admin API login (password + e-mailed code)

ADMIN_LOGIN_OTP_PURPOSE = "admin_login_2fa"


def _admin_otp_pointer_key(user_id):
    return _key("admin_otp_current", user_id)


def _enforce_admin_otp_send_limits(user, ip):
    """Cooldown between two OTP e-mails plus an hourly cap per admin. Only reachable after a correct password."""
    cooldown = settings.ADMIN_LOGIN_OTP_RESEND_COOLDOWN_SECONDS
    blocked = bool(cooldown) and not cache.add(_key("admin_otp_cooldown", user.id), 1, timeout=cooldown)
    if not blocked:
        counter = _key("admin_otp_hourly", user.id)
        cache.add(counter, 0, timeout=3600)
        blocked = cache.incr(counter) > settings.ADMIN_LOGIN_OTP_MAX_PER_HOUR
    if blocked:
        create_audit_event(Actions.ADMIN_OTP_RATE_LIMITED, actor=user, ip=ip)
        raise ServiceError(
            "OTP_RATE_LIMITED", "Too many verification codes requested. Please try again later.", 429,
            {"retry_after": max(cooldown, 1)},
        )


def _issue_admin_login_otp(user, nonce):
    """A new 6-digit code for this login attempt. It replaces (invalidates) any earlier code of the same admin."""
    pointer_key = _admin_otp_pointer_key(user.id)
    previous = cache.get(pointer_key)
    if previous:
        old_ident = f"{user.id}:{previous.split('|')[0]}"
        cache.delete_many(list(_otp_keys(ADMIN_LOGIN_OTP_PURPOSE, old_ident)))
    ttl = settings.ADMIN_LOGIN_OTP_SECONDS
    otp = _store_otp(ADMIN_LOGIN_OTP_PURPOSE, f"{user.id}:{nonce}", ttl=ttl)
    cache.set(pointer_key, f"{nonce}|{time.time()}", timeout=ttl)
    return otp


def _verify_admin_login_otp(user, nonce, otp):
    """True once for the live code of THIS login attempt; None when there is no live code (expired, used, burned or
    replaced by a newer one); False for a wrong guess. Expiry is judged by the server clock, here and by the cache."""
    pointer_key = _admin_otp_pointer_key(user.id)
    pointer = cache.get(pointer_key)
    if not pointer:
        return None
    current, _, issued = pointer.partition("|")
    if current != nonce:
        return None
    if time.time() - float(issued) > settings.ADMIN_LOGIN_OTP_SECONDS:
        cache.delete(pointer_key)
        return None
    result = _check_otp(
        ADMIN_LOGIN_OTP_PURPOSE, f"{user.id}:{nonce}", otp,
        max_attempts=settings.ADMIN_LOGIN_OTP_MAX_ATTEMPTS, ttl=settings.ADMIN_LOGIN_OTP_SECONDS,
    )
    if result is not False:
        cache.delete(pointer_key)  # used up (True) or gone (None)
    return result


def start_admin_login_otp(user, ip=None):
    """Rate-limit, generate, store (hashed) and e-mail a new admin sign-in code. Returns the attempt's nonce.
    Shared by the API admin login and the Django admin site; the caller has already verified the password and role."""
    _enforce_admin_otp_send_limits(user, ip)
    nonce = uuid.uuid4().hex
    otp = _issue_admin_login_otp(user, nonce)
    notifications.send_admin_login_otp_email(to=user.email, otp=otp, seconds=settings.ADMIN_LOGIN_OTP_SECONDS)
    create_audit_event(Actions.ADMIN_OTP_SENT, actor=user, ip=ip)
    return nonce


def admin_login_otp_is_live(user, nonce):
    """True while the code of this attempt can still be tried (not expired, used, replaced or burned)."""
    pointer = cache.get(_admin_otp_pointer_key(user.id))
    if not pointer or pointer.partition("|")[0] != nonce:
        return False
    return cache.get(_otp_keys(ADMIN_LOGIN_OTP_PURPOSE, f"{user.id}:{nonce}")[0]) is not None


def check_admin_login_otp(*, user, nonce, otp, ip=None):
    """The one place an admin sign-in code is checked (API and Django admin). Raises ServiceError on any failure; the
    error carries `.restart = True` when no usable code is left and the admin must enter the password again."""
    _ensure_not_locked("2fa", user.id)
    result = _verify_admin_login_otp(user, nonce, otp)
    if result is not True:
        if result is None:
            create_audit_event(Actions.ADMIN_OTP_EXPIRED, actor=user, ip=ip)
        locked = _register_failure("2fa", user.id)
        create_audit_event(
            Actions.TWO_FACTOR_FAILED, actor=user, ip=ip,
            metadata={"reason": "bad_otp" if result is False else "expired_or_used_otp", "locked": locked},
        )
        error = ServiceError("INVALID_TWO_FACTOR_CODE", "The verification code is invalid or has expired.", 401)
        error.restart = not admin_login_otp_is_live(user, nonce)
        raise error
    _clear_failures("2fa", user.id)
    create_audit_event(Actions.ADMIN_OTP_VERIFIED, actor=user, ip=ip)


def admin_login(*, email, password, ip=None):
    """Step 1 of the admin sign-in: password, then an e-mailed 6-digit code (valid 30 s). No tokens are issued."""
    user = authenticate_credentials(email=email, password=password, role=User.Role.ADMIN, ip=ip)
    if not user.is_approved:  # same answer as a wrong password: nothing about the account is revealed
        create_audit_event(Actions.LOGIN_FAILED, actor=user, ip=ip, metadata={"reason": "not_approved"})
        raise ServiceError("INVALID_CREDENTIALS", "Invalid email or password.", 401)
    nonce = start_admin_login_otp(user, ip)
    challenge = signing.dumps({"uid": str(user.id), "n": nonce}, salt=_CHALLENGE_SALT)
    return {
        "requires_two_factor": True,
        "two_factor_method": "email_otp",
        "challenge_token": challenge,
        "expires_in": settings.ADMIN_LOGIN_OTP_SECONDS,
        "message": "A verification code has been sent to your registered email.",
    }


def _user_from_challenge(challenge_token):
    invalid = ServiceError("INVALID_CHALLENGE", "The login challenge is invalid or expired.", 401)
    try:
        payload = signing.loads(
            challenge_token, salt=_CHALLENGE_SALT, max_age=settings.TWO_FACTOR_CHALLENGE_SECONDS
        )
        user = User.objects.get(pk=payload["uid"])
    except (signing.BadSignature, User.DoesNotExist, KeyError):
        raise invalid
    if user.role != User.Role.ADMIN or not user.is_approved:
        raise invalid
    if cache.get(_key("challenge_used", payload.get("n", ""))):
        raise invalid
    return user


def _challenge_nonce(challenge_token):
    return signing.loads(challenge_token, salt=_CHALLENGE_SALT).get("n", "")


def _consume_challenge(challenge_token):
    """Once a challenge has produced tokens it cannot be replayed (it would otherwise live for its full 5 minutes)."""
    payload = signing.loads(challenge_token, salt=_CHALLENGE_SALT)
    cache.set(_key("challenge_used", payload.get("n", "")), 1, timeout=settings.TWO_FACTOR_CHALLENGE_SECONDS + 60)


def two_factor_verify(*, challenge_token, otp, ip=None):
    """Step 2 of the admin API sign-in: the e-mailed code. The only place an admin API token is ever issued."""
    user = _user_from_challenge(challenge_token)
    check_admin_login_otp(user=user, nonce=_challenge_nonce(challenge_token), otp=otp, ip=ip)
    _consume_challenge(challenge_token)
    create_audit_event(Actions.LOGIN_SUCCESS, actor=user, ip=ip, metadata={"role": "admin", "method": "email_otp"})
    return user, issue_tokens(user)


# ---------------------------------------------------------------- registration review + user management

def _locked_student(user_id):
    return User.objects.select_for_update().get(pk=user_id, role=User.Role.STUDENT)


def approve_registration(*, actor, user, ip=None):
    with transaction.atomic():
        user = _locked_student(user.pk)
        if user.status != User.Status.PENDING:
            raise ServiceError("INVALID_STATE", "Only pending registrations can be approved.", 409)
        user.status = User.Status.ACTIVE
        user.reviewed_by, user.reviewed_at, user.rejection_reason = actor, timezone.now(), ""
        user.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason", "updated_at"])
        create_audit_event(
            Actions.REGISTRATION_APPROVED, actor=actor, target_type="user", target_id=user.id, ip=ip
        )
        notifications.send_notification(user, Notification.Type.REGISTRATION_APPROVED)
    return user


def reject_registration(*, actor, user, reason="", ip=None):
    with transaction.atomic():
        user = _locked_student(user.pk)
        if user.status != User.Status.PENDING:
            raise ServiceError("INVALID_STATE", "Only pending registrations can be rejected.", 409)
        user.status = User.Status.REJECTED
        user.reviewed_by, user.reviewed_at, user.rejection_reason = actor, timezone.now(), reason[:500]
        user.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason", "updated_at"])
        create_audit_event(
            Actions.REGISTRATION_REJECTED, actor=actor, target_type="user", target_id=user.id, ip=ip,
            metadata={"reason": reason[:500]},
        )
        notifications.send_notification(
            user, Notification.Type.REGISTRATION_REJECTED, reason=f"Reason: {reason[:500]}" if reason else ""
        )
    return user


def _guard_not_self(actor, user):
    if user.pk == actor.pk:
        raise ServiceError("CANNOT_MODIFY_SELF", "You cannot perform this action on your own account.", 400)


def suspend_user(*, actor, user, ip=None):
    _guard_not_self(actor, user)
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        if user.status != User.Status.ACTIVE:
            raise ServiceError("INVALID_STATE", "Only active users can be suspended.", 409)
        user.status = User.Status.SUSPENDED
        user.save(update_fields=["status", "updated_at"])
        revoke_all_sessions(user)
        create_audit_event(Actions.USER_SUSPENDED, actor=actor, target_type="user", target_id=user.id, ip=ip)
    return user


def reactivate_user(*, actor, user, ip=None):
    _guard_not_self(actor, user)
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        if user.status != User.Status.SUSPENDED:
            raise ServiceError("INVALID_STATE", "Only suspended users can be reactivated.", 409)
        user.status = User.Status.ACTIVE
        user.save(update_fields=["status", "updated_at"])
        create_audit_event(Actions.USER_REACTIVATED, actor=actor, target_type="user", target_id=user.id, ip=ip)
    return user


def admin_update_user(*, actor, user, full_name, ip=None):
    with transaction.atomic():
        user.full_name = full_name
        user.save(update_fields=["full_name", "updated_at"])
        create_audit_event(Actions.USER_UPDATED, actor=actor, target_type="user", target_id=user.id, ip=ip)
    return user


def delete_user(*, actor, user, ip=None):
    _guard_not_self(actor, user)
    if user.role == User.Role.ADMIN:
        raise ServiceError("CANNOT_DELETE_ADMIN", "Admin accounts cannot be deleted through the API.", 400)
    user_id, email = user.id, user.email
    try:
        with transaction.atomic():
            user.delete()
            create_audit_event(
                Actions.USER_DELETED, actor=actor, target_type="user", target_id=user_id, ip=ip,
                metadata={"email": email},
            )
    except ProtectedError:
        raise ServiceError("USER_IN_USE", "This user has records that must be kept. Suspend the account instead.", 409)
