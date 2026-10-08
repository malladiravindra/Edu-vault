import re
import unicodedata
import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


_NAME_SEPARATORS = re.compile(r"[\W_]+")


def name_slug(value):
    """Normalised form of a name used to compare the name in a URL with the signed-in student's name: case-insensitive,
    punctuation and spaces collapse to single hyphens. It is only ever compared with the authenticated user's own name,
    never used to look anybody up (names are not unique)."""
    return _NAME_SEPARATORS.sub("-", unicodedata.normalize("NFKC", value or "").casefold()).strip("-")


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("role", User.Role.STUDENT)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.update(role=User.Role.ADMIN, is_staff=True, is_superuser=True)
        return self._create(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        ADMIN = "admin", "Admin"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending approval"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    # full_name is the display name (first + middle + last for self-registered students).
    full_name = models.CharField(max_length=150)
    first_name = models.CharField(max_length=100, blank=True)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    # Student preference: e-mail copies of notifications (security notices are always e-mailed).
    email_notifications = models.BooleanField(default=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.STUDENT)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    is_staff = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=500, blank=True)
    two_factor_enabled = models.BooleanField(default=False)
    totp_secret = models.CharField(max_length=255, blank=True)  # Fernet-encrypted
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["role", "status"])]

    @property
    def is_active(self):
        """Can authenticate. Pending/rejected students may sign in to see their registration status."""
        return self.status != self.Status.SUSPENDED

    @property
    def dashboard_name(self):
        """The name segment of this student's dashboard URL: the first name (full name as a fallback)."""
        return "-".join((self.first_name or self.full_name or "student").split())

    @property
    def is_approved(self):
        """Fully active account: allowed to use course content."""
        return self.status == self.Status.ACTIVE

    def __str__(self):
        return self.email


class _RoleManager(models.Manager):
    """Rows of the one accounts_user table that have a given role (used by the Django admin proxies only)."""

    def __init__(self, role):
        super().__init__()
        self._role = role

    def get_queryset(self):
        return super().get_queryset().filter(role=self._role)

    def deconstruct(self):  # never written to migrations (use_in_migrations stays False)
        raise NotImplementedError


class AdminUser(User):
    """Django-admin view of the users whose role is admin. Proxy: same table, no authentication of its own."""

    objects = _RoleManager(User.Role.ADMIN)

    class Meta:
        proxy = True
        verbose_name = "admin user"
        verbose_name_plural = "admin users"


class StudentUser(User):
    """Django-admin view of the users whose role is student. Proxy: same table, no authentication of its own."""

    objects = _RoleManager(User.Role.STUDENT)

    class Meta:
        proxy = True
        verbose_name = "student user"
        verbose_name_plural = "student users"


class AdminBackupCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="backup_codes")
    code_hash = models.CharField(max_length=64, unique=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
