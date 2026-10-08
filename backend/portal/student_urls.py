"""Everything served under /api/student/. Each app contributes the routes it owns (see `student_portal_urlpatterns`)."""
from access import urls as access_urls
from accounts import urls as accounts_urls
from courses import urls as course_urls
from notifications import urls as notification_urls
from payments import urls as payment_urls
from portal import urls as portal_urls
from viewing import urls as viewing_urls

urlpatterns = [
    *course_urls.student_portal_urlpatterns,  # course/, courses/
    *viewing_urls.student_portal_urlpatterns,  # viewing/, learning-history/
    *access_urls.student_portal_urlpatterns,  # access/
    *payment_urls.student_portal_urlpatterns,  # payment/, payments/, payment-requests/
    *notification_urls.student_portal_urlpatterns,  # notifications/
    *portal_urls.student_portal_urlpatterns,  # dashboard/, settings/
    *accounts_urls.student_portal_urlpatterns,  # register/, login/, profile/
    *portal_urls.student_named_dashboard_urlpatterns,  # <student name>/dashboard/ (last: fixed routes win)
]
