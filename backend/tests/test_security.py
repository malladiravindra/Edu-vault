import re
from pathlib import Path
from unittest import mock

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

BACKEND = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.django_db

UUID = "00000000-0000-0000-0000-000000000000"
PUBLIC_ROUTES = {
    "api/student/register/", "api/student/register/send-otp/", "api/student/register/verify-otp/", "api/student/login/",
    "api/accounts/register/", "api/accounts/register/send-otp/", "api/accounts/register/verify-otp/", "api/accounts/login/", "api/accounts/refresh/", "api/accounts/forgot-password/",
    "api/accounts/forgot-password/verify/", "api/accounts/reset-password/", "api/admin/login/",
    "api/admin/login/2fa/verify/",
    "api/payment/stripe/webhook/",
}


def all_routes():
    def walk(patterns, prefix=""):
        for p in patterns:
            route = prefix + str(p.pattern)
            if isinstance(p, URLResolver):
                yield from walk(p.url_patterns, route)
            elif isinstance(p, URLPattern):
                yield route, p

    for route, pattern in walk(get_resolver().url_patterns):
        if route.startswith("admin/"):  # Django's own admin site (tests/test_django_admin.py), not an API route
            continue
        concrete = re.sub(r"<uuid:\w+>", UUID, route)
        concrete = re.sub(r"<int:\w+>", "1", concrete)
        yield route, concrete


ROUTES = sorted(set(all_routes()))


def test_routes_discovered():
    assert len(ROUTES) >= 60


@pytest.mark.parametrize("route,url", ROUTES)
def test_protected_routes_reject_anonymous(route, url):
    if route in PUBLIC_ROUTES:
        pytest.skip("public by design")
    c = APIClient()
    for method in ("get", "post", "patch", "delete"):
        res = getattr(c, method)("/" + url, {}, format="json")
        assert res.status_code in (401, 405), (method, url, res.status_code)


@pytest.mark.parametrize("route,url", [r for r in ROUTES if r[0].startswith("api/admin/") and r[0] not in PUBLIC_ROUTES])
def test_every_admin_route_rejects_students(route, url, student_client):
    for method in ("get", "post", "patch", "delete"):
        res = getattr(student_client, method)("/" + url, {}, format="json")
        assert res.status_code in (403, 405), (method, url, res.status_code)


@pytest.mark.parametrize("route,url", [r for r in ROUTES if r[0].startswith(("api/viewing/", "api/student/", "api/course/")) and r[0] not in PUBLIC_ROUTES])
def test_student_routes_reject_admins(route, url, admin_client):
    res = admin_client.get("/" + url)
    assert res.status_code in (403, 404), (url, res.status_code)


def test_admin_apis_unreachable_before_second_factor(admin):
    """A password alone must never yield tokens for admin APIs."""
    c = APIClient()
    res = c.post("/api/admin/login/", {"email": admin.email, "password": "Str0ng-Passw0rd!x"}, format="json")
    data = res.json()["data"]
    assert "tokens" not in data and "access" not in str(data)
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {data['challenge_token']}")  # a challenge is not an access token
    assert c.get("/api/admin/students/").status_code == 401


def test_admin_cannot_use_student_login_endpoint(admin):
    res = APIClient().post("/api/accounts/login/", {"email": admin.email, "password": "Str0ng-Passw0rd!x"}, format="json")
    assert res.status_code == 401 and "tokens" not in res.content.decode()


def test_refresh_token_is_not_an_access_token(client, student):
    tokens = client.post("/api/accounts/login/", {"email": student.email, "password": "Str0ng-Passw0rd!x"}, format="json").json()["data"]["tokens"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['refresh']}")
    assert client.get("/api/accounts/me/").status_code == 401


