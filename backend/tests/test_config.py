import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
from cryptography.fernet import Fernet
from django.db.utils import OperationalError
from redis.exceptions import ConnectionError as RedisConnectionError

from accounts import crypto

from .conftest import auth_client

BACKEND = Path(__file__).resolve().parent.parent


def settings_probe(extra_env, code):
    """Evaluate config.settings in a clean interpreter so environment-dependent branches can be exercised."""
    env = {k: v for k, v in os.environ.items() if k not in {"DATABASE_URL", "DEBUG", "FIELD_ENCRYPTION_KEY", "DB_CONNECT_TIMEOUT"}}
    env.update(
        SECRET_KEY="s" * 50, JWT_SIGNING_KEY="j" * 50, REDIS_URL="locmemcache://",
        DJANGO_SETTINGS_MODULE="config.settings", **extra_env,
    )
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=60)


POSTGRES = "postgres://user:pw@localhost:5432/eduvault"


class TestDatabaseConfiguration:
    def test_postgres_gets_fast_connect_timeout(self):
        r = settings_probe({"DATABASE_URL": POSTGRES, "DEBUG": "True"}, "from django.conf import settings as s; d=s.DATABASES['default']; print(d['ENGINE'], d['OPTIONS']['connect_timeout'], d['HOST'], d['PORT'], d['NAME'])")
        assert r.returncode == 0, r.stderr
        assert r.stdout.split() == ["django.db.backends.postgresql", "10", "localhost", "5432", "eduvault"]

    def test_connect_timeout_is_configurable(self):
        r = settings_probe({"DATABASE_URL": POSTGRES, "DEBUG": "True", "DB_CONNECT_TIMEOUT": "3"}, "from django.conf import settings as s; print(s.DATABASES['default']['OPTIONS']['connect_timeout'])")
        assert r.stdout.strip() == "3"

    def test_sqlite_url_is_not_given_postgres_options(self):
        r = settings_probe({"DATABASE_URL": "sqlite:///:memory:", "DEBUG": "True"}, "from django.conf import settings as s; print('OPTIONS' in s.DATABASES['default'] and 'connect_timeout' in s.DATABASES['default']['OPTIONS'])")
        assert r.stdout.strip() == "False"

    def test_no_database_url_means_startup_failure_not_a_silent_fallback(self):
        # Run from a directory whose .env has no DATABASE_URL by hiding the real one via an explicit empty-file copy.
        r = settings_probe({"DEBUG": "True", "DATABASE_URL": ""}, "from django.conf import settings as s; s.DATABASES")
        assert r.returncode != 0 and "sqlite" not in r.stdout.lower()


class TestEncryptionKeyIsRequiredInProduction:
    def test_missing_key_refuses_to_start_when_debug_off(self):
        r = settings_probe({"DATABASE_URL": POSTGRES, "DEBUG": "False"}, "from django.conf import settings as s; s.SECRET_KEY")
        assert r.returncode != 0 and "FIELD_ENCRYPTION_KEY is required" in r.stderr

    def test_starts_with_key_when_debug_off(self):
        r = settings_probe({"DATABASE_URL": POSTGRES, "DEBUG": "False", "FIELD_ENCRYPTION_KEY": Fernet.generate_key().decode()}, "from django.conf import settings as s; print(s.DEBUG)")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == "False"

    def test_dev_may_omit_key(self):
        r = settings_probe({"DATABASE_URL": POSTGRES, "DEBUG": "True"}, "from django.conf import settings as s; print(s.DEBUG)")
        assert r.returncode == 0, r.stderr

    def test_env_example_documents_the_key_without_a_value(self):
        lines = (BACKEND / ".env.example").read_text(encoding="utf-8").splitlines()
        assert "FIELD_ENCRYPTION_KEY=" in lines
        assert any("REQUIRED when DEBUG=False" in line for line in lines)


class TestKeyRotation:
    def test_totp_ciphertext_survives_secret_key_rotation(self, settings):
        settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
        token = crypto.encrypt("JBSWY3DPEHPK3PXP")
        settings.SECRET_KEY = "a-completely-different-secret-key-after-rotation-0123456789"
        assert crypto.decrypt(token) == "JBSWY3DPEHPK3PXP"

    def test_keyed_hashes_survive_secret_key_rotation(self, settings):
        settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
        before = crypto.keyed_hash("backup-code", "abcde12345")
        settings.SECRET_KEY = "another-rotated-secret-key-0123456789-0123456789-0123456789"
        assert crypto.keyed_hash("backup-code", "abcde12345") == before

    def test_changing_the_encryption_key_does_invalidate(self, settings):
        settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
        token = crypto.encrypt("secret")
        settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
        with pytest.raises(ValueError):
            crypto.decrypt(token)

    def test_hash_purposes_are_separated(self, settings):
        settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
        assert crypto.keyed_hash("backup-code", "x") != crypto.keyed_hash("other", "x")


@pytest.mark.django_db
class TestDependencyOutagesAreReportedCleanly:
    def test_database_outage_is_503_without_details(self, student_client):
        with mock.patch("accounts.views.s.UserSerializer", side_effect=OperationalError("connection to server at 10.0.0.5 password=hunter2 failed")):
            res = student_client.get("/api/accounts/me/")
        assert res.status_code == 503 and res.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
        text = res.content.decode()
        assert "10.0.0.5" not in text and "hunter2" not in text

    def test_redis_outage_is_503_and_not_a_silent_fallback(self, student_client):
        with mock.patch("accounts.services.touch_session", side_effect=RedisConnectionError("redis://:secret@cache:6379 refused")):
            res = student_client.get("/api/accounts/me/")
        assert res.status_code == 503 and res.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
        assert "secret" not in res.content.decode()

    def test_other_errors_still_500(self, student_client):
        with mock.patch("accounts.views.s.UserSerializer", side_effect=RuntimeError("bug")):
            assert student_client.get("/api/accounts/me/").status_code == 500


@pytest.mark.django_db
class TestRealRedisOutage:
    """Uses the real django-redis backend against a closed port (nothing is mocked)."""

    CLOSED = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": "redis://:s3cr3t-redis-pw@127.0.0.1:6399/1",
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient", "SOCKET_CONNECT_TIMEOUT": 2, "SOCKET_TIMEOUT": 2},
        }
    }

    def test_login_returns_sanitized_503(self, settings, student):
        from rest_framework.test import APIClient

        settings.CACHES = self.CLOSED
        res = APIClient().post("/api/accounts/login/", {"email": student.email, "password": "Str0ng-Passw0rd!x"}, format="json")
        text = res.content.decode()
        assert res.status_code == 503 and res.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
        assert res.json()["success"] is False
        for leak in ("s3cr3t-redis-pw", "6399", "127.0.0.1", "redis://", "Traceback", "django_redis"):
            assert leak not in text

    def test_authenticated_request_returns_503_not_a_silent_pass(self, settings, student):
        from rest_framework.test import APIClient

        c = APIClient()
        tokens = c.post("/api/accounts/login/", {"email": student.email, "password": "Str0ng-Passw0rd!x"}, format="json").json()["data"]["tokens"]
        auth_client(c, tokens)
        settings.CACHES = self.CLOSED  # Redis goes away after the user logged in
        res = c.get("/api/accounts/me/")
        assert res.status_code == 503 and res.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
