import uuid

from django.conf import settings
from django.db import models


class ViewActivity(models.Model):
    """One server-recorded protected page view. Rows are created only by the viewer service."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="view_activities")
    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT, related_name="view_activities")
    resource = models.ForeignKey("resources.Resource", on_delete=models.PROTECT, related_name="view_activities")
    page_number = models.PositiveIntegerField()
    watermark_id = models.CharField(max_length=16)
    duration_seconds = models.PositiveIntegerField(default=0)
    viewed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-viewed_at"]
        indexes = [
            models.Index(fields=["student", "-viewed_at"]),
            models.Index(fields=["resource", "page_number"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(page_number__gt=0), name="view_page_positive"),
        ]