class TestCodebaseRules:
    SOURCE = [p for p in BACKEND.rglob("*.py") if ".venv" not in p.parts and "migrations" not in p.parts and "tests" not in p.parts]

    def test_no_viewsets_or_routers(self):
        banned = re.compile(r"\b(ViewSet|ModelViewSet|GenericViewSet|ReadOnlyModelViewSet|DefaultRouter|SimpleRouter)\b|router\w*\.register\(")
        offenders = [str(p) for p in self.SOURCE if banned.search(p.read_text(encoding="utf-8"))]
        assert offenders == []

    def test_no_test_py_file(self):
        assert not [p for p in BACKEND.rglob("test.py") if ".venv" not in p.parts]

    def test_single_settings_module(self):
        assert (BACKEND / "config" / "settings.py").exists() and not (BACKEND / "config" / "settings").exists()
        assert not (BACKEND / "config" / "settings_test.py").exists()

    def test_no_hardcoded_secrets_in_source(self):
        pattern = re.compile(r"(sk_live_|sk_test_|whsec_|AKIA[0-9A-Z]{12,}|-----BEGIN [A-Z ]*PRIVATE KEY)")
        offenders = [str(p) for p in self.SOURCE if pattern.search(p.read_text(encoding="utf-8"))]
        assert offenders == []

    def test_env_is_gitignored_and_example_has_no_real_values(self):
        assert ".env" in (BACKEND / ".gitignore").read_text().splitlines()
        example = (BACKEND / ".env.example").read_text()
        assert "CHANGE_ME" not in example and not re.search(r"sk_(live|test)_\w{6,}", example)


class TestNoRawPdfExposure:
    def test_storage_key_never_serialized(self):
        from resources.serializers import AdminResourceSerializer
        from viewing.serializers import ViewerResourceSerializer

        assert "storage_key" not in AdminResourceSerializer.Meta.fields
        assert "storage_key" not in ViewerResourceSerializer.Meta.fields

    def test_no_media_or_static_routes(self):
        assert not [r for r, _ in ROUTES if r.startswith(("media", "static", "api/media", "api/files"))]

    def test_original_pdf_bytes_never_in_viewer_response(self, student_client, student, admin, admin_client):
        from access.services import grant_course_access
        from courses.models import Course
        from resources.models import Resource

        from .test_resources import make_pdf_bytes, upload

        course = Course.objects.create(title="Sec", slug="sec", status="published", created_by=admin)
        rid = upload(admin_client, course, data=make_pdf_bytes()).json()["data"]["id"]
        admin_client.post(f"/api/admin/course/resources/{rid}/validate/")
        admin_client.post(f"/api/admin/course/resources/{rid}/publish/")
        grant_course_access(student=student, course=course, source="admin_approval", actor=admin)
        body = student_client.get(f"/api/student/viewing/resources/{rid}/pages/1/").content
        assert b"%PDF" not in body and Resource.objects.get(pk=rid).storage_key.encode() not in body


class TestTransportAndErrors:
    def test_security_headers(self, client):
        res = client.get("/api/accounts/me/")
        assert res["X-Content-Type-Options"] == "nosniff" and res["X-Frame-Options"] == "DENY"

    def test_cors_only_for_allowed_origins(self, client, settings):
        allowed = settings.CORS_ALLOWED_ORIGINS[0] if settings.CORS_ALLOWED_ORIGINS else None
        bad = client.get("/api/accounts/me/", HTTP_ORIGIN="https://evil.example")
        assert "Access-Control-Allow-Origin" not in bad
        if allowed:
            good = client.get("/api/accounts/me/", HTTP_ORIGIN=allowed)
            assert good["Access-Control-Allow-Origin"] == allowed

    def test_unhandled_error_does_not_leak(self, student_client):
        with mock.patch("accounts.views.s.UserSerializer", side_effect=RuntimeError("SELECT * FROM secrets /tmp/x.py")):
            res = student_client.get("/api/accounts/me/")
        text = res.content.decode()
        assert res.status_code == 500 and res.json()["error"]["code"] == "INTERNAL_ERROR"
        assert "SELECT" not in text and "Traceback" not in text and ".py" not in text

    def test_all_errors_use_envelope(self, client):
        for res in (client.get("/api/nope/"), client.post("/api/accounts/login/", {}, format="json"), client.get("/api/accounts/me/")):
            body = res.json() if res["Content-Type"].startswith("application/json") else None
            if body is not None:
                assert body["success"] is False and {"code", "message", "details"} <= set(body["error"])

    def test_malformed_json_is_clean_400(self, client):
        res = client.post("/api/accounts/login/", data="{bad json", content_type="application/json")
        assert res.status_code == 400 and res.json()["error"]["code"] == "PARSE_ERROR"

    def test_wrong_content_type_rejected(self, client):
        res = client.post("/api/accounts/login/", data="email=a", content_type="text/plain")
        assert res.status_code == 415

    def test_debug_is_off_in_test_settings(self, settings):
        assert settings.DEBUG is False
