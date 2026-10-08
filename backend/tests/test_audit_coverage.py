"""Every audit action the application emits is asserted here (or in another module), with actor and target."""
import json

import pytest
from rest_framework.test import APIClient

from access.models import CourseAccess
from audit.models import AuditEvent
from courses.models import Course
from payments.models import Payment

from .conftest import PASSWORD, auth_client, login_student
from .test_payments import (  # noqa: F401  (stripe settings fixture lives there)
    WEBHOOK_SECRET,
    send_event,
    session_obj,
)
from .test_resources import make_pdf_bytes, upload

pytestmark = pytest.mark.django_db


def latest(action):
    event = AuditEvent.objects.filter(action=action).order_by("-created_at").first()
    assert event is not None, f"no audit event {action!r}"
    return event


def test_logout_event(student_client, student):
    tokens = login_student(APIClient()).json()["data"]["tokens"]
    c = APIClient()
    auth_client(c, tokens)
    c.post("/api/accounts/logout/", {"refresh": tokens["refresh"]}, format="json")
    assert latest("auth.logout").actor == student


def test_password_change_and_profile_update_events(student_client, student):
    student_client.patch("/api/accounts/me/", {"full_name": "New Name"}, format="json")
    ev = latest("user.profile_updated")
    assert ev.actor == student and ev.target_id == str(student.id)
    student_client.post("/api/accounts/password-change/", {"current_password": PASSWORD, "new_password": "An0ther-Str0ng-Pass!"}, format="json")
    ev = latest("auth.password.changed")
    assert ev.actor == student and ev.target_type == "user"
    assert "An0ther" not in json.dumps(ev.metadata) and PASSWORD not in json.dumps(ev.metadata)


def test_two_factor_events(admin_client, admin):
    challenge = APIClient().post("/api/admin/login/", {"email": admin.email, "password": PASSWORD}, format="json").json()["data"]["challenge_token"]
    APIClient().post("/api/admin/login/2fa/verify/", {"challenge_token": challenge, "otp": "000000"}, format="json")
    ev = latest("auth.2fa.failed")
    assert ev.actor == admin and ev.metadata["reason"] == "bad_otp"
    assert "000000" not in json.dumps(ev.metadata)


def test_user_update_event(admin_client, admin, student):
    admin_client.patch(f"/api/admin/students/{student.id}/", {"full_name": "Edited By Admin"}, format="json")
    ev = latest("user.updated")
    assert ev.actor == admin and ev.target_id == str(student.id)


def test_access_request_reject_revoke_events(student_client, admin_client, admin, student):
    course = Course.objects.create(title="Algebra", slug="algebra", status="published", created_by=admin)
    access_id = student_client.post("/api/student/access/", {"course": str(course.id)}, format="json").json()["data"]["id"]
    ev = latest("access.requested")
    assert ev.actor == student and ev.target_id == access_id and ev.metadata["course"] == str(course.id)

    admin_client.patch(f"/api/admin/students/access/{access_id}/", {"action": "reject"}, format="json")
    ev = latest("access.rejected")
    assert ev.actor == admin and ev.target_id == access_id and ev.metadata["student"] == str(student.id)

    student_client.post("/api/student/access/", {"course": str(course.id)}, format="json")  # re-request after rejection
    admin_client.patch(f"/api/admin/students/access/{access_id}/", {"action": "approve"}, format="json")
    admin_client.patch(f"/api/admin/students/access/{access_id}/", {"action": "revoke"}, format="json")
    ev = latest("access.revoked")
    assert ev.actor == admin and ev.target_id == access_id
    assert CourseAccess.objects.get(pk=access_id).revoked_by == admin


def test_resource_update_event(admin_client, admin):
    course = Course.objects.create(title="Chem", slug="chem", status="published", created_by=admin)
    rid = upload(admin_client, course, data=make_pdf_bytes()).json()["data"]["id"]
    admin_client.patch(f"/api/admin/course/resources/{rid}/", {"title": "Renamed"}, format="json")
    ev = latest("resource.updated")
    assert ev.actor == admin and ev.target_id == rid and ev.metadata["changed_fields"] == ["title"]


def test_payment_cancelled_event(student_client, student, admin, settings):
    from unittest import mock

    settings.STRIPE_SECRET_KEY = "sk_test_dummy_for_pytest"
    settings.STRIPE_WEBHOOK_SECRET = WEBHOOK_SECRET
    course = Course.objects.create(title="Paid", slug="paid", status="published", access_mode="payment_required", price_amount="10.00", created_by=admin)
    from .conftest import approve_payment

    approve_payment(student, course)
    with mock.patch("payments.services.stripe.checkout.Session.create", return_value={"id": "cs_test_cancel", "url": "https://checkout.stripe.test/x"}):
        pid = student_client.post("/api/student/payment/create-checkout/", {"course": str(course.id)}, format="json").json()["data"]["id"]
    payment = Payment.objects.get(pk=pid)
    send_event("checkout.session.expired", session_obj(payment, payment_status="unpaid"))
    ev = latest("payment.cancelled")
    assert ev.target_id == pid and ev.actor is None and ev.actor_email == "stripe"


def test_every_emitted_audit_action_is_asserted_somewhere():
    """Guard: a new Actions constant that is emitted but never asserted in tests fails here."""
    import re
    from pathlib import Path

    backend = Path(__file__).resolve().parent.parent
    models_src = (backend / "audit" / "models.py").read_text(encoding="utf-8")
    block = models_src.split("class Actions")[1].split("class ImmutableQuerySet")[0]
    actions = re.findall(r'^\s+[A-Z_0-9]+ = "([a-z0-9_.]+)"', block, flags=re.M)
    tests_src = "\n".join(p.read_text(encoding="utf-8") for p in (backend / "tests").glob("test_*.py"))
    untested = [a for a in actions if f'"{a}"' not in tests_src and f"'{a}'" not in tests_src]
    assert untested == []
