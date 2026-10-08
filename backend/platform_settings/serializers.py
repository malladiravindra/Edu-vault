from rest_framework import serializers


class PlatformSettingsUpdateSerializer(serializers.Serializer):
    """Every field is optional; sending null resets it to the environment default."""

    otp_expiry_seconds = serializers.IntegerField(min_value=60, max_value=3600, allow_null=True, required=False)
    session_inactivity_seconds = serializers.IntegerField(min_value=300, max_value=86400, allow_null=True, required=False)
    login_max_attempts = serializers.IntegerField(min_value=3, max_value=20, allow_null=True, required=False)
    login_lockout_seconds = serializers.IntegerField(min_value=60, max_value=86400, allow_null=True, required=False)
    password_min_length = serializers.IntegerField(min_value=8, max_value=64, allow_null=True, required=False)
    registration_requires_approval = serializers.BooleanField(allow_null=True, required=False)
    email_notifications_enabled = serializers.BooleanField(allow_null=True, required=False)
    viewer_render_width = serializers.IntegerField(min_value=600, max_value=2400, allow_null=True, required=False)
    viewer_jpeg_quality = serializers.IntegerField(min_value=40, max_value=95, allow_null=True, required=False)
    payments_enabled = serializers.BooleanField(allow_null=True, required=False)


class TestEmailSerializer(serializers.Serializer):
    to = serializers.EmailField(required=False)
