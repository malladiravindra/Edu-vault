"""Read-only reporting. Everything is computed with ORM aggregation; nothing is hardcoded or cached business data."""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from access.models import CourseAccess
from accounts.models import User
from audit.models import AuditEvent
from courses.models import Course
from payments.models import Payment
from resources.models import Resource
from viewing.models import ViewActivity


def _counts(queryset, field):
    """{value: count} for one grouped column, in a single query."""
    return {row[field]: row["n"] for row in queryset.values(field).annotate(n=Count("pk"))}


def _since(days):
    return timezone.now() - timedelta(days=days)


def _daily(queryset, date_field, **aggregates):
    rows = (
        queryset.annotate(day=TruncDate(date_field)).values("day").annotate(**aggregates).order_by("day")
    )
    return [{"date": r["day"].isoformat(), **{k: _plain(r[k]) for k in aggregates}} for r in rows]


def _money(value):
    """Fixed two-decimal string, identical on every database backend."""
    return f"{Decimal(value or 0):.2f}"


def _plain(value):
    return _money(value) if isinstance(value, Decimal) else (0 if value is None else value)


def _money_by_currency(queryset):
    rows = queryset.values("currency").annotate(total=Sum("amount"), n=Count("pk")).order_by("currency")
    return [{"currency": r["currency"], "total": _money(r["total"]), "count": r["n"]} for r in rows]


# ---------------------------------------------------------------- building blocks

def user_summary():
    by_status = _counts(User.objects.filter(role=User.Role.STUDENT), "status")
    return {
        "total": User.objects.count(),
        "students": User.objects.filter(role=User.Role.STUDENT).count(),
        "admins": User.objects.filter(role=User.Role.ADMIN).count(),
        "pending_registrations": by_status.get(User.Status.PENDING, 0),
        "active": by_status.get(User.Status.ACTIVE, 0),
        "suspended": by_status.get(User.Status.SUSPENDED, 0),
        "rejected": by_status.get(User.Status.REJECTED, 0),
    }


def course_summary():
    by_status = _counts(Course.objects.all(), "status")
    return {
        "total": sum(by_status.values()),
        "published": by_status.get(Course.Status.PUBLISHED, 0),
        "draft": by_status.get(Course.Status.DRAFT, 0),
        "archived": by_status.get(Course.Status.ARCHIVED, 0),
    }


def resource_summary():
    by_status = _counts(Resource.objects.all(), "status")
    return {"total": sum(by_status.values()), **{s.value: by_status.get(s.value, 0) for s in Resource.Status}}


def access_summary():
    now = timezone.now()
    live = CourseAccess.objects.filter(status=CourseAccess.Status.ACTIVE).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    )
    return {
        "active": live.count(),
        "pending_approvals": CourseAccess.objects.filter(
            status=CourseAccess.Status.PENDING, payment_required=False
        ).count(),
        "payment_requests_pending": CourseAccess.objects.filter(
            status=CourseAccess.Status.PENDING, payment_required=True
        ).count(),
        "expired": CourseAccess.objects.filter(status=CourseAccess.Status.ACTIVE, expires_at__lte=now).count(),
        "revoked": CourseAccess.objects.filter(status=CourseAccess.Status.REVOKED).count(),
        "rejected": CourseAccess.objects.filter(status=CourseAccess.Status.REJECTED).count(),
    }


def payment_summary():
    by_status = _counts(Payment.objects.all(), "status")
    return {
        "by_status": {s.value: by_status.get(s.value, 0) for s in Payment.Status},
        "revenue": _money_by_currency(Payment.objects.filter(status=Payment.Status.PAID)),
        "refunded": _money_by_currency(Payment.objects.filter(status=Payment.Status.REFUNDED)),
    }


def activity_summary(days=30):
    qs = ViewActivity.objects.filter(viewed_at__gte=_since(days))
    totals = qs.aggregate(
        page_views=Count("pk"), active_students=Count("student", distinct=True), seconds=Sum("duration_seconds")
    )
    return {
        "days": days,
        "page_views": totals["page_views"],
        "active_students": totals["active_students"],
        "reading_minutes": round((totals["seconds"] or 0) / 60, 1),
    }


# ---------------------------------------------------------------- admin dashboard + reports

def admin_dashboard():
    recent = AuditEvent.objects.order_by("-created_at")[:10]
    return {
        "users": user_summary(),
        "courses": course_summary(),
        "resources": resource_summary(),
        "access": access_summary(),
        "payments": payment_summary(),
        "activity_last_30_days": activity_summary(30),
        "recent_activity": [
            {
                "id": str(e.id), "action": e.action, "actor_email": e.actor_email,
                "target_type": e.target_type, "target_id": e.target_id, "created_at": e.created_at,
            }
            for e in recent
        ],
    }


def overview_report(days):
    return {
        "users": user_summary(),
        "courses": course_summary(),
        "resources": resource_summary(),
        "access": access_summary(),
        "payments": payment_summary(),
        "activity": activity_summary(days),
    }


