"""Everything served under /api/admin/ (the EduVault admin API; Django's own admin site is /admin/).

Each app contributes the routes it owns (see `admin_portal_urlpatterns`). The more specific prefixes come before the
general ones (course/resources/ before course/, students/... before students/).
"""
import platform_settings.urls as settings_urls
import reports.urls as report_urls
from access import urls as access_urls
from accounts import urls as accounts_urls
from audit import urls as audit_urls
from courses import urls as course_urls
from notifications import urls as notification_urls
from payments import urls as payment_urls
from resources import urls as resource_urls

urlpatterns = [
    *accounts_urls.admin_portal_urlpatterns,  # login/, profile/, students/approval-requests/, students/registrations/ (alias)
    *resource_urls.admin_portal_urlpatterns,  # course/resources/
    *course_urls.admin_portal_urlpatterns,  # course/
    *access_urls.admin_portal_urlpatterns,  # students/access/, students/<id>/decision/
    *payment_urls.admin_portal_urlpatterns,  # students/payments/
    *accounts_urls.admin_portal_students_urlpatterns,  # students/ (general, after the specific ones)
    *report_urls.admin_portal_urlpatterns,  # reports/
    *audit_urls.admin_portal_urlpatterns,  # audit-logs/
    *settings_urls.admin_portal_urlpatterns,  # settings/
    *notification_urls.admin_portal_urlpatterns,  # notifications/
]
