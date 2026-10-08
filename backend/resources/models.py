import uuid

from django.conf import settings
from django.db import models


class Resource(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Uploaded, not yet validated"
        VALIDATED = "validated", "Validated"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT, related_name="resources")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    # Private object key. Never serialized, never returned to any client.
    storage_key = models.CharField(max_length=255, unique=True, editable=False)
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveBigIntegerField()
    page_count = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    validated_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["course", "status"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(file_size__gt=0), name="resource_size_positive"),
            models.CheckConstraint(condition=models.Q(page_count__gt=0), name="resource_pages_positive"),
        ]

    def __str__(self):
        return self.title
