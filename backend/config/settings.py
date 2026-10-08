from datetime import timedelta
from pathlib import Path

import environ
from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured

# --- Base / environment ---
BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env", overwrite=True)

# --- Security ---
SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
# Optional Fernet key for secrets at rest; derived from SECRET_KEY when empty (DEBUG only).
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", default="")
if not DEBUG and not FIELD_ENCRYPTION_KEY:
    raise ImproperlyConfigured(
        "FIELD_ENCRYPTION_KEY is required when DEBUG is off. Generate one with: "
        'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
    )

# --- Applications ---
INSTALLED_APPS = [
    "accounts.admin_config.EduVaultAdminConfig",  # django.contrib.admin with role/status-checked password sign-in; /admin/ (the EduVault admin API is /api/admin/)
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "accounts",
    "audit",
    "courses",
    "access",
    "resources",
    "viewing",
    "payments",
    "notifications",
    "platform_settings",
]

# --- Middleware (order matters) ---
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "core.middleware.AdminSiteHostGuardMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# --- Django core ---
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

TEMPLATES = [  # used by the Django admin site only; the API returns JSON
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

# --- Database (PostgreSQL) ---
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
if "postgresql" in DATABASES["default"]["ENGINE"]:
    # Report an unreachable database in seconds instead of psycopg's 130 s default.
    DATABASES["default"].setdefault("OPTIONS", {})["connect_timeout"] = env.int("DB_CONNECT_TIMEOUT", default=10)

# --- Cache (Redis) ---
CACHES = {"default": env.cache("REDIS_URL")}

# --- Authentication ---
AUTH_USER_MODEL = "accounts.User"
PASSWORD_HASHERS = [
    env("PASSWORD_HASHER", default="django.contrib.auth.hashers.Argon2PasswordHasher"),
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
# Django admin site (/admin/): e-mail + password with a normal Django session (accounts/admin_site.py), served only on these hosts, 404 elsewhere.
# The admin API (/api/admin/) is separate: password + e-mailed code + JWT.
LOGIN_REDIRECT_URL = "/admin/"  # Django admin sign-in without a ?next= lands in the admin (the only session login)
DJANGO_ADMIN_ALLOWED_HOSTS = env.list("DJANGO_ADMIN_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "[::1]"])
SESSION_COOKIE_AGE = env.int("DJANGO_ADMIN_SESSION_SECONDS", default=8 * 60 * 60)
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# --- REST framework ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["accounts.authentication.SessionAwareJWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", default="60/minute"),
        "user": env("THROTTLE_USER", default="600/minute"),
        "register": env("THROTTLE_REGISTER", default="10/hour"),
        "otp": env("THROTTLE_OTP", default="10/hour"),
        "otp_verify": env("THROTTLE_OTP_VERIFY", default="30/hour"),
        "login": env("THROTTLE_LOGIN", default="20/minute"),
        "two_factor": env("THROTTLE_TWO_FACTOR", default="20/minute"),
        "password_reset": env("THROTTLE_PASSWORD_RESET", default="5/hour"),
        "viewer": env("THROTTLE_VIEWER", default="180/minute"),
        "checkout": env("THROTTLE_CHECKOUT", default="20/hour"),
        "webhook": env("THROTTLE_WEBHOOK", default="600/minute"),
    },
}

# --- JWT ---
JWT_SIGNING_KEY = env("JWT_SIGNING_KEY")
if not DEBUG and (len(JWT_SIGNING_KEY) < 32 or JWT_SIGNING_KEY == SECRET_KEY):
    raise ImproperlyConfigured("JWT_SIGNING_KEY must be at least 32 characters and different from SECRET_KEY.")
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("ACCESS_TOKEN_MINUTES", default=15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("REFRESH_TOKEN_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "SIGNING_KEY": JWT_SIGNING_KEY,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# --- CORS ---
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
# e.g. CORS_EXTRA_ALLOW_HEADERS=ngrok-skip-browser-warning when testing through an ngrok tunnel.
CORS_ALLOW_HEADERS = (*default_headers, *env.list("CORS_EXTRA_ALLOW_HEADERS", default=[]))

# --- EduVault policies ---
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:5173")
TRUST_PROXY_HEADERS = env.bool("TRUST_PROXY_HEADERS", default=False)

# Platform settings may override some of these at runtime (platform_settings app).
SESSION_INACTIVITY_SECONDS = env.int("SESSION_INACTIVITY_SECONDS", default=1800)
LOGIN_MAX_ATTEMPTS = env.int("LOGIN_MAX_ATTEMPTS", default=5)
LOGIN_LOCKOUT_SECONDS = env.int("LOGIN_LOCKOUT_SECONDS", default=900)
PASSWORD_MIN_LENGTH = env.int("PASSWORD_MIN_LENGTH", default=10)
REGISTRATION_REQUIRES_APPROVAL = env.bool("REGISTRATION_REQUIRES_APPROVAL", default=True)
EMAIL_NOTIFICATIONS_ENABLED = env.bool("EMAIL_NOTIFICATIONS_ENABLED", default=True)
PAYMENTS_ENABLED = env.bool("PAYMENTS_ENABLED", default=True)

OTP_EXPIRY_SECONDS = env.int("OTP_EXPIRY_SECONDS", default=600)
OTP_MAX_ATTEMPTS = env.int("OTP_MAX_ATTEMPTS", default=5)
OTP_RESEND_COOLDOWN_SECONDS = env.int("OTP_RESEND_COOLDOWN_SECONDS", default=60)  # 0 disables
REGISTRATION_VERIFICATION_SECONDS = env.int("REGISTRATION_VERIFICATION_SECONDS", default=1800)

# Fixed security policy, not environment-specific.
TWO_FACTOR_CHALLENGE_SECONDS = 300
PASSWORD_RESET_TOKEN_SECONDS = 900
# API admin sign-in: password, then a 6-digit code e-mailed to the admin. Valid for 5 minutes (300s).
ADMIN_LOGIN_OTP_SECONDS = env.int("ADMIN_LOGIN_OTP_SECONDS", default=300)
ADMIN_LOGIN_OTP_MAX_ATTEMPTS = env.int("ADMIN_LOGIN_OTP_MAX_ATTEMPTS", default=3)
ADMIN_LOGIN_OTP_RESEND_COOLDOWN_SECONDS = env.int("ADMIN_LOGIN_OTP_RESEND_COOLDOWN_SECONDS", default=10)
ADMIN_LOGIN_OTP_MAX_PER_HOUR = env.int("ADMIN_LOGIN_OTP_MAX_PER_HOUR", default=10)

# --- Email ---
# Settings reloaded with Gmail SMTP credentials
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=25)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@eduvault.local")

# --- Private PDF storage: "local" or "s3". Never exposed by URL; students get rendered pages only. ---
STORAGE_BACKEND = env("STORAGE_BACKEND", default="local")
PRIVATE_MEDIA_ROOT = env("PRIVATE_MEDIA_ROOT", default=str(BASE_DIR / "private_media"))
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")
AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default="") or None
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="") or None

# --- Resource / viewer limits ---
RESOURCE_MAX_BYTES = env.int("RESOURCE_MAX_BYTES", default=50 * 1024 * 1024)
RESOURCE_MAX_PAGES = env.int("RESOURCE_MAX_PAGES", default=2000)
VIEWER_RENDER_WIDTH = env.int("VIEWER_RENDER_WIDTH", default=1200)
VIEWER_JPEG_QUALITY = env.int("VIEWER_JPEG_QUALITY", default=80)
VIEWER_MAX_DURATION_SECONDS = 4 * 60 * 60
DATA_UPLOAD_MAX_MEMORY_SIZE = RESOURCE_MAX_BYTES + 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = RESOURCE_MAX_BYTES + 1024 * 1024

# --- Stripe: payment access is activated only from a verified webhook. ---
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")

# --- Security headers ---
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
if not DEBUG:
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# --- Logging ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
