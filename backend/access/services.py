from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from audit.models import Actions
from audit.services import create_audit_event
from core.exceptions import ServiceError
from courses.models import Course
from notifications import services as notifications
from notifications.models import Notification

from .models import CourseAccess

_UNSET = object()

# Access states exposed to clients.
GRANTED = "granted"
PENDING = "pending"
REQUESTABLE = "requestable"
PAYMENT_REQUIRED = "payment_required"
EXPIRED = "expired"
REJECTED = "rejected"
REVOKED = "revoked"
UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class AccessDecision:
    state: str
    allowed: bool
    expires_at: object = None
    access_id: object = None

    def as_dict(self):
        return {
            "state": self.state,
            "allowed": self.allowed,
            "expires_at": self.expires_at,
            "access_id": self.access_id,
        }


def evaluate_access(student, course, record=_UNSET):
    """Single source of truth for whether `student` may view `course` content right now."""
    if course.status != Course.Status.PUBLISHED or not student.is_approved or student.role != "student":
        return AccessDecision(UNAVAILABLE, False)
    if record is _UNSET:
        record = CourseAccess.objects.filter(student=student, course=course).first()
    if record is not None:
        info = {"expires_at": record.expires_at, "access_id": record.id}
        if record.status == CourseAccess.Status.ACTIVE:
            if record.expires_at is not None and record.expires_at <= timezone.now():
                return AccessDecision(EXPIRED, False, **info)
            return AccessDecision(GRANTED, True, **info)
        if record.status == CourseAccess.Status.PENDING:
            if record.payment_required:
                return AccessDecision(PAYMENT_REQUIRED, False, **info)
            return AccessDecision(PENDING, False, **info)
        if record.status == CourseAccess.Status.REJECTED:
            return AccessDecision(REJECTED, False, **info)
        return AccessDecision(REVOKED, False, **info)
    return AccessDecision(REQUESTABLE, False)


def access_states_for(student, courses):
    """Evaluate many courses with a single query (avoids N+1 in listings)."""
    courses = list(courses)
    records = {
        r.course_id: r for r in CourseAccess.objects.filter(student=student, course__in=[c.pk for c in courses])
    }
    return {c.pk: evaluate_access(student, c, records.get(c.pk)).as_dict() for c in courses}


def _expiry_for(course):
    if course.access_duration_days:
        return timezone.now() + timedelta(days=course.access_duration_days)
    return None


def grant_course_access(*, student, course, source, actor=None, note="", ip=None):
    """Activate access (creating or updating the record). Callers own the surrounding transaction when needed."""
    now = timezone.now()
    with transaction.atomic():
        record, _created = CourseAccess.objects.select_for_update().get_or_create(
            student=student, course=course
        )
        record.status = CourseAccess.Status.ACTIVE
        record.source = source
        record.decided_by = actor
        record.decided_at = now
        record.granted_at = now
        record.expires_at = _expiry_for(course)
        record.revoked_by, record.revoked_at = None, None
        record.payment_required = False
        if note:
            record.note = note[:500]
        record.save()
        create_audit_event(
            Actions.ACCESS_GRANTED, actor=actor, actor_email="" if actor else "system",
            target_type="course_access", target_id=record.id, ip=ip,
            metadata={"student": str(student.id), "course": str(course.id), "source": source},
        )
        if source == CourseAccess.Source.ADMIN_APPROVAL:  # self-service and paid grants have their own feedback
            notifications.send_notification(
                student, Notification.Type.ACCESS_GRANTED, course=course.title, data={"course": str(course.id)}
            )
    return record


def request_course_access(*, student, course, ip=None):
    decision = evaluate_access(student, course)
    if decision.state == UNAVAILABLE:
        raise ServiceError("COURSE_UNAVAILABLE", "This course is not available.", 404)
    if decision.allowed or decision.state == PENDING:
        return CourseAccess.objects.get(pk=decision.access_id)
    if decision.state == REVOKED:
        raise ServiceError("ACCESS_REVOKED", "Your access to this course was revoked.", 403)
    if course.access_mode == Course.AccessMode.IMMEDIATE:
        return grant_course_access(student=student, course=course, source=CourseAccess.Source.IMMEDIATE, ip=ip)
    with transaction.atomic():
        record, _ = CourseAccess.objects.select_for_update().get_or_create(student=student, course=course)
        record.status = CourseAccess.Status.PENDING
        record.source = ""
        record.decided_by = None
        record.decided_at = None
        record.expires_at = None
        record.save()
        create_audit_event(
            Actions.ACCESS_REQUESTED, actor=student, target_type="course_access", target_id=record.id, ip=ip,
            metadata={"course": str(course.id)},
        )
        notifications.notify_admins(
            Notification.Type.ACCESS_REQUESTED, student=student.full_name, course=course.title,
            data={"access": str(record.id), "course": str(course.id), "user": str(student.id)},
        )
    return record


def _require_published(course):
    if course.status != Course.Status.PUBLISHED:
        raise ServiceError("COURSE_UNAVAILABLE", "Access can only be granted on a published course.", 409)


def admin_grant_access(*, actor, student, course, note="", ip=None):
    _require_published(course)
    if student.role != "student" or not student.is_approved:
        raise ServiceError("INVALID_STUDENT", "Access can only be granted to approved, active students.", 400)
    return grant_course_access(
        student=student, course=course, source=CourseAccess.Source.ADMIN_APPROVAL, actor=actor, note=note, ip=ip
    )


