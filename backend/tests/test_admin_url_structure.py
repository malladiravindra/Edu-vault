"""Admin URL structure: one prefix per include(), approval-requests, deprecated alias, authorization table."""
import collections
import pytest
from django.urls import get_resolver, resolve, reverse
from django.urls.resolvers import URLResolver
from rest_framework.test import APIClient

from accounts.models import User

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db

APPROVAL = "/api/admin/students/approval-requests/"
OLD = "/api/admin/students/registrations/"
NIL = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def pending(db):
    return User.objects.create_user("pending@example.com", PASSWORD, full_name="Pending One", status="pending")


def sibling_groups(resolver=None, path=""):
    """Yield (location, [prefixes of the include()s directly inside it]) for every nesting level."""
    resolver = resolver or get_resolver()
    includes = [p for p in resolver.url_patterns if isinstance(p, URLResolver)]
    if includes:
        yield path or "config/urls.py", [str(p.pattern) for p in includes]
    for p in includes:
        if str(p.pattern) != "admin/":  # Django's own admin site
            yield from sibling_groups(p, path + str(p.pattern))


class TestPrefixes:
    def test_config_urls_holds_only_high_level_prefixes(self):
        top = get_resolver().url_patterns
        assert all(isinstance(p, URLResolver) for p in top), "config/urls.py must not contain individual endpoints"
        assert [str(p.pattern) for p in top] == ["admin/", "api/accounts/", "api/payment/", "api/student/", "api/admin/"]

    def test_no_prefix_is_repeated_at_any_level(self):
        repeated = {
            where: [p for p, n in collections.Counter(prefixes).items() if n > 1]
            for where, prefixes in sibling_groups()
        }
        assert {k: v for k, v in repeated.items() if v} == {}

    def test_specific_prefixes_come_before_the_general_ones(self):
        for where, prefixes in sibling_groups():
            for index, general in enumerate(prefixes):
                later_specific = [p for p in prefixes[index + 1:] if p != general and p.startswith(general)]
                assert later_specific == [], (where, general, later_specific)

    @pytest.mark.parametrize(
        "path,view",
        [
            (APPROVAL, "AdminRegistrationListView"),
            (f"{APPROVAL}{NIL}/", "AdminRegistrationDetailView"),
            (f"{APPROVAL}{NIL}/approve/", "AdminRegistrationApproveView"),
            (f"{APPROVAL}{NIL}/reject/", "AdminRegistrationRejectView"),
            ("/api/admin/students/", "AdminUserListView"),
            (f"/api/admin/students/{NIL}/", "AdminUserDetailView"),
            (f"/api/admin/students/{NIL}/decision/", "AdminStudentDecisionView"),
            ("/api/admin/students/access/", "AdminAccessListView"),
            ("/api/admin/students/access/grant/", "AdminAccessGrantView"),
            ("/api/admin/students/payments/", "AdminPaymentListView"),
            ("/api/admin/course/", "AdminCourseListCreateView"),
            ("/api/admin/course/resources/", "AdminResourceListCreateView"),
            (f"/api/admin/course/{NIL}/", "AdminCourseDetailView"),
        ],
    )
    def test_nothing_is_shadowed(self, path, view):
        assert resolve(path).func.view_class.__name__ == view

    def test_url_names_are_unique(self):
        names = []

        def walk(res):
            for p in res.url_patterns:
                if str(p.pattern) == "admin/":
                    continue  # Django admin names live in the "admin" namespace
                walk(p) if isinstance(p, URLResolver) else names.append(p.name)

        walk(get_resolver())
        assert [n for n, c in collections.Counter(names).items() if c > 1] == []

    def test_reverse_gives_the_new_paths(self):
        assert reverse("admin-approval-request-list") == APPROVAL
        assert reverse("admin-access-list") == "/api/admin/students/access/"
        assert reverse("admin-resource-list") == "/api/admin/course/resources/"
        assert reverse("admin-payment-list") == "/api/admin/students/payments/"


class TestApprovalRequests:
    def test_lists_pending_by_default_and_filters(self, admin_client, pending, student):
        assert [r["email"] for r in admin_client.get(APPROVAL).json()["data"]] == [pending.email]
        assert admin_client.get(APPROVAL + "?status=all").json()["meta"]["count"] == 2
        assert admin_client.get(APPROVAL + "?status=active").json()["data"][0]["email"] == student.email

    def test_retrieve_includes_accesses_and_payments(self, admin_client, pending):
        data = admin_client.get(f"{APPROVAL}{pending.id}/").json()["data"]
        assert data["email"] == pending.email and data["accesses"] == [] and data["payments"] == []

    def test_approve_and_reject(self, admin_client, pending):
        other = User.objects.create_user("p2@example.com", PASSWORD, full_name="Two", status="pending")
        assert admin_client.post(f"{APPROVAL}{pending.id}/approve/").json()["data"]["status"] == "active"
        res = admin_client.post(f"{APPROVAL}{other.id}/reject/", {"reason": "Incomplete"}, format="json")
        assert res.json()["data"]["status"] == "rejected" and res.json()["data"]["rejection_reason"] == "Incomplete"
        assert admin_client.get(APPROVAL).json()["data"] == []  # nothing pending any more
        assert admin_client.post(f"{APPROVAL}{pending.id}/approve/").status_code == 409

    def test_admins_are_not_approval_requests(self, admin_client, admin):
        assert admin_client.get(f"{APPROVAL}{admin.id}/").status_code == 404


class TestDeprecatedAlias:
    def test_old_path_still_works_with_its_old_behaviour(self, admin_client, pending, student):
        assert admin_client.get(OLD).json()["meta"]["count"] == 2  # every student, as before
        assert admin_client.get(f"{OLD}{pending.id}/").status_code == 200
        assert admin_client.post(f"{OLD}{pending.id}/approve/").json()["data"]["status"] == "active"

    def test_alias_is_protected_like_the_new_path(self, student_client, pending):
        assert APIClient().get(OLD).status_code == 401
        assert student_client.get(OLD).status_code == 403
        assert student_client.post(f"{OLD}{pending.id}/approve/").status_code == 403



class TestAuthorizationTable:
    @pytest.mark.parametrize("method,suffix", [("get", ""), ("get", "{id}/"), ("post", "{id}/approve/"), ("post", "{id}/reject/")])
    def test_approval_routes(self, method, suffix, admin_client, student_client, pending):
        url = APPROVAL + suffix.format(id=pending.id)
        send = lambda c: getattr(c, method)(url, {}, format="json")  # noqa: E731
        assert send(APIClient()).status_code == 401
        assert send(student_client).status_code == 403
        assert send(admin_client).status_code == 200

    @pytest.mark.parametrize(
        "url",
        ["/api/admin/students/", "/api/admin/students/access/", "/api/admin/students/payments/",
         "/api/admin/course/", "/api/admin/course/resources/"],
    )
    def test_other_admin_routes(self, url, admin_client, student_client):
        assert APIClient().get(url).status_code == 401
        assert student_client.get(url).status_code == 403
        assert admin_client.get(url).status_code == 200
