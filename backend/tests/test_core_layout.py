"""The old common/ package is gone; its code lives in config/, accounts/ and core/ and behaves exactly as before."""
import importlib
import importlib.util
import json
import re
from pathlib import Path

import pytest
from django.conf import settings as dj_settings
from django.test import RequestFactory
from django.test.utils import override_settings
from rest_framework.test import APIClient

BACKEND = Path(__file__).resolve().parent.parent

# Values produced by the ORIGINAL common/crypto.py before it was moved (test-only keys, as in pytest.ini): the moved
# module must reproduce them exactly, otherwise stored TOTP seeds, backup-code hashes and OTP/replay hashes would stop
# verifying.
FIELD_KEY = "DjjEHBgBsvHmrGpSg7dVuFHrubFH-67Uq-j3zcZKdwE="
A_TOKEN = "gAAAAABqw4l2v87_6l5yzfKPwn0ZhOqwBhetoAyw35AtHUvIsYeIQ0il8U101Unsvi6xR_WtU3KPeMsTCAF9t7rKfY1TqcObmb9rC7xIUOeyHLvNP4QfgYo="
A_HASH_BACKUP = "7ce61141a88bab9b4461bdc8097c2fa6671311b08dffbfae978deb1751efeb7c"
A_HASH_TOTP = "7d5d54a0301fe09515342f88a185e6076d67c67431bcaf00ba82d9ba5031f9fa"
B_TOKEN = "gAAAAABqw4l2cKoVaH2vQep1-OtWXC6vvLB6inf05_L5R2d2uAD9Ex1qhZw-OO6pA_egKjq90eEBtGtSixM16TlKft3c6EmyL-WkWzLMwlpStbmOQHsn9Qs="
B_HASH_BACKUP = "72c06409f2d176b09adc99bbdd77f3c629f2d6fe497f5940595d55faf84990b2"
PLAINTEXT = "JBSWY3DPEHPK3PXP"


class TestNoCommonPackage:
    def test_the_directory_is_gone(self):
        assert not (BACKEND / "common").exists()

    def test_it_cannot_be_imported(self):
        assert importlib.util.find_spec("common") is None

    def test_no_source_file_refers_to_it(self):
        # Dated audit reports describe the old layout and are deliberately not rewritten.
        historical = {"COMMON_APP_AUDIT.txt", "COMMON_REMOVAL_FINAL.md", "BACKEND_AUDIT.md", "empty.txt"}
        pattern = re.compile(
            r"\bfrom common\b|\bimport common\b|[\"']common\.\w"
            r"|\bcommon/(admin|crypto|exceptions|middleware|pagination|permissions|responses|utils|views|__init__)\b"
        )
        hits = []
        for path in BACKEND.rglob("*"):
            parts = set(path.relative_to(BACKEND).parts)
            if not path.is_file() or path.name in historical or parts & {".venv", "__pycache__", "staticfiles"}:
                continue
            if path.suffix not in {".py", ".ini", ".toml", ".cfg", ".txt", ".md", ".json"} or path.name == "test_core_layout.py":
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if pattern.search(line):
                    hits.append(f"{path.relative_to(BACKEND)}:{number}: {line.strip()[:80]}")
        assert hits == []


