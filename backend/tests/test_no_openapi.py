"""drf-spectacular / Swagger / OpenAPI are gone; the API itself is unchanged."""
from pathlib import Path

import pytest
from django.urls import resolve
from rest_framework.test import APIClient

from .test_config import settings_probe

pytestmark = pytest.mark.django_db
BACKEND = Path(__file__).resolve().parent.parent

# Assembled from pieces so this file does not match its own search.
FORBIDDEN = [
    "drf" + "_spectacular", "drf" + "-spectacular", "extend" + "_schema", "Open" + "Api", "Swagger" + "UI", "Spectacular",
    "Auto" + "Schema", "SPECTACULAR" + "_SETTINGS", "API_DOCS" + "_ENABLED",
]


class TestDocumentationRoutesAreGone:
    @pytest.mark.parametrize("path", ["/api/schema/", "/api/docs/", "/api/redoc/", "/api/swagger/", "/api/openapi.json", "/api/openapi.yaml"])
    def test_404_for_everyone(self, path, admin_client, student_client):
        assert APIClient().get(path).status_code == 404
        assert student_client.get(path).status_code == 404
        assert admin_client.get(path).status_code == 404

    def test_unknown_routes_still_use_the_json_error_envelope(self, client):
        body = client.get("/api/docs/").json()
        assert body["success"] is False and set(body["error"]) == {"code", "message", "details"}


class TestNothingLeftInTheSource:
    def test_settings_have_no_documentation_configuration(self, settings):
        assert "drf" + "_spectacular" not in settings.INSTALLED_APPS
        assert not hasattr(settings, "SPECTACULAR" + "_SETTINGS") and not hasattr(settings, "API_DOCS" + "_ENABLED")
        assert "DEFAULT_SCHEMA_CLASS" not in settings.REST_FRAMEWORK

    def test_requirements_do_not_list_it(self):
        assert "spectacular" not in (BACKEND / "requirements.txt").read_text(encoding="utf-8").lower()

    def test_no_application_source_mentions_it(self):
        # Dated audit reports record what was true when written and are deliberately not rewritten.
        historical = {"empty.txt", "BACKEND_AUDIT.md"}
        hits = []
        for path in BACKEND.rglob("*"):
            parts = set(path.relative_to(BACKEND).parts)
            if not path.is_file() or path.name in historical or parts & {".venv", "__pycache__", "tests", "migrations"}:
                continue
            if path.suffix not in {".py", ".txt", ".md", ".ini", ".toml", ".cfg"} and path.name != ".env.example":
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            hits += [f"{path.relative_to(BACKEND)}: {word}" for word in FORBIDDEN if word in text]
        assert hits == []

    def test_the_project_boots_without_the_package_installed(self):
        code = (
            "import sys; sys.modules['drf' + '_spectacular'] = None\n"  # makes any import of it raise ImportError
            "import django; django.setup()\n"
            "from django.urls import get_resolver\n"
            "import config.urls\n"
            "from django.core.management import call_command; call_command('check')\n"
            "print('BOOT-OK', len(get_resolver().url_patterns))"
        )
        res = settings_probe({"DEBUG": "True", "DATABASE_URL": "sqlite:///:memory:"}, code)
        assert res.returncode == 0 and "BOOT-OK" in res.stdout, res.stderr[-600:]


class TestRealRoutesAreUntouched:
    @pytest.mark.parametrize(
        "path",
        [
            "/api/accounts/login/", "/api/accounts/register/", "/api/accounts/register/send-otp/", "/api/accounts/refresh/",
            "/api/admin/login/", "/api/admin/login/2fa/verify/", "/api/admin/profile/", "/api/admin/course/",
            "/api/admin/course/resources/", "/api/admin/students/", "/api/admin/students/approval-requests/",
            "/api/admin/students/access/", "/api/admin/students/payments/", "/api/admin/reports/dashboard/",
            "/api/admin/audit-logs/", "/api/admin/settings/", "/api/admin/notifications/",
            "/api/student/dashboard/", "/api/student/profile/", "/api/student/settings/", "/api/student/courses/",
            "/api/student/course/", "/api/student/access/", "/api/student/payment-requests/", "/api/student/payments/",
            "/api/student/payment/create-checkout/", "/api/student/learning-history/", "/api/student/notifications/",
            "/api/payment/stripe/webhook/",
        ],
    )
    def test_route_resolves_to_an_apiview(self, path):
        from rest_framework.views import APIView

        view_class = resolve(path).func.view_class
        assert issubclass(view_class, APIView)
        assert not any(base.__name__.endswith(("ViewSet", "GenericViewSet")) for base in view_class.__mro__)
