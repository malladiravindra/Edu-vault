from typing import Optional

from rest_framework import serializers

from accounts.models import User
from courses.models import Course

from .models import CourseAccess
from .services import evaluate_access


class CourseAccessSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title", read_only=True)
    student_email = serializers.CharField(source="student.email", read_only=True)
    state = serializers.SerializerMethodField()
    granted_by = serializers.SerializerMethodField()

    class Meta:
        model = CourseAccess
        fields = [
            "id", "student", "student_email", "course", "course_title", "status", "state", "source", "payment_required", "note",
            "requested_at", "decided_at", "granted_at", "granted_by", "expires_at", "revoked_at", "revoked_by",
        ]
        read_only_fields = fields

    def get_granted_by(self, obj) -> Optional[str]:
        return obj.decided_by_id if obj.status == CourseAccess.Status.ACTIVE else None

    def get_state(self, obj) -> str:
        return evaluate_access(obj.student, obj.course, obj).state


class AccessRequestSerializer(serializers.Serializer):
    course = serializers.UUIDField()


class AccessGrantSerializer(serializers.Serializer):
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all())
    student = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=User.Role.STUDENT))
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class AccessDecisionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject", "revoke"])
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class StudentDecisionSerializer(serializers.Serializer):
    # "manual" is the admin-facing name of "keep pending (manual review)".
    decision = serializers.ChoiceField(choices=["immediate", "payment_required", "pending", "manual"])
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.filter(status=Course.Status.PUBLISHED))
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")

    def validate_decision(self, value):
        return "pending" if value == "manual" else value
