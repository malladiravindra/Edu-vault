from django.contrib import admin
from django.urls import include, path

from accounts import urls as accounts_urls
from payments import urls as payment_urls

handler404 = "core.error_handlers.not_found"
handler500 = "core.error_handlers.server_error"

# High-level prefixes only. The detailed routes live in each app's urls.py and are combined per portal in
# portal/student_urls.py and portal/admin_urls.py. There is deliberately no route for "/" (it stays 404).
urlpatterns = [
    path("admin/", admin.site.urls),  # Django's built-in admin site (not the EduVault admin API)
    path("api/accounts/", include(accounts_urls.urlpatterns)),  # register, login, refresh, password reset, ...
    path("api/payment/", include(payment_urls.urlpatterns)),  # Stripe webhook (no JWT; signature-verified)
    path("api/student/", include("portal.student_urls")),  # student portal
    path("api/admin/", include("portal.admin_urls")),  # EduVault admin API
]
