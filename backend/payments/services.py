import json
from datetime import timedelta
from decimal import Decimal

import stripe
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from access.models import CourseAccess
from access.services import (
    GRANTED,
    PAYMENT_REQUIRED,
    REVOKED,
    evaluate_access,
    grant_course_access,
    revoke_payment_access,
)
from audit.models import Actions
from audit.services import create_audit_event
from core.exceptions import ServiceError
from courses.models import Course
from notifications import services as notifications
from notifications.models import Notification
from platform_settings import services as platform

from .models import Payment, StripeEvent

# Currencies Stripe treats as having no minor unit.
_ZERO_DECIMAL = {"BIF", "CLP", "DJF", "GNF", "JPY", "KMF", "KRW", "MGA", "PYG", "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF"}


def to_minor_units(amount, currency):
    amount = Decimal(amount)
    return int(amount) if currency.upper() in _ZERO_DECIMAL else int((amount * 100).quantize(Decimal("1")))


# ---------------------------------------------------------------- checkout

def _open_checkout(student, course):
    """The student's still-open Stripe session for this course (same server-side price), so a double click or a
    page reload does not pile up pending payments. Returns (payment, url) or None."""
    candidate = (
        Payment.objects.filter(
            student=student, course=course, status=Payment.Status.PENDING,
            stripe_checkout_session_id__isnull=False, created_at__gte=timezone.now() - timedelta(hours=23),
        )
        .order_by("-created_at")
        .first()
    )
    if candidate is None or candidate.amount != course.price_amount or candidate.currency != course.currency.upper():
        return None
    try:
        session = stripe.checkout.Session.retrieve(candidate.stripe_checkout_session_id, api_key=settings.STRIPE_SECRET_KEY)
    except stripe.StripeError:
        return None
    if session.get("status") == "open" and session.get("url"):
        return candidate, session["url"]
    return None


def create_checkout(*, student, course, ip=None):
    if course.status != Course.Status.PUBLISHED:
        raise ServiceError("COURSE_UNAVAILABLE", "This course is not available.", 404)
    if course.access_mode != Course.AccessMode.PAYMENT_REQUIRED:
        raise ServiceError("PAYMENT_NOT_REQUIRED", "This course does not require payment.", 400)
    decision = evaluate_access(student, course)
    if decision.state == GRANTED:
        raise ServiceError("ALREADY_HAS_ACCESS", "You already have access to this course.", 409)
    if decision.state == REVOKED:
        raise ServiceError("ACCESS_REVOKED", "Your access to this course was revoked.", 403)
    if decision.state != PAYMENT_REQUIRED:  # an admin must have approved this student's request for payment first
        raise ServiceError("PAYMENT_NOT_APPROVED", "An admin must approve your request before you can pay.", 403)
    if not platform.get("payments_enabled"):
        raise ServiceError("PAYMENTS_DISABLED", "Payments are currently disabled.", 503)
    if not settings.STRIPE_SECRET_KEY:
        raise ServiceError("PAYMENTS_NOT_CONFIGURED", "Payments are not available right now.", 503)

    reused = _open_checkout(student, course)
    if reused is not None:
        return reused

    with transaction.atomic():
        payment = Payment.objects.create(
            student=student, course=course, amount=course.price_amount, currency=course.currency.upper()
        )
        create_audit_event(
            Actions.PAYMENT_CREATED, actor=student, target_type="payment", target_id=payment.id, ip=ip,
            metadata={"course": str(course.id), "currency": payment.currency},
        )
    base = settings.FRONTEND_URL.rstrip("/")
    try:
        session = stripe.checkout.Session.create(
            api_key=settings.STRIPE_SECRET_KEY,
            mode="payment",
            customer_email=student.email,
            client_reference_id=str(payment.id),
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": payment.currency.lower(),
                        "unit_amount": to_minor_units(payment.amount, payment.currency),
                        "product_data": {"name": course.title},
                    },
                }
            ],
            metadata={"payment_id": str(payment.id), "student_id": str(student.id), "course_id": str(course.id)},
            payment_intent_data={"metadata": {"payment_id": str(payment.id)}},
            success_url=f"{base}/payments/success?payment_id={payment.id}",
            cancel_url=f"{base}/payments/cancelled?payment_id={payment.id}",
            idempotency_key=f"checkout-{payment.id}",
        )
    except stripe.StripeError:
        with transaction.atomic():
            Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.FAILED)
            create_audit_event(
                Actions.PAYMENT_FAILED, actor=student, target_type="payment", target_id=payment.id, ip=ip,
                metadata={"reason": "checkout_session_creation_failed"},
            )
        raise ServiceError("PAYMENT_PROVIDER_ERROR", "The payment provider is unavailable. Please try again.", 502)
    payment.stripe_checkout_session_id = session["id"]
    payment.save(update_fields=["stripe_checkout_session_id", "updated_at"])
    return payment, session["url"]


# ---------------------------------------------------------------- webhook

def _locked_payment(obj, *, intent_lookup=False):
    """Find the payment an event refers to (by Stripe ids first, then our own metadata)."""
    qs = Payment.objects.select_for_update()
    payment = None
    if intent_lookup:
        intent = obj.get("payment_intent") if obj.get("object") == "charge" else obj.get("id")
        if intent:
            payment = qs.filter(stripe_payment_intent_id=intent).first()
    elif obj.get("id"):
        payment = qs.filter(stripe_checkout_session_id=obj["id"]).first()
    if payment is None:
        meta_id = (obj.get("metadata") or {}).get("payment_id") or obj.get("client_reference_id")
        if meta_id:
            try:
                payment = qs.filter(pk=meta_id).first()
            except (ValueError, TypeError, DjangoValidationError):
                payment = None
    return payment


