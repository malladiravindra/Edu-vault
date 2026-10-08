import re
from urllib.parse import quote

from rest_framework import serializers

from .models import User
from .services import password_policy_errors


class UserSerializer(serializers.ModelSerializer):
    dashboard_path = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "full_name", "first_name", "middle_name", "last_name", "phone_number", "role", "status",
            "two_factor_enabled",
            "reviewed_at", "rejection_reason", "created_at", "dashboard_path",
        ]
        read_only_fields = fields

    def get_dashboard_path(self, obj):
        """Where the frontend finds this student's dashboard (students only). The name is a routing label: the
        server still authenticates with the JWT and refuses a name that is not the signed-in student's."""
        if obj.role != User.Role.STUDENT:
            return None
        return f"/api/student/{quote(obj.dashboard_name)}/dashboard/"


class AdminUserSerializer(UserSerializer):
    reviewed_by_email = serializers.CharField(source="reviewed_by.email", read_only=True, default=None)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ["reviewed_by", "reviewed_by_email", "updated_at"]
        read_only_fields = fields


class RegistrationDetailSerializer(AdminUserSerializer):
    """Registration detail for the decision screen: profile plus the student's access records and payments."""

    accesses = serializers.SerializerMethodField()
    payments = serializers.SerializerMethodField()

    class Meta(AdminUserSerializer.Meta):
        fields = AdminUserSerializer.Meta.fields + ["accesses", "payments"]
        read_only_fields = fields

    def get_accesses(self, obj):
        from access.models import CourseAccess
        from access.serializers import CourseAccessSerializer

        qs = CourseAccess.objects.filter(student=obj).select_related("student", "course")
        return CourseAccessSerializer(qs, many=True).data

    def get_payments(self, obj):
        from payments.models import Payment
        from payments.serializers import PaymentSerializer

        return PaymentSerializer(Payment.objects.filter(student=obj).select_related("course"), many=True).data


_NAME_RE = re.compile(r"[^\W\d_]+(?:[ .'\-][^\W\d_]+)*\.?")
_PHONE_STRIP_RE = re.compile(r"[ \-().]")
_PHONE_RE = re.compile(r"\+?[0-9]{7,15}")


def clean_name(value):
    value = " ".join(value.split())
    if value and not _NAME_RE.fullmatch(value):
        raise serializers.ValidationError("Use letters only (spaces, hyphens, apostrophes and dots are allowed).")
    return value


def clean_phone(value):
    cleaned = _PHONE_STRIP_RE.sub("", value.strip())
    if not _PHONE_RE.fullmatch(cleaned):
        raise serializers.ValidationError("Enter a valid phone number (7-15 digits, optional leading +).")
    return cleaned


class RegistrationOtpRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, value):
        return value.strip().lower()


class RegistrationOtpVerifySerializer(RegistrationOtpRequestSerializer):
    otp = serializers.CharField(max_length=10)


class StudentSerializer(serializers.ModelSerializer):
    """What a student sees about themselves right after registering."""

    class Meta:
        model = User
        fields = ["id", "first_name", "middle_name", "last_name", "full_name", "email", "phone_number", "status"]
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=100)
    phone_number = serializers.CharField(max_length=30)
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)
    confirm_password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)

    def validate_email(self, value):
        return value.strip().lower()

    def _name(self, value):
        return clean_name(value)

    validate_first_name = validate_middle_name = validate_last_name = _name

    def validate_phone_number(self, value):
        return clean_phone(value)

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": ["Passwords do not match."]})
        full_name = " ".join(p for p in (attrs["first_name"], attrs.get("middle_name"), attrs["last_name"]) if p)
        if len(full_name) > 150:
            raise serializers.ValidationError({"last_name": ["The full name is too long (150 characters at most)."]})
        candidate = User(email=attrs["email"], full_name=full_name)
        errors = password_policy_errors(attrs["password"], candidate)
        if errors:
            raise serializers.ValidationError({"password": errors})
        attrs.pop("confirm_password")
        return attrs


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class ProfileUpdateSerializer(serializers.Serializer):
    """Own profile only. Role, status, flags, password and audit fields are not editable here."""

    full_name = serializers.CharField(max_length=150, required=False)
    first_name = serializers.CharField(max_length=100, required=False)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=100, required=False)
    phone_number = serializers.CharField(max_length=30, required=False)

    def validate_first_name(self, value):
        return clean_name(value)

    validate_middle_name = validate_last_name = validate_first_name

    def validate_phone_number(self, value):
        return clean_phone(value)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide at least one field to update.")
        user = self.context.get("user")
        parts = ("first_name", "middle_name", "last_name")
        if any(p in attrs for p in parts) and user is not None:
            merged = {p: attrs.get(p, getattr(user, p)) for p in parts}
            if not merged["first_name"] or not merged["last_name"]:
                raise serializers.ValidationError("First and last name are required.")
            if len(" ".join(v for v in merged.values() if v)) > 150:
                raise serializers.ValidationError({"last_name": ["The full name is too long (150 characters at most)."]})
        return attrs


class StudentSettingsSerializer(serializers.Serializer):
    email_notifications = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide at least one setting.")
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=128, trim_whitespace=False)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False)

    def validate(self, attrs):
        errors = password_policy_errors(attrs["new_password"], self.context["request"].user)
        if errors:
            raise serializers.ValidationError({"new_password": errors})
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class PasswordResetVerifySerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    otp = serializers.CharField(max_length=10)


class PasswordResetConfirmSerializer(serializers.Serializer):
    reset_token = serializers.CharField()
    new_password = serializers.CharField(max_length=128, trim_whitespace=False)
    confirm_password = serializers.CharField(max_length=128, trim_whitespace=False)

    def validate(self, attrs):
        if attrs["new_password"] != attrs.pop("confirm_password"):
            raise serializers.ValidationError({"confirm_password": ["Passwords do not match."]})
        return attrs


class ChallengeSerializer(serializers.Serializer):
    challenge_token = serializers.CharField()


class TwoFactorVerifySerializer(ChallengeSerializer):
    otp = serializers.RegexField(r"^\d{6}$", max_length=6, help_text="The 6-digit code e-mailed after the password step.")


class AdminUserUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)


class RegistrationRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
