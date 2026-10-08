from django.urls import include, path

from . import views

# Mounted at /api/payment/  (called by Stripe, no JWT: trust comes from the signature)
urlpatterns = [
    path("stripe/webhook/", views.StripeWebhookView.as_view(), name="payment-stripe-webhook"),
]

# Mounted at /api/student/payment/
checkout_urlpatterns = [
    path("create-checkout/", views.CreateCheckoutView.as_view(), name="payment-create-checkout"),
]

# Mounted at /api/student/payments/  (the signed-in student's own payments)
student_urlpatterns = [
    path("", views.MyPaymentsView.as_view(), name="my-payments"),
    path("<uuid:payment_id>/", views.PaymentDetailView.as_view(), name="payment-detail"),
]

# Mounted at /api/admin/students/payments/
admin_urlpatterns = [
    path("", views.AdminPaymentListView.as_view(), name="admin-payment-list"),
    path("<uuid:payment_id>/", views.AdminPaymentDetailView.as_view(), name="admin-payment-detail"),
]

# --- What this app contributes to the two portals. Paths are relative to /api/student/ and /api/admin/ and are
# --- combined in portal/student_urls.py and portal/admin_urls.py; the final public URLs are the ones in the comments above.
student_portal_urlpatterns = [
    path("payment/", include(checkout_urlpatterns)),
    path("payments/", include(student_urlpatterns)),
    path("payment-requests/", views.MyPaymentRequestsView.as_view(), name="my-payment-requests"),
]
admin_portal_urlpatterns = [
    path("students/payments/", include(admin_urlpatterns)),
]
