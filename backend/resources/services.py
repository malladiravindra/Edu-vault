import hashlib
import os
import uuid

import pypdfium2 as pdfium
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone

from audit.models import Actions
from audit.services import create_audit_event
from core.exceptions import ServiceError
from courses.models import Course

from .models import Resource
from .storage import get_private_storage

_ACCEPTED_CONTENT_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream", ""}


def _invalid(message, **details):
    return ServiceError("INVALID_PDF", message, 400, details)


def inspect_pdf(data):
    """Validate PDF bytes by content (never by filename alone). Returns the page count."""
    if len(data) == 0:
        raise _invalid("The file is empty.")
    if len(data) > settings.RESOURCE_MAX_BYTES:
        raise ServiceError(
            "FILE_TOO_LARGE", "The file exceeds the maximum allowed size.", 413,
            {"max_bytes": settings.RESOURCE_MAX_BYTES},
        )
    if not data.startswith(b"%PDF-"):
        raise _invalid("The file is not a PDF (missing PDF signature).")
    if b"%%EOF" not in data[-2048:]:
        raise _invalid("The PDF is truncated or corrupt (missing end-of-file marker).")
    try:
        document = pdfium.PdfDocument(data)
    except pdfium.PdfiumError:
        raise _invalid("The PDF could not be parsed. It may be corrupt or password protected.")
    try:
        pages = len(document)
        if pages < 1:
            raise _invalid("The PDF has no pages.")
        if pages > settings.RESOURCE_MAX_PAGES:
            raise _invalid("The PDF has too many pages.", max_pages=settings.RESOURCE_MAX_PAGES)
        try:
            document[0].render(scale=0.1)  # integrity smoke test: the first page must be renderable
        except pdfium.PdfiumError:
            raise _invalid("The PDF content could not be rendered.")
    finally:
        document.close()
    return pages


def _check_upload(uploaded):
    name = os.path.basename(uploaded.name or "")
    if not name.lower().endswith(".pdf"):
        raise _invalid("Only files with a .pdf extension are accepted.")
    if (uploaded.content_type or "").lower() not in _ACCEPTED_CONTENT_TYPES:
        raise _invalid("The declared content type is not application/pdf.")
    if uploaded.size > settings.RESOURCE_MAX_BYTES:  # reject before reading into memory
        raise ServiceError(
            "FILE_TOO_LARGE", "The file exceeds the maximum allowed size.", 413,
            {"max_bytes": settings.RESOURCE_MAX_BYTES},
        )
    return name[:255]


def load_pdf_bytes(resource):
    """Read the original PDF from private storage. For server-side rendering only."""
    storage = get_private_storage()
    with storage.open(resource.storage_key, "rb") as handle:
        return handle.read()


def upload_resource(*, actor, course, title, description, uploaded, ip=None):
    if course.status == Course.Status.ARCHIVED:
        raise ServiceError("COURSE_ARCHIVED", "Resources cannot be added to an archived course.", 409)
    filename = _check_upload(uploaded)
    data = uploaded.read()
    pages = inspect_pdf(data)
    key = f"resources/{uuid.uuid4()}.pdf"
    storage = get_private_storage()
    storage.save(key, ContentFile(data))
    try:
        with transaction.atomic():
            resource = Resource.objects.create(
                course=course, title=title, description=description, storage_key=key,
                original_filename=filename, file_size=len(data), page_count=pages,
                sha256=hashlib.sha256(data).hexdigest(), uploaded_by=actor,
            )
            create_audit_event(
                Actions.RESOURCE_UPLOADED, actor=actor, target_type="resource", target_id=resource.id, ip=ip,
                metadata={"course": str(course.id), "pages": pages, "size": len(data)},
            )
    except Exception:
        storage.delete(key)
        raise
    return resource


def replace_resource_file(*, actor, resource, uploaded, ip=None):
    """Swap the PDF behind a resource. The resource goes back to draft: it must be validated and published again."""
    if resource.status == Resource.Status.ARCHIVED:
        raise ServiceError("INVALID_STATE", "An archived resource cannot be replaced.", 409)
    filename = _check_upload(uploaded)
    data = uploaded.read()
    pages = inspect_pdf(data)
    new_key = f"resources/{uuid.uuid4()}.pdf"
    storage = get_private_storage()
    storage.save(new_key, ContentFile(data))
    old_key = resource.storage_key
    try:
        with transaction.atomic():
            resource = Resource.objects.select_for_update().get(pk=resource.pk)
            old_key = resource.storage_key
            resource.storage_key, resource.original_filename = new_key, filename
            resource.file_size, resource.page_count = len(data), pages
            resource.sha256 = hashlib.sha256(data).hexdigest()
            resource.status, resource.validated_at, resource.published_at = Resource.Status.DRAFT, None, None
            resource.save()
            create_audit_event(
                Actions.RESOURCE_REPLACED, actor=actor, target_type="resource", target_id=resource.id, ip=ip,
                metadata={"pages": pages, "size": len(data)},
            )
            transaction.on_commit(lambda: storage.delete(old_key))
    except Exception:
        storage.delete(new_key)
        raise
    return resource


