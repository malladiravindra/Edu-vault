from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole, IsApprovedStudent
from core.pagination import paginate
from core.responses import success
from core.utils import get_client_ip, query_value
from courses.models import Course

from . import services
from .models import Payment
from .serializers import (
    AdminPaymentSerializer,
    CheckoutSerializer,
    PaymentRequestSerializer,
    PaymentSerializer,
)


def _queryset():
    return Payment.objects.select_related("course", "student")


class CreateCheckoutView(APIView):
    permission_classes = [IsApprovedStudent]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "checkout"

    def post(self, request):
        data = CheckoutSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        # Price, currency and student always come from the server, never from the request.
        course = get_object_or_404(Course, pk=data.validated_data["course"], status=Course.Status.PUBLISHED)
        payment, checkout_url = services.create_checkout(student=request.user, course=course, ip=get_client_ip(request))
        body = PaymentSerializer(_queryset().get(pk=payment.pk)).data
        return success({**body, "checkout_url": checkout_url}, status=status.HTTP_201_CREATED)


class PaymentDetailView(APIView):
    permission_classes = [IsApprovedStudent]

    def get(self, request, payment_id):
        # Another student's payment is indistinguishable from a missing one.
        payment = get_object_or_404(_queryset().filter(student=request.user), pk=payment_id)
        return success(PaymentSerializer(payment).data)


class MyPaymentsView(APIView):
    permission_classes = [IsApprovedStudent]

    def get(self, request):
        qs = _queryset().filter(student=request.user)
        if query_value(request, "status"):
            qs = qs.filter(status=query_value(request, "status"))
        return paginate(request, qs, PaymentSerializer)


def payment_requests_for(student):
    """Outstanding payment requests of one student (also used by the dashboard). Paid ones have left this state."""
    from access.models import CourseAccess

    return CourseAccess.objects.filter(
        student=student, payment_required=True, status=CourseAccess.Status.PENDING, course__status=Course.Status.PUBLISHED,
    ).select_related("course")


class MyPaymentRequestsView(APIView):
    """GET: payments the admin has asked this student to make. Pay with POST /student/payment/create-checkout/."""

    permission_classes = [IsApprovedStudent]

    def get(self, request):
        return paginate(request, payment_requests_for(request.user).order_by("-decided_at"), PaymentRequestSerializer)


class StripeWebhookView(APIView):
    """Stripe calls this directly: no JWT; trust comes only from the verified signature."""

    authentication_classes = []
    permission_classes = [AllowAny]
    # Not the 60/min anonymous default: Stripe retries bursts from shared IPs. The signature is the real gate.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "webhook"

    def post(self, request):
        result = services.process_stripe_webhook(
            payload=request.body, signature=request.META.get("HTTP_STRIPE_SIGNATURE", "")
        )
        return success({"result": result})


class AdminPaymentListView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        qs = _queryset()
        for field in ("student", "course"):
            if request.query_params.get(field):
                qs = qs.filter(**{field: request.query_params[field]})
        if query_value(request, "status"):
            qs = qs.filter(status=query_value(request, "status"))
        return paginate(request, qs, AdminPaymentSerializer)


class AdminPaymentDetailView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request, payment_id):
        return success(AdminPaymentSerializer(get_object_or_404(_queryset(), pk=payment_id)).data)