def _needs_attention(payment, detail):
    notifications.notify_admins(
        Notification.Type.PAYMENT_ATTENTION, student=payment.student.full_name, course=payment.course.title,
        detail=detail, data={"payment": str(payment.id), "course": str(payment.course_id), "user": str(payment.student_id)},
    )


def _mismatch(payment, event_id, reason):
    create_audit_event(
        Actions.PAYMENT_MISMATCH, actor_email="stripe", target_type="payment", target_id=payment.id,
        metadata={"reason": reason, "event": event_id},
    )
    _needs_attention(payment, "a Stripe payment did not match the amount or currency and was NOT activated")


def _mark_paid(obj, event_id):
    payment = _locked_payment(obj)
    if payment is None:
        return None
    if payment.status in (Payment.Status.PAID, Payment.Status.REFUNDED):
        return payment  # already settled: idempotent
    if obj.get("payment_status") != "paid":
        return payment  # async method still processing; a later event settles it
    if (
        obj.get("amount_total") != to_minor_units(payment.amount, payment.currency)
        or str(obj.get("currency", "")).upper() != payment.currency
    ):
        _mismatch(payment, event_id, "amount_or_currency_mismatch")
        return payment
    payment.status = Payment.Status.PAID
    payment.paid_at = timezone.now()
    payment.stripe_payment_intent_id = obj.get("payment_intent") or ""
    payment.stripe_event_id = event_id
    payment.save()
    grant_course_access(
        student=payment.student, course=payment.course, source=CourseAccess.Source.PAYMENT,
        note=f"Payment {payment.id}",
    )
    create_audit_event(
        Actions.PAYMENT_COMPLETED, actor_email="stripe", target_type="payment", target_id=payment.id,
        metadata={"course": str(payment.course_id), "student": str(payment.student_id), "event": event_id},
    )
    notifications.send_notification(
        payment.student, Notification.Type.PAYMENT_SUCCESSFUL, course=payment.course.title,
        data={"payment": str(payment.id), "course": str(payment.course_id), "event": event_id},
    )
    notifications.notify_admins(
        Notification.Type.PAYMENT_RECEIVED, student=payment.student.full_name, course=payment.course.title,
        data={"payment": str(payment.id), "course": str(payment.course_id), "user": str(payment.student_id)},
    )
    return payment


def _mark_unpaid(status, action):
    def handler(obj, event_id):
        payment = _locked_payment(obj, intent_lookup=obj.get("object") == "payment_intent")
        if payment is None or payment.status != Payment.Status.PENDING:
            return payment
        payment.status = status
        payment.stripe_event_id = event_id
        payment.save(update_fields=["status", "stripe_event_id", "updated_at"])
        create_audit_event(
            action, actor_email="stripe", target_type="payment", target_id=payment.id, metadata={"event": event_id}
        )
        notifications.send_notification(
            payment.student, Notification.Type.PAYMENT_FAILED, course=payment.course.title,
            data={"payment": str(payment.id), "course": str(payment.course_id), "event": event_id},
        )
        return payment

    return handler


def _mark_refunded(obj, event_id):
    if not obj.get("refunded"):
        return None  # partial refunds do not change access
    payment = _locked_payment(obj, intent_lookup=True)
    if payment is None or payment.status != Payment.Status.PAID:
        return payment
    payment.status = Payment.Status.REFUNDED
    payment.stripe_event_id = event_id
    payment.save(update_fields=["status", "stripe_event_id", "updated_at"])
    revoke_payment_access(student=payment.student, course=payment.course)
    create_audit_event(
        Actions.PAYMENT_REFUNDED, actor_email="stripe", target_type="payment", target_id=payment.id,
        metadata={"event": event_id},
    )
    _needs_attention(payment, "a payment was refunded and the student's access was revoked")
    return payment


_HANDLERS = {
    "checkout.session.completed": _mark_paid,
    "checkout.session.async_payment_succeeded": _mark_paid,
    "checkout.session.async_payment_failed": _mark_unpaid(Payment.Status.FAILED, Actions.PAYMENT_FAILED),
    "checkout.session.expired": _mark_unpaid(Payment.Status.CANCELLED, Actions.PAYMENT_CANCELLED),
    "payment_intent.payment_failed": _mark_unpaid(Payment.Status.FAILED, Actions.PAYMENT_FAILED),
    "charge.refunded": _mark_refunded,
}


def process_stripe_webhook(*, payload, signature):
    """Verify the Stripe signature, then apply the event exactly once, atomically."""
    secret = settings.STRIPE_WEBHOOK_SECRET
    if not secret:
        raise ServiceError("WEBHOOK_NOT_CONFIGURED", "Webhook processing is not configured.", 503)
    try:
        stripe.Webhook.construct_event(payload, signature or "", secret)
        event = json.loads(payload)
    except (ValueError, stripe.SignatureVerificationError):
        raise ServiceError("INVALID_SIGNATURE", "The webhook signature could not be verified.", 400)

    with transaction.atomic():
        try:
            with transaction.atomic():
                record = StripeEvent.objects.create(event_id=event["id"], event_type=event["type"])
        except IntegrityError:
            return "duplicate"
        handler = _HANDLERS.get(event["type"])
        payment = handler(event["data"]["object"], event["id"]) if handler else None
        if payment is not None:
            record.payment = payment
            record.save(update_fields=["payment"])
        create_audit_event(
            Actions.STRIPE_WEBHOOK_PROCESSED, actor_email="stripe", target_type="stripe_event",
            target_id=event["id"], metadata={"type": event["type"], "handled": handler is not None},
        )
    return "processed"
