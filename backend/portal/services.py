from django.db.models import Count, Q, Sum
from django.utils import timezone

from access.models import CourseAccess
from accounts.serializers import UserSerializer
from notifications.models import Notification
from notifications.serializers import NotificationSerializer
from payments.models import Payment
from payments.serializers import PaymentSerializer
from resources.models import Resource
from viewing.models import ViewActivity


def _course_progress(student, course_ids):
    """Per course: distinct pages the student has viewed vs. total pages of published resources."""
    totals = {
        r["course"]: r["pages"]
        for r in Resource.objects.filter(course__in=course_ids, status=Resource.Status.PUBLISHED)
        .values("course").annotate(pages=Sum("page_count"))
    }
    seen = {}
    for course, resource, page in (
        ViewActivity.objects.filter(student=student, course__in=course_ids, resource__status=Resource.Status.PUBLISHED)
        .order_by()  # the model's default ordering would otherwise leak viewed_at into SELECT DISTINCT
        .values_list("course", "resource", "page_number").distinct()
    ):
        seen[course] = seen.get(course, 0) + 1
    return totals, seen


def student_dashboard(student):
    now = timezone.now()
    accesses = CourseAccess.objects.filter(student=student).select_related("course")
    active = [
        a for a in accesses.filter(status=CourseAccess.Status.ACTIVE).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        if a.course.status == "published"
    ]
    pending = accesses.filter(status=CourseAccess.Status.PENDING, payment_required=False)
    payment_requests = accesses.filter(status=CourseAccess.Status.PENDING, payment_required=True, course__status="published")
    totals, seen = _course_progress(student, [a.course_id for a in active])

    views = ViewActivity.objects.filter(student=student)
    stats = views.aggregate(
        pages_viewed=Count("pk"), seconds=Sum("duration_seconds"), resources_opened=Count("resource", distinct=True),
        courses_studied=Count("course", distinct=True),
    )
    distinct_pages = views.order_by().values("resource", "page_number").distinct().count()
    recent = views.select_related("course", "resource")[:10]
    unread = Notification.objects.filter(user=student, read_at__isnull=True).count()
    payments = Payment.objects.filter(student=student).select_related("course")

    return {
        "profile": UserSerializer(student).data,
        "registration": {
            "status": student.status,
            "reviewed_at": student.reviewed_at,
            "rejection_reason": student.rejection_reason,
        },
        "active_courses": [
            {
                "access_id": str(a.id), "course": str(a.course_id), "title": a.course.title, "slug": a.course.slug,
                "expires_at": a.expires_at,
                "total_pages": totals.get(a.course_id, 0), "pages_viewed": seen.get(a.course_id, 0),
                "progress_percent": round(100 * seen.get(a.course_id, 0) / totals[a.course_id], 1) if totals.get(a.course_id) else 0.0,
            }
            for a in active
        ],
        "pending_requests": [
            {"access_id": str(a.id), "course": str(a.course_id), "title": a.course.title, "requested_at": a.requested_at}
            for a in pending
        ],
        "payment_requests": [
            {
                "id": str(a.id), "course": {"id": str(a.course_id), "title": a.course.title},
                "amount": f"{a.course.price_amount:.2f}" if a.course.price_amount else None,
                "currency": a.course.currency, "status": "pending", "created_at": a.decided_at or a.requested_at,
            }
            for a in payment_requests
        ],
        "recent_payments": PaymentSerializer(payments[:5], many=True).data,
        "recent_activity": [
            {
                "course": str(v.course_id), "course_title": v.course.title, "resource": str(v.resource_id),
                "resource_title": v.resource.title, "page_number": v.page_number, "viewed_at": v.viewed_at,
            }
            for v in recent
        ],
        "notifications": {
            "unread_count": unread,
            "latest": NotificationSerializer(Notification.objects.filter(user=student)[:5], many=True).data,
        },
        "learning_stats": {
            "pages_viewed": stats["pages_viewed"],
            "distinct_pages": distinct_pages,
            "reading_minutes": round((stats["seconds"] or 0) / 60, 1),
            "resources_opened": stats["resources_opened"],
            "courses_studied": stats["courses_studied"],
            "active_courses": len(active),
            "pending_courses": pending.count(),
            "payment_required_courses": payment_requests.count(),
            "payments_completed": payments.filter(status=Payment.Status.PAID).count(),
            "total_courses": accesses.count(),
            "last_viewed_at": recent[0].viewed_at if recent else None,
        },
    }


def update_student_settings(*, user, **settings):
    for name, value in settings.items():
        setattr(user, name, value)
    user.save(update_fields=[*settings, "updated_at"])
    return user