def users_report(days):
    students = User.objects.filter(role=User.Role.STUDENT)
    reviewed = students.filter(reviewed_at__isnull=False)
    return {
        "days": days,
        "summary": user_summary(),
        "registrations_per_day": _daily(students.filter(created_at__gte=_since(days)), "created_at", registrations=Count("pk")),
        "approved_in_period": reviewed.filter(status=User.Status.ACTIVE, reviewed_at__gte=_since(days)).count(),
        "rejected_in_period": reviewed.filter(status=User.Status.REJECTED, reviewed_at__gte=_since(days)).count(),
        "awaiting_review": students.filter(status=User.Status.PENDING).count(),
        "oldest_pending_since": (
            students.filter(status=User.Status.PENDING).order_by("created_at").values_list("created_at", flat=True).first()
        ),
    }


def course_rows(courses):
    """Per-course statistics for a page of courses, using one grouped query per metric (no N+1)."""
    ids = [c.pk for c in courses]
    access = {}
    for row in CourseAccess.objects.filter(course__in=ids).values("course", "status").annotate(n=Count("pk")):
        access.setdefault(row["course"], {})[row["status"]] = row["n"]
    resources = _counts(Resource.objects.filter(course__in=ids, status=Resource.Status.PUBLISHED), "course")
    revenue = {
        (r["course"], r["currency"]): r["total"]
        for r in Payment.objects.filter(course__in=ids, status=Payment.Status.PAID)
        .values("course", "currency").annotate(total=Sum("amount"))
    }
    views = {
        r["course"]: r
        for r in ViewActivity.objects.filter(course__in=ids)
        .values("course").annotate(n=Count("pk"), students=Count("student", distinct=True), seconds=Sum("duration_seconds"))
    }
    rows = []
    for c in courses:
        counts = access.get(c.pk, {})
        view = views.get(c.pk)
        rows.append(
            {
                "id": str(c.pk), "title": c.title, "status": c.status, "access_mode": c.access_mode,
                "published_resources": resources.get(c.pk, 0),
                "active_students": counts.get(CourseAccess.Status.ACTIVE, 0),
                "pending_requests": counts.get(CourseAccess.Status.PENDING, 0),
                "revoked": counts.get(CourseAccess.Status.REVOKED, 0),
                "revenue": [{"currency": cur, "total": _money(total)} for (cid, cur), total in revenue.items() if cid == c.pk],
                "page_views": view["n"] if view else 0,
                "viewing_students": view["students"] if view else 0,
                "reading_minutes": round(((view["seconds"] if view else 0) or 0) / 60, 1),
            }
        )
    return rows


def access_report(days):
    since = _since(days)
    now = timezone.now()
    return {
        "days": days,
        "summary": access_summary(),
        "by_source": _counts(CourseAccess.objects.filter(status=CourseAccess.Status.ACTIVE), "source"),
        "granted_per_day": _daily(
            CourseAccess.objects.filter(granted_at__gte=since), "granted_at", grants=Count("pk")
        ),
        "requests_per_day": _daily(CourseAccess.objects.filter(requested_at__gte=since), "requested_at", requests=Count("pk")),
        "expiring_within_7_days": CourseAccess.objects.filter(
            status=CourseAccess.Status.ACTIVE, expires_at__gt=now, expires_at__lte=now + timedelta(days=7)
        ).count(),
        "oldest_pending_request": (
            CourseAccess.objects.filter(status=CourseAccess.Status.PENDING)
            .order_by("requested_at").values_list("requested_at", flat=True).first()
        ),
    }


def payments_report(days):
    paid = Payment.objects.filter(status=Payment.Status.PAID, paid_at__gte=_since(days))
    top = (
        Payment.objects.filter(status=Payment.Status.PAID)
        .values("course", "course__title", "currency")
        .annotate(total=Sum("amount"), n=Count("pk"))
        .order_by("-total")[:10]
    )
    return {
        "days": days,
        "summary": payment_summary(),
        "revenue_in_period": _money_by_currency(paid),
        "average_payment": [
            {"currency": r["currency"], "average": _money(r["avg"])}
            for r in Payment.objects.filter(status=Payment.Status.PAID).values("currency").annotate(avg=Avg("amount"))
        ],
        "paid_per_day": _daily(paid, "paid_at", payments=Count("pk"), revenue=Sum("amount")),
        "top_courses": [
            {"course": str(r["course"]), "title": r["course__title"], "currency": r["currency"], "revenue": _money(r["total"]), "payments": r["n"]}
            for r in top
        ],
    }


def activity_report(days):
    qs = ViewActivity.objects.filter(viewed_at__gte=_since(days))
    top_resources = (
        qs.values("resource", "resource__title", "course__title")
        .annotate(views=Count("pk"), students=Count("student", distinct=True))
        .order_by("-views")[:10]
    )
    return {
        "summary": activity_summary(days),
        "views_per_day": _daily(qs, "viewed_at", views=Count("pk"), students=Count("student", distinct=True)),
        "top_resources": [
            {"resource": str(r["resource"]), "title": r["resource__title"], "course": r["course__title"], "views": r["views"], "students": r["students"]}
            for r in top_resources
        ],
    }
