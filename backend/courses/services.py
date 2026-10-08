import uuid

from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import User
from audit.models import Actions
from audit.services import create_audit_event
from core.exceptions import ServiceError
from notifications import services as notifications
from notifications.models import Notification

from .models import Course


def _unique_slug(title):
    base = slugify(title)[:200] or "course"
    slug = base
    while Course.objects.filter(slug=slug).exists():
        slug = f"{base}-{uuid.uuid4().hex[:6]}"
    return slug


def create_course(*, actor, data, ip=None):
    with transaction.atomic():
        course = Course.objects.create(
            created_by=actor, slug=_unique_slug(data["title"]), status=Course.Status.DRAFT, **data
        )
        create_audit_event(
            Actions.COURSE_CREATED, actor=actor, target_type="course", target_id=course.id, ip=ip,
            metadata={"title": course.title},
        )
    return course


def update_course(*, actor, course, data, ip=None):
    with transaction.atomic():
        course = Course.objects.select_for_update().get(pk=course.pk)
        changed = sorted(k for k, v in data.items() if getattr(course, k) != v)
        for key, value in data.items():
            setattr(course, key, value)
        if data.get("access_mode") and data["access_mode"] != Course.AccessMode.PAYMENT_REQUIRED:
            course.price_amount = None
        course.save()
        create_audit_event(
            Actions.COURSE_UPDATED, actor=actor, target_type="course", target_id=course.id, ip=ip,
            metadata={"changed_fields": changed},
        )
    return course


def publish_course(*, actor, course, ip=None):
    with transaction.atomic():
        course = Course.objects.select_for_update().get(pk=course.pk)
        if course.status == Course.Status.PUBLISHED:
            raise ServiceError("INVALID_STATE", "The course is already published.", 409)
        first_publish = course.published_at is None
        course.status = Course.Status.PUBLISHED
        course.published_at = course.published_at or timezone.now()
        course.save(update_fields=["status", "published_at", "updated_at"])
        create_audit_event(Actions.COURSE_PUBLISHED, actor=actor, target_type="course", target_id=course.id, ip=ip)
        if first_publish:
            notifications.notify_many(
                User.objects.filter(role=User.Role.STUDENT, status=User.Status.ACTIVE).iterator(),
                Notification.Type.COURSE_PUBLISHED, course=course.title, data={"course": str(course.id)},
            )
    return course


def unpublish_course(*, actor, course, ip=None):
    """published -> draft. Students lose access immediately (evaluate_access treats it as unavailable); access
    records are kept so republishing restores them."""
    with transaction.atomic():
        course = Course.objects.select_for_update().get(pk=course.pk)
        if course.status != Course.Status.PUBLISHED:
            raise ServiceError("INVALID_STATE", "Only a published course can be unpublished.", 409)
        course.status = Course.Status.DRAFT
        course.save(update_fields=["status", "updated_at"])
        create_audit_event(Actions.COURSE_UNPUBLISHED, actor=actor, target_type="course", target_id=course.id, ip=ip)
    return course


def archive_course(*, actor, course, ip=None):
    with transaction.atomic():
        course = Course.objects.select_for_update().get(pk=course.pk)
        if course.status == Course.Status.ARCHIVED:
            raise ServiceError("INVALID_STATE", "The course is already archived.", 409)
        course.status = Course.Status.ARCHIVED
        course.save(update_fields=["status", "updated_at"])
        create_audit_event(Actions.COURSE_ARCHIVED, actor=actor, target_type="course", target_id=course.id, ip=ip)
    return course


def delete_course(*, actor, course, ip=None):
    course_id, title = course.id, course.title
    try:
        with transaction.atomic():
            course.delete()
            create_audit_event(
                Actions.COURSE_DELETED, actor=actor, target_type="course", target_id=course_id, ip=ip,
                metadata={"title": title},
            )
    except ProtectedError:
        raise ServiceError(
            "COURSE_IN_USE", "This course has access records or resources. Archive it instead.", 409
        )