class TestNewLocations:
    @pytest.mark.parametrize(
        "module,names",
        [
            ("core.middleware", ["AdminSiteHostGuardMiddleware"]),
            ("core.error_handlers", ["not_found", "server_error"]),
            ("accounts.crypto", ["encrypt", "decrypt", "keyed_hash"]),
            ("accounts.permissions", ["IsAdminRole", "IsStudentRole", "IsApprovedStudent"]),
            ("core.responses", ["success", "error_response"]),
            ("core.exceptions", ["ServiceError", "api_exception_handler"]),
            ("core.pagination", ["EnvelopePagination", "paginate"]),
            ("core.utils", ["get_client_ip", "query_value"]),
            ("core.admin", ["ReadOnlyModelAdmin"]),
        ],
    )
    def test_importable_with_the_same_names(self, module, names):
        loaded = importlib.import_module(module)
        assert all(hasattr(loaded, name) for name in names)

    def test_settings_and_urls_point_at_the_new_modules(self):
        assert "core.middleware.AdminSiteHostGuardMiddleware" in dj_settings.MIDDLEWARE
        assert dj_settings.REST_FRAMEWORK["EXCEPTION_HANDLER"] == "core.exceptions.api_exception_handler"
        from config import urls

        assert (urls.handler404, urls.handler500) == ("core.error_handlers.not_found", "core.error_handlers.server_error")

    def test_core_holds_only_shared_infrastructure(self):
        files = sorted(p.name for p in (BACKEND / "core").glob("*.py"))
        assert files == [
            "__init__.py", "admin.py", "error_handlers.py", "exceptions.py", "middleware.py", "pagination.py", "responses.py", "utils.py",
        ]

    def test_core_does_not_depend_on_any_domain_app(self):
        # shared infrastructure must not import the apps that use it (that would create circular dependencies)
        domain = r"(accounts|access|audit|courses|notifications|payments|platform_settings|portal|reports|resources|viewing)"
        for path in (BACKEND / "core").glob("*.py"):
            assert not re.search(rf"^\s*(from|import) {domain}\b", path.read_text(encoding="utf-8"), re.M), path.name


class TestCryptoIsByteIdentical:
    def test_explicit_key_known_answers(self):
        from accounts import crypto

        with override_settings(FIELD_ENCRYPTION_KEY=FIELD_KEY, SECRET_KEY="kat-secret-key-ignored-when-field-key-set-0123456789"):
            assert crypto.decrypt(A_TOKEN) == PLAINTEXT
            assert crypto.keyed_hash("backup-code", "abcde12345") == A_HASH_BACKUP
            assert crypto.keyed_hash("totp-replay", "123456") == A_HASH_TOTP

    def test_secret_key_derived_known_answers(self):
        from accounts import crypto

        with override_settings(FIELD_ENCRYPTION_KEY="", SECRET_KEY="kat-secret-key-for-derivation-0123456789-abcdef"):
            assert crypto.decrypt(B_TOKEN) == PLAINTEXT
            assert crypto.keyed_hash("backup-code", "abcde12345") == B_HASH_BACKUP

    def test_wrong_key_is_still_rejected(self):
        from accounts import crypto

        with override_settings(FIELD_ENCRYPTION_KEY=FIELD_KEY):
            with pytest.raises(ValueError):
                crypto.decrypt(B_TOKEN)

    def test_the_legacy_migration_uses_the_new_module(self):
        source = (BACKEND / "accounts" / "migrations" / "0002_encrypt_totp_secret.py").read_text(encoding="utf-8")
        assert "from accounts import crypto" in source


class TestBehaviourIsUnchanged:
    def test_envelope_helpers(self):
        from core.responses import error_response, success

        assert success({"a": 1}).data == {"success": True, "data": {"a": 1}, "meta": {}}
        assert error_response("X", "m", 400).data == {"success": False, "error": {"code": "X", "message": "m", "details": {}}}

    def test_error_handlers_are_the_json_envelope(self):
        from core.error_handlers import not_found, server_error

        request = RequestFactory().get("/x/")
        for handler, status, code in ((not_found, 404, "NOT_FOUND"), (server_error, 500, "INTERNAL_ERROR")):
            response = handler(request)
            assert response.status_code == status and json.loads(response.content)["error"]["code"] == code

    @pytest.mark.django_db
    def test_error_statuses_through_the_api(self, student_client, admin_client):
        anon = APIClient()
        assert anon.get("/api/student/profile/").status_code == 401  # NOT_AUTHENTICATED
        assert student_client.get("/api/admin/students/").status_code == 403  # PERMISSION_DENIED
        assert admin_client.get("/api/admin/students/00000000-0000-0000-0000-000000000000/").status_code == 404
        assert anon.post("/api/accounts/login/", {}, format="json").json()["error"]["code"] == "VALIDATION_ERROR"
        assert anon.get("/api/nope/").status_code == 404

    @pytest.mark.django_db
    def test_roles_still_separate(self, student_client, admin_client):
        assert admin_client.get("/api/admin/students/").status_code == 200
        assert student_client.get("/api/student/profile/").status_code == 200
        assert admin_client.get("/api/student/profile/").status_code == 403
