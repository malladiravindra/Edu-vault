from typing import Optional

from rest_framework import serializers

from .models import Course


class CourseSerializer(serializers.ModelSerializer):
    """Student-facing course representation. `access` is the requesting student's access state."""

    access = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id", "title", "slug", "description", "category", "access_mode", "price_amount", "currency",
            "access_duration_days", "published_at", "access",
        ]
        read_only_fields = fields

    def get_access(self, obj) -> Optional[dict]:
        return self.context.get("access_states", {}).get(obj.pk)


class AdminCourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = [
            "id", "title", "slug", "description", "category", "status", "access_mode", "price_amount",
            "currency", "access_duration_days", "created_by", "published_at", "created_at", "updated_at",
        ]
        read_only_fields = fields


class CourseWriteSerializer(serializers.ModelSerializer):
    """Status is changed only through the publish/archive actions, never by PATCH."""

    class Meta:
        model = Course
        fields = [
            "title", "description", "category", "access_mode", "price_amount", "currency", "access_duration_days",
        ]

    def validate_currency(self, value):
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise serializers.ValidationError("Use a 3-letter ISO currency code.")
        return value

    def validate(self, attrs):
        instance = self.instance
        mode = attrs.get("access_mode", instance.access_mode if instance else Course.AccessMode.MANUAL_APPROVAL)
        price = attrs.get("price_amount", instance.price_amount if instance else None)
        if mode == Course.AccessMode.PAYMENT_REQUIRED and (price is None or price <= 0):
            raise serializers.ValidationError({"price_amount": ["A positive price is required for paid courses."]})
        if mode != Course.AccessMode.PAYMENT_REQUIRED and attrs.get("price_amount") is not None:
            raise serializers.ValidationError({"price_amount": ["Only paid courses can have a price."]})
        return attrs
