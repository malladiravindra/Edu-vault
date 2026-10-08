import json

import pytest
from django.urls import Resolver404, get_resolver, resolve, reverse
from rest_framework.test import APIClient
from rest_framework.views import APIView

from core.error_handlers import server_error

from .test_security import ROUTES

pytestmark = pytest.mark.django_db

EXPECTED = {
    "auth-register": "/api/accounts/register/",
    "auth-login": "/api/accounts/login/",
    "auth-logout": "/api/accounts/logout/",
    "auth-refresh": "/api/accounts/refresh/",
    "auth-me": "/api/accounts/me/",
    "auth-forgot-password": "/api/accounts/forgot-password/",
    "auth-forgot-password-verify": "/api/accounts/forgot-password/verify/",
    "auth-reset-password": "/api/accounts/reset-password/",
    "auth-admin-login": "/api/admin/login/",
    "auth-2fa-verify": "/api/admin/login/2fa/verify/",
    "course-list": "/api/student/course/",
    "payment-create-checkout": "/api/student/payment/create-checkout/",
    "payment-stripe-webhook": "/api/payment/stripe/webhook/",
    "access-list": "/api/student/access/",
    "my-payments": "/api/student/payments/",
    "my-learning-history": "/api/student/learning-history/",
    "student-dashboard": "/api/student/dashboard/",
    "notification-list": "/api/student/notifications/",
    "admin-user-list": "/api/admin/students/",
    "admin-approval-request-list": "/api/admin/students/approval-requests/",
    "admin-course-list": "/api/admin/course/",
    "admin-access-list": "/api/admin/students/access/",
    "admin-resource-list": "/api/admin/course/resources/",
    "admin-payment-list": "/api/admin/students/payments/",
    "admin-settings": "/api/admin/settings/",
    "audit-list": "/api/admin/audit-logs/",
    "admin-dashboard": "/api/admin/reports/dashboard/",
}


class TestRootUrlIsUnmatched:
    """The project has no landing page: `/` must fall through to Django's own 404 handling."""

    def test_no_route_is_mounted_at_the_root(self):
        top_level = [str(p.pattern) for p in get_resolver().url_patterns]
        assert "" not in top_level and "api/" not in top_level
        assert all(p.startswith("api/") or p == "admin/" for p in top_level), top_level  # admin/ = Django admin site

    @pytest.mark.parametrize("path", ["/", "/api/"])
    def test_resolver_does_not_match(self, path):
        with pytest.raises(Resolver404):
            resolve(path)

    def test_root_shows_djangos_standard_debug_404_page(self, client, settings):
        settings.DEBUG = True
        res = client.get("/")
        page = res.content.decode()
        assert res.status_code == 404 and res["Content-Type"].startswith("text/html")
        assert "Page not found" in page and "(404)" in page and "Request Method:" in page and "Request URL:" in page
        assert "Using the URLconf defined in" in page and "config.urls" in page
        assert "Django tried these URL patterns" in page
        for prefix in ("api/accounts/", "api/student/", "api/admin/", "api/payment/"):
            assert prefix in page, prefix
        for custom in ("EduVault API running", "View as JSON", "endpoint_count", "Interactive docs"):
            assert custom not in page

    def test_root_is_a_json_404_when_debug_is_off(self, client, settings):
        assert settings.DEBUG is False
        res = client.get("/")
        assert res.status_code == 404 and res.json()["error"]["code"] == "NOT_FOUND"

    def test_nothing_redirects_the_root(self, client):
        for method in ("get", "post", "head"):
            res = getattr(client, method)("/")
            assert res.status_code == 404 and "Location" not in res


class TestUrlLayout:
    @pytest.mark.parametrize("name,url", sorted(EXPECTED.items()))
    def test_named_routes_reverse_to_the_expected_urls(self, name, url):
        assert reverse(name) == url
        assert resolve(url).url_name == name

    @pytest.mark.parametrize("route,url", ROUTES)
    def test_every_registered_route_resolves(self, route, url):
        match = resolve("/" + url)
        assert match.url_name and issubclass(match.func.view_class, APIView)

    @pytest.mark.parametrize("old", [
        "/api/auth/login/", "/api/auth/register/", "/api/auth/password-reset/", "/api/auth/admin/login/",
        "/api/courses/", "/api/access/", "/api/viewer/resources/00000000-0000-0000-0000-000000000000/",
        "/api/payments/create-checkout/", "/api/payments/stripe/webhook/", "/api/my/payments/",
        "/api/my/learning-history/", "/api/users/", "/api/audit/",
    ])
    def test_old_urls_are_gone_not_aliased(self, client, old):
        res = client.get(old)
        assert res.status_code == 404 and res.json()["error"]["code"] == "NOT_FOUND"

    def test_every_endpoint_is_an_apiview_never_a_viewset(self):
        def walk(patterns):
            for p in patterns:
                if str(p.pattern) == "admin/":
                    continue  # Django's own admin site is not an API view
                if hasattr(p, "url_patterns"):
                    yield from walk(p.url_patterns)
                else:
                    yield p

        callbacks = [p.callback for p in walk(get_resolver().url_patterns)]
        assert callbacks
        for cb in callbacks:
            view_class = getattr(cb, "view_class", None)
            assert view_class is not None and issubclass(view_class, APIView), cb
            assert not hasattr(cb, "actions"), f"{cb} looks like a ViewSet"

    def test_student_and_admin_areas_are_separate(self, client, student_client, admin_client):
        assert student_client.get("/api/student/dashboard/").status_code == 200
        assert student_client.get("/api/admin/reports/dashboard/").status_code == 403
        assert admin_client.get("/api/admin/reports/dashboard/").status_code == 200
        assert admin_client.get("/api/student/dashboard/").status_code == 403
        assert APIClient().get("/api/student/dashboard/").status_code == 401

    @pytest.mark.parametrize("url,expected", [
        ("/api/accounts/login/", 405), ("/api/accounts/register/", 405), ("/api/admin/login/", 405),
        ("/api/student/dashboard/", 401), ("/api/admin/students/", 401), ("/api/student/course/", 401),
        ("/api/student/viewing/courses/00000000-0000-0000-0000-000000000000/resources/", 401),
        ("/api/student/payment/create-checkout/", 401), ("/api/student/notifications/", 401),
    ])
    def test_existing_routes_reach_their_view(self, client, url, expected):
        """Public POST-only routes answer GET with 405; protected routes answer 401 (auth runs before the method check)."""
        assert client.get(url).status_code == expected

    def test_django_admin_site_is_separate_from_the_admin_api(self, client):
        from django.conf import settings

        from django.apps import apps

        assert apps.is_installed("django.contrib.admin")  # see tests/test_django_admin.py
        assert client.get("/admin/").status_code == 302 and "/admin/login/" in client.get("/admin/")["Location"]
        assert client.get("/api/admin/students/").status_code == 401  # the EduVault admin API is unchanged


class TestJsonErrors:
    def test_unknown_url_returns_json_envelope(self, client):
        res = client.get("/api/definitely/not/here/")
        assert res.status_code == 404 and res["Content-Type"].startswith("application/json")
        assert res.json() == {"success": False, "error": {"code": "NOT_FOUND", "message": "The requested resource was not found.", "details": {}}}

    def test_500_handler_is_json_and_generic(self, rf):
        res = server_error(rf.get("/boom/"))
        body = json.loads(res.content)
        assert res.status_code == 500 and body["error"]["code"] == "INTERNAL_ERROR" and "Traceback" not in res.content.decode()
