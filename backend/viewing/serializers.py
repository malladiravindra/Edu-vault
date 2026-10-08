from rest_framework import serializers

from resources.models import Resource

from .models import ViewActivity


class ViewerResourceSerializer(serializers.ModelSerializer):
    """What a student may know about a resource. No storage key, checksum, or file details beyond page count."""

    class Meta:
        model = Resource
        fields = ["id", "course", "title", "description", "page_count", "published_at"]
        read_only_fields = fields


class ActivitySerializer(serializers.Serializer):
    view_id = serializers.UUIDField()
    duration_seconds = serializers.IntegerField(min_value=0, max_value=3600)


class LearningHistorySerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title", read_only=True)
    resource_title = serializers.CharField(source="resource.title", read_only=True)

    class Meta:
        model = ViewActivity
        fields = [
            "id", "course", "course_title", "resource", "resource_title", "page_number", "duration_seconds",
            "viewed_at",
        ]
        read_only_fields = fields
