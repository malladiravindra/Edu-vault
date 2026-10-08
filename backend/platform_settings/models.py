from django.db import models


class PlatformSettings(models.Model):
    """
    Single-row table of admin overrides. A NULL column means "use the environment default", so the
    deployment environment stays the baseline and nothing is duplicated here. No secrets live in this table.
    """

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    otp_expiry_seconds = models.PositiveIntegerField(null=True, blank=True)
    session_inactivity_seconds = models.PositiveIntegerField(null=True, blank=True)
    login_max_attempts = models.PositiveSmallIntegerField(null=True, blank=True)
    login_lockout_seconds = models.PositiveIntegerField(null=True, blank=True)
    password_min_length = models.PositiveSmallIntegerField(null=True, blank=True)
    registration_requires_approval = models.BooleanField(null=True, blank=True)
    email_notifications_enabled = models.BooleanField(null=True, blank=True)
    viewer_render_width = models.PositiveSmallIntegerField(null=True, blank=True)
    viewer_jpeg_quality = models.PositiveSmallIntegerField(null=True, blank=True)
    payments_enabled = models.BooleanField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="platform_settings_single_row")]
