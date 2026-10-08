from datetime import datetime

from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title", read_only=True)

    class Meta:
        model = Payment
        fields = ["id", "course", "course_title", "amount", "currency", "status", "paid_at", "created_at"]
        read_only_fields = fields


class AdminPaymentSerializer(PaymentSerializer):
    student_email = serializers.CharField(source="student.email", read_only=True)

    class Meta(PaymentSerializer.Meta):
        fields = PaymentSerializer.Meta.fields + [
            "student", "student_email", "stripe_checkout_session_id", "stripe_payment_intent_id", "stripe_event_id",
            "updated_at",
        ]
        read_only_fields = fields


class CheckoutSerializer(serializers.Serializer):
    course = serializers.UUIDField()


class PaymentRequestSerializer(serializers.Serializer):
    """A payment an admin has asked this student to make: an access record flagged `payment_required`."""

    id = serializers.UUIDField()
    course = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    note = serializers.CharField()
    created_at = serializers.SerializerMethodField()

    def get_course(self, obj) -> dict:
        return {"id": str(obj.course_id), "title": obj.course.title}

    def get_amount(self, obj) -> str:
        return f"{obj.course.price_amount:.2f}"

    def get_currency(self, obj) -> str:
        return obj.course.currency

    def get_status(self, obj) -> str:
        return "pending"

    def get_created_at(self, obj) -> datetime:
        return obj.decided_at or obj.requested_at