def update_resource(*, actor, resource, data, ip=None):
    with transaction.atomic():
        for key, value in data.items():
            setattr(resource, key, value)
        resource.save()
        create_audit_event(
            Actions.RESOURCE_UPDATED, actor=actor, target_type="resource", target_id=resource.id, ip=ip,
            metadata={"changed_fields": sorted(data)},
        )
    return resource


def validate_resource(*, actor, resource, ip=None):
    """Re-check the stored file (integrity vs. recorded hash and PDF structure) and mark it validated."""
    with transaction.atomic():
        resource = Resource.objects.select_for_update().get(pk=resource.pk)
        if resource.status not in (Resource.Status.DRAFT, Resource.Status.VALIDATED):
            raise ServiceError("INVALID_STATE", "Only draft or validated resources can be validated.", 409)
        try:
            data = load_pdf_bytes(resource)
        except OSError:
            raise ServiceError("STORAGE_ERROR", "The stored file could not be read.", 500)
        if hashlib.sha256(data).hexdigest() != resource.sha256:
            raise _invalid("The stored file does not match its recorded checksum.")
        inspect_pdf(data)
        if resource.course.status == Course.Status.ARCHIVED:
            raise ServiceError("COURSE_ARCHIVED", "The course is archived.", 409)
        resource.status = Resource.Status.VALIDATED
        resource.validated_at = timezone.now()
        resource.save(update_fields=["status", "validated_at", "updated_at"])
        create_audit_event(Actions.RESOURCE_VALIDATED, actor=actor, target_type="resource", target_id=resource.id, ip=ip)
    return resource


def _notify_students_with_access(resource):
    """Tell the students who can open this course right now that new material is available (in-app only)."""
    from django.db.models import Q

    from access.models import CourseAccess
    from accounts.models import User
    from notifications import services as notifications
    from notifications.models import Notification

    now = timezone.now()
    students = User.objects.filter(
        role=User.Role.STUDENT, status=User.Status.ACTIVE,
        pk__in=CourseAccess.objects.filter(course=resource.course_id, status=CourseAccess.Status.ACTIVE)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now)).values("student"),
    )
    notifications.notify_many(
        students.iterator(), Notification.Type.RESOURCE_AVAILABLE, course=resource.course.title,
        resource=resource.title, data={"course": str(resource.course_id), "resource": str(resource.id)},
    )


def publish_resource(*, actor, resource, ip=None):
    with transaction.atomic():
        resource = Resource.objects.select_for_update().get(pk=resource.pk)
        if resource.status == Resource.Status.PUBLISHED:
            raise ServiceError("INVALID_STATE", "The resource is already published.", 409)
        if resource.validated_at is None or resource.status == Resource.Status.DRAFT:
            raise ServiceError("RESOURCE_NOT_VALIDATED", "Validate the resource before publishing.", 409)
        resource.status = Resource.Status.PUBLISHED
        resource.published_at = timezone.now()
        resource.save(update_fields=["status", "published_at", "updated_at"])
        create_audit_event(Actions.RESOURCE_PUBLISHED, actor=actor, target_type="resource", target_id=resource.id, ip=ip)
        _notify_students_with_access(resource)
    return resource


def archive_resource(*, actor, resource, ip=None):
    with transaction.atomic():
        resource = Resource.objects.select_for_update().get(pk=resource.pk)
        if resource.status == Resource.Status.ARCHIVED:
            raise ServiceError("INVALID_STATE", "The resource is already archived.", 409)
        resource.status = Resource.Status.ARCHIVED
        resource.save(update_fields=["status", "updated_at"])
        create_audit_event(Actions.RESOURCE_ARCHIVED, actor=actor, target_type="resource", target_id=resource.id, ip=ip)
    return resource


def delete_resource(*, actor, resource, ip=None):
    key, resource_id = resource.storage_key, resource.id
    try:
        with transaction.atomic():
            resource.delete()
            create_audit_event(
                Actions.RESOURCE_DELETED, actor=actor, target_type="resource", target_id=resource_id, ip=ip
            )
            transaction.on_commit(lambda: get_private_storage().delete(key))
    except ProtectedError:
        raise ServiceError("RESOURCE_IN_USE", "This resource has viewing history. Archive it instead.", 409)
