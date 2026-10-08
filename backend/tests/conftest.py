import re

import pytest
import time
from django.core import mail
from django.core.cache import cache
from rest_framework.test import APIClient

from accounts import services
from accounts.models import User

PASSWORD = "Str0ng-Passw0rd!x"


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def private_storage_dir(settings, tmp_path):
    settings.STORAGE_BACKEND = "local"
    settings.PRIVATE_MEDIA_ROOT = str(tmp_path / "private")


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def student(db):
    return User.objects.create_user("student@example.com", PASSWORD, full_name="Student One")


@pytest.fixture
def other_student(db):
    return User.objects.create_user("other@example.com", PASSWORD, full_name="Student Two")


@pytest.fixture
def admin(db):
    return User.objects.create_superuser("admin@example.com", PASSWORD, full_name="Admin One")


def login_student(client, email="student@example.com", password=PASSWORD):
    return client.post("/api/student/login/", {"email": email, "password": password}, format="json")


def minted_client(user):
    """A client holding genuine tokens for `user` whatever its status. A pending/rejected student can no longer sign
    in, so this is how tests prove the server still refuses such a token (defence in depth)."""
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {services.issue_tokens(user)['access']}")
    return c


def auth_client(client, tokens):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


@pytest.fixture
def student_client(client, student):
    res = login_student(client)
    return auth_client(client, res.json()["data"]["tokens"])


def admin_otp_from_outbox(email):
    """The most recent admin sign-in code e-mailed to `email` (read from the test outbox, never from an API response)."""
    for message in reversed(mail.outbox):
        if email.lower() in [r.lower() for r in message.to] and "Admin Login Verification" in message.subject:
            found = re.search(r"verification code is: (\d{6})", message.body)
            if found:
                return found.group(1)
    return None


def admin_login_step(client, email, password=PASSWORD):
    """Step 1 of the admin API sign-in (password): the e-mailed code is waiting in the outbox afterwards."""
    return client.post("/api/admin/login/", {"email": email, "password": password}, format="json")


def admin_sign_in(client, email, password=PASSWORD):
    """The real admin API sign-in: password, then the e-mailed code. Returns the final response."""
    first = admin_login_step(client, email, password)
    assert first.status_code == 200, first.content
    return client.post(
        "/api/admin/login/2fa/verify/",
        {"challenge_token": first.json()["data"]["challenge_token"], "otp": admin_otp_from_outbox(email)},
        format="json",
    )


@pytest.fixture
def admin_client(db, admin):
    """APIClient authenticated as an admin who signed in with password + the e-mailed code."""
    c = APIClient()
    res = admin_sign_in(c, admin.email)
    auth_client(c, res.json()["data"]["tokens"])
    mail.outbox.clear()  # the sign-in code e-mail is not what the tests using this fixture are about
    return c


def otp_from_outbox(email):
    """The most recent OTP e-mailed to `email` (read from the test mail outbox, never from an API response)."""
    for message in reversed(mail.outbox):
        if email.lower() in [r.lower() for r in message.to]:
            found = re.search(r"OTP is: (\d{6})", message.body)
            if found:
                return found.group(1)
    return None


def django_admin_login(client, email, *, password=PASSWORD, next_url="/admin/"):
    """The Django admin sign-in: e-mail + password only (a normal Django session). Returns the response."""
    return client.post(f"/admin/login/?next={next_url}", {"username": email, "password": password})


def register_via_api(client, email, *, password=PASSWORD, first_name="Test", last_name="Student", middle_name="",
                     phone_number="9876543210", confirm_password=None, **extra):
    """The real three-step registration: send OTP -> verify OTP -> create account. Returns the final response."""
    client.post("/api/student/register/send-otp/", {"email": email}, format="json")
    client.post("/api/student/register/verify-otp/", {"email": email, "otp": otp_from_outbox(email.strip().lower())}, format="json")
    body = {
        "first_name": first_name, "middle_name": middle_name, "last_name": last_name, "phone_number": phone_number,
        "email": email, "password": password, "confirm_password": password if confirm_password is None else confirm_password,
    }
    body.update(extra)
    return client.post("/api/student/register/", body, format="json")


def approve_payment(student, course):
    """State left by the admin's 'payment required' decision: a pending request flagged payment_required."""
    from access.models import CourseAccess

    record, _ = CourseAccess.objects.update_or_create(
        student=student, course=course, defaults={"status": "pending", "payment_required": True}
    )
    return record