def decide_registration(*, actor, student, course, decision, note="", ip=None):
    """Admin's per-student decision for a course: immediate | payment_required | pending."""
    if student.role != "student" or not student.is_approved:
        raise ServiceError("INVALID_STUDENT", "Decisions apply only to approved, active students.", 400)
    if decision == "immediate":
        return grant_course_access(
            student=student, course=course, source=CourseAccess.Source.ADMIN_APPROVAL, actor=actor, note=note, ip=ip
        )
    if decision == "payment_required" and (
        course.access_mode != Course.AccessMode.PAYMENT_REQUIRED or not course.price_amount
    ):
        raise ServiceError("COURSE_NOT_PAID", "Only a priced, payment-required course can require payment.", 409)
    with transaction.atomic():
        record, created = CourseAccess.objects.select_for_update().get_or_create(student=student, course=course)
        unchanged = (
            not created and record.status == CourseAccess.Status.PENDING
            and record.payment_required == (decision == "payment_required")
        )
        live = (
            record.status == CourseAccess.Status.ACTIVE
            and (record.expires_at is None or record.expires_at > timezone.now())
        )
        if live:
            raise ServiceError("ALREADY_HAS_ACCESS", "The student already has access; revoke it first.", 409)
        record.status = CourseAccess.Status.PENDING
        record.payment_required = decision == "payment_required"
        record.source, record.expires_at, record.granted_at = "", None, None
        record.revoked_by, record.revoked_at = None, None
        record.decided_by, record.decided_at = actor, timezone.now()
        if note:
            record.note = note[:500]
        record.save()
        create_audit_event(
            Actions.ACCESS_PAYMENT_REQUIRED if record.payment_required else Actions.ACCESS_KEPT_PENDING,
            actor=actor, target_type="course_access", target_id=record.id, ip=ip,
            metadata={"student": str(student.id), "course": str(course.id)},
        )
        if unchanged:
            pass  # the same decision again is not a new event: no second notification
        elif record.payment_required:  # the student's "payment request"
            notifications.send_notification(
                student, Notification.Type.PAYMENT_REQUESTED, course=course.title,
                amount=f"{course.price_amount:.2f}", currency=course.currency,
                data={
                    "course": str(course.id), "access": str(record.id), "amount": f"{course.price_amount:.2f}",
                    "currency": course.currency, "action": "pay",
                },
            )
        else:  # manual review
            notifications.send_notification(
                student, Notification.Type.ACCESS_PENDING, course=course.title,
                data={"course": str(course.id), "access": str(record.id)},
            )
    return record


def decide_access(*, actor, record, action, note="", ip=None):
    """Admin decision on an existing record: approve | reject | revoke."""
    with transaction.atomic():
        record = CourseAccess.objects.select_for_update().select_related("student", "course").get(pk=record.pk)
        if action == "approve":
            if record.status != CourseAccess.Status.PENDING:
                raise ServiceError("INVALID_STATE", "Only pending requests can be approved.", 409)
            _require_published(record.course)
            return grant_course_access(
                student=record.student, course=record.course, source=CourseAccess.Source.ADMIN_APPROVAL,
                actor=actor, note=note, ip=ip,
            )
        if action == "reject":
            if record.status != CourseAccess.Status.PENDING:
                raise ServiceError("INVALID_STATE", "Only pending requests can be rejected.", 409)
            new_status, audit_action = CourseAccess.Status.REJECTED, Actions.ACCESS_REJECTED
        else:
            if record.status != CourseAccess.Status.ACTIVE:
                raise ServiceError("INVALID_STATE", "Only active access can be revoked.", 409)
            new_status, audit_action = CourseAccess.Status.REVOKED, Actions.ACCESS_REVOKED
        record.status = new_status
        record.decided_by = actor
        record.decided_at = timezone.now()
        if new_status == CourseAccess.Status.REVOKED:
            record.revoked_by, record.revoked_at = actor, record.decided_at
        record.note = note[:500] if note else record.note
        record.save()
        create_audit_event(
            audit_action, actor=actor, target_type="course_access", target_id=record.id, ip=ip,
            metadata={"student": str(record.student_id), "course": str(record.course_id)},
        )
        if new_status == CourseAccess.Status.REVOKED:
            notifications.send_notification(
                record.student, Notification.Type.ACCESS_REVOKED, course=record.course.title,
                data={"course": str(record.course_id)},
            )
        else:  # rejected
            notifications.send_notification(
                record.student, Notification.Type.ACCESS_REJECTED, course=record.course.title,
                data={"course": str(record.course_id), "access": str(record.id)},
            )
    return record


def revoke_payment_access(*, student, course):
    """Revoke access that was granted by a payment (used when that payment is refunded)."""
    now = timezone.now()
    with transaction.atomic():
        record = (
            CourseAccess.objects.select_for_update()
            .filter(student=student, course=course, status=CourseAccess.Status.ACTIVE, source=CourseAccess.Source.PAYMENT)
            .first()
        )
        if record is None:
            return None
        record.status = CourseAccess.Status.REVOKED
        record.decided_at = record.revoked_at = now
        record.decided_by = record.revoked_by = None
        record.note = "Payment refunded"
        record.save()
        create_audit_event(
            Actions.ACCESS_REVOKED, actor_email="system", target_type="course_access", target_id=record.id,
            metadata={"student": str(student.id), "course": str(course.id), "reason": "payment_refunded"},
        )
        notifications.send_notification(
            student, Notification.Type.ACCESS_REVOKED, course=course.title, data={"course": str(course.id)}
        )
    return record
