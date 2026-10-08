"""Backend behaviour needed to serve a browser frontend on another PC through a tunnel (ngrok)."""
import pytest
from corsheaders.defaults import default_headers
from rest_framework.test import APIClient

from .conftest import PASSWORD, login_student
from .test_config import settings_probe

pytestmark = pytest.mark.django_db

FRIEND = "http://localhost:3000"
LOGIN = "/api/accounts/login/"


def preflight(origin, headers="authorization,content-type,ngrok-skip-browser-warning", host=None):
    extra = {"HTTP_HOST": host} if host else {}
    return APIClient().options(
        LOGIN, HTTP_ORIGIN=origin, HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS=headers, **extra,
    )


class TestCorsForAFrontendOnAnotherPc:
    @pytest.fixture(autouse=True)
    def cors(self, settings):
        settings.CORS_ALLOWED_ORIGINS = [FRIEND]
        settings.CORS_ALLOW_HEADERS = (*default_headers, "ngrok-skip-browser-warning")

    def test_preflight_allows_bearer_jwt_and_the_ngrok_header(self):
        res = preflight(FRIEND)
        allowed = res["Access-Control-Allow-Headers"].lower()
        assert res.status_code == 200 and res["Access-Control-Allow-Origin"] == FRIEND
        assert "authorization" in allowed and "content-type" in allowed and "ngrok-skip-browser-warning" in allowed

    def test_only_the_configured_origin_is_allowed(self):
        for origin in ("http://evil.example.com", "https://abc123.ngrok-free.app", "http://localhost:4000"):
            assert "Access-Control-Allow-Origin" not in preflight(origin)

    def test_never_a_wildcard(self):
        assert preflight(FRIEND)["Access-Control-Allow-Origin"] != "*"

    def test_actual_request_carries_the_cors_header(self):
        res = APIClient().post(LOGIN, {"email": "x@example.com", "password": "nope"}, format="json", HTTP_ORIGIN=FRIEND)
        assert res.status_code in (400, 401) and res["Access-Control-Allow-Origin"] == FRIEND
        res = APIClient().post(LOGIN, {"email": "x@example.com", "password": "nope"}, format="json", HTTP_ORIGIN="http://evil.example.com")
        assert "Access-Control-Allow-Origin" not in res

    def test_unlisted_header_is_not_allowed(self):
        assert "x-secret-thing" not in preflight(FRIEND, headers="x-secret-thing")["Access-Control-Allow-Headers"].lower()


class TestSettingsWiring:
    def test_extra_header_comes_from_the_environment(self):
        code = "from django.conf import settings as s; print('ngrok-skip-browser-warning' in s.CORS_ALLOW_HEADERS, 'authorization' in s.CORS_ALLOW_HEADERS)"
        on = settings_probe({"CORS_EXTRA_ALLOW_HEADERS": "ngrok-skip-browser-warning"}, code)
        off = settings_probe({"CORS_EXTRA_ALLOW_HEADERS": ""}, code)  # explicit: the real .env sets it
        assert on.returncode == 0 and on.stdout.strip() == "True True", on.stderr
        assert off.stdout.strip() == "False True"  # default: only the standard headers

    def test_hosts_and_origins_come_from_the_environment(self):
        code = "from django.conf import settings as s; print(s.ALLOWED_HOSTS, s.CORS_ALLOWED_ORIGINS, s.TRUST_PROXY_HEADERS)"
        res = settings_probe(
            {"DEBUG": "True", "DATABASE_URL": "sqlite:///:memory:", "ALLOWED_HOSTS": "localhost,.ngrok-free.app",
             "CORS_ALLOWED_ORIGINS": "http://localhost:3000", "TRUST_PROXY_HEADERS": "True"}, code,
        )
        assert res.stdout.strip() == "['localhost', '.ngrok-free.app'] ['http://localhost:3000'] True", res.stderr

    def test_no_wildcard_cors_in_source(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parent.parent / "config" / "settings.py").read_text(encoding="utf-8")
        assert "CORS_ALLOW_ALL_ORIGINS" not in source and "CSRF_TRUSTED_ORIGINS" not in source


class TestHostValidation:
    def test_ngrok_suffix_is_accepted_and_other_hosts_are_not(self, settings):
        settings.ALLOWED_HOSTS = ["localhost", ".ngrok-free.app"]
        ok = APIClient().get("/api/student/profile/", HTTP_HOST="abc123.ngrok-free.app")
        assert ok.status_code == 401  # reached the API (not logged in)
        for host in ("evil.example.com", "abc123.ngrok-free.app.evil.com"):
            assert APIClient().get("/api/student/profile/", HTTP_HOST=host).status_code == 400


class TestRealClientIpBehindTheTunnel:
    def fail(self, email, forwarded, times):
        for _ in range(times):
            APIClient().post(LOGIN, {"email": email, "password": "wrong-Password-1"}, format="json", HTTP_X_FORWARDED_FOR=forwarded)

    def test_with_proxy_headers_visitors_are_told_apart(self, student, settings):
        settings.TRUST_PROXY_HEADERS = True
        self.fail(student.email, "203.0.113.5", settings.LOGIN_MAX_ATTEMPTS)
        attacker = APIClient().post(LOGIN, {"email": student.email, "password": PASSWORD}, format="json", HTTP_X_FORWARDED_FOR="203.0.113.5")
        owner = APIClient().post(LOGIN, {"email": student.email, "password": PASSWORD}, format="json", HTTP_X_FORWARDED_FOR="198.51.100.7")
        assert attacker.status_code == 429 and owner.status_code == 200

    def test_without_it_the_header_is_ignored_so_it_cannot_be_spoofed(self, student, settings):
        settings.TRUST_PROXY_HEADERS = False
        self.fail(student.email, "203.0.113.5", settings.LOGIN_MAX_ATTEMPTS)
        spoofed = APIClient().post(LOGIN, {"email": student.email, "password": PASSWORD}, format="json", HTTP_X_FORWARDED_FOR="198.51.100.7")
        assert spoofed.status_code == 429  # same real address, the forged header changed nothing


class TestBearerJwtThroughAProxy:
    def test_bearer_token_works_with_forwarded_headers(self, student, settings):
        settings.TRUST_PROXY_HEADERS = True
        tokens = login_student(APIClient(), student.email).json()["data"]["tokens"]
        res = APIClient().get(
            "/api/student/profile/", HTTP_AUTHORIZATION=f"Bearer {tokens['access']}", HTTP_ORIGIN=FRIEND,
            HTTP_X_FORWARDED_FOR="203.0.113.5", HTTP_X_FORWARDED_PROTO="https",
        )
        assert res.status_code == 200 and res.json()["data"]["email"] == student.email
