"""The public URL contract: every final URL, its methods, view, URL name and permissions.

`tests/url_inventory.json` was generated from the live URL configuration before the routes were moved into the apps'
own urls.py files. If an endpoint is added, removed or renamed ON PURPOSE, regenerate it:

    python manage.py shell -c "import json; from tests.test_url_structure_contract import live_inventory; \
        json.dump(live_inventory(), open('tests/url_inventory.json', 'w'), indent=1)"
"""
import json
from pathlib import Path

import pytest
from django.urls import get_resolver
from django.urls.resolvers import URLResolver
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db
CONTRACT = Path(__file__).resolve().parent / "url_inventory.json"


def live_inventory():
    def walk(res, prefix=""):
        for p in res.url_patterns:
            full = prefix + str(p.pattern)
            if isinstance(p, URLResolver):
                yield from walk(p, full)
            else:
                yield full, p

    rows = []
    for full, p in walk(get_resolver()):
        if full.startswith("admin/"):  # Django's own admin site
            continue
        cls = p.callback.cls
        methods = sorted(m.upper() for m in cls.http_method_names if m != "options" and hasattr(cls, m))
        perms = sorted(c.__name__ for c in (p.callback.initkwargs.get("permission_classes") or cls.permission_classes))
        rows.append({
            "url": "/" + full, "methods": methods, "view": cls.__name__, "view_module": cls.__module__, "name": p.name,
            "permissions": perms, "kwargs": sorted(p.callback.initkwargs.keys()),
        })
    return sorted(rows, key=lambda r: (r["url"], r["view"]))


class TestContract:
    def test_every_public_url_is_exactly_as_recorded(self):
        assert live_inventory() == json.loads(CONTRACT.read_text(encoding="utf-8"))

    # A view served on two URLs is deliberate and limited to: the notification views (student and admin portal, each with
    # its own permission), MeView (accounts/me/ and student/profile/) and the deprecated registrations/ alias.
    SHARED_ON_PURPOSE = {
        "MeView", "NotificationListView", "NotificationDetailView", "NotificationReadView", "NotificationReadAllView",
        "AdminRegistrationListView", "AdminRegistrationDetailView", "AdminRegistrationApproveView", "AdminRegistrationRejectView",
        # /api/student/{register,login}/ are canonical; /api/accounts/{register,login}/ are deprecated aliases (same views).
        "RegistrationSendOtpView", "RegistrationVerifyOtpView", "RegisterView", "LoginView",
    }

    def test_no_view_is_registered_twice_except_the_documented_cases(self):
        by_view, by_name = {}, {}
        for row in live_inventory():
            by_view.setdefault(row["view"], []).append(row["url"])
            by_name.setdefault(row["name"], []).append(row["url"])
        assert {k: v for k, v in by_name.items() if len(v) > 1} == {}  # no URL name is reused
        assert {k for k, v in by_view.items() if len(v) > 1} == self.SHARED_ON_PURPOSE
        assert all(len(v) == 2 for k, v in by_view.items() if k in self.SHARED_ON_PURPOSE)

    def test_every_route_is_an_apiview_with_explicit_path(self):
        from rest_framework.views import APIView

        for row in live_inventory():
            module = __import__(row["view_module"], fromlist=[row["view"]])
            assert issubclass(getattr(module, row["view"]), APIView), row

    def test_url_names_are_unique(self):
        names = [r["name"] for r in live_inventory()]
        assert len(names) == len(set(names))


class TestHighLevelEndpoints:
    def test_root_is_404(self):
        assert APIClient().get("/").status_code == 404
        assert APIClient().get("/api/").status_code == 404

    def test_django_admin_is_at_admin(self):
        res = APIClient().get("/admin/")
        assert res.status_code == 302 and res["Location"].startswith("/admin/login/")

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("/api/accounts/me/", 401), ("/api/accounts/login/", 405), ("/api/student/dashboard/", 401), ("/api/student/profile/", 401),
            ("/api/student/course/", 401), ("/api/student/courses/", 401), ("/api/student/access/", 401), ("/api/student/viewing/courses/00000000-0000-0000-0000-000000000000/resources/", 401),
            ("/api/student/payments/", 401), ("/api/student/payment-requests/", 401), ("/api/student/notifications/", 401), ("/api/student/learning-history/", 401),
            ("/api/payment/stripe/webhook/", 405),
            ("/api/admin/login/", 405), ("/api/admin/profile/", 401), ("/api/admin/course/", 401), ("/api/admin/course/resources/", 401),
            ("/api/admin/students/", 401), ("/api/admin/students/approval-requests/", 401), ("/api/admin/students/access/", 401),
            ("/api/admin/students/payments/", 401), ("/api/admin/reports/dashboard/", 401), ("/api/admin/audit-logs/", 401),
            ("/api/admin/settings/", 401), ("/api/admin/notifications/", 401),
        ],
    )
    def test_prefixes_answer_without_a_token(self, url, expected):
        assert APIClient().get(url).status_code == expected

    @pytest.mark.parametrize("url", ["/api/schema/", "/api/docs/", "/api/redoc/", "/api/course/", "/api/viewing/", "/api/notifications/", "/api/access/"])
    def test_removed_or_never_public_prefixes_stay_404(self, url):
        assert APIClient().get(url).status_code == 404
