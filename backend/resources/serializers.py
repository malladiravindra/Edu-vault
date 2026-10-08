from rest_framework import serializers

from courses.models import Course

from .models import Resource


class AdminResourceSerializer(serializers.ModelSerializer):
    """Admin metadata. The private storage key is deliberately not exposed."""

    course_title = serializers.CharField(source="course.title", read_only=True)

    class Meta:
        model = Resource
        fields = [
            "id", "course", "course_title", "title", "description", "status", "original_filename", "file_size",
            "page_count", "sha256", "uploaded_by", "validated_at", "published_at", "created_at", "updated_at",
        ]
        read_only_fields = fields


class ResourceUploadSerializer(serializers.Serializer):
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all())
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    file = serializers.FileField(allow_empty_file=False)


class ResourceUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False, allow_blank=True)


class ResourceReplaceSerializer(serializers.Serializer):
    file = serializers.FileField(allow_empty_file=False)
