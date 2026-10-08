from django.urls import include, path

from .permissions import IsStudentRole

from . import views

# Mounted at /api/accounts/  (shared by students and admins; admin sign-in is /api/admin/login/).
# register/* and login/ are DEPRECATED aliases of /api/student/register/* and /api/student/login/ (same views, same
# behaviour) kept until existing clients move; logout, refresh, me, password-change and the password reset stay here.
urlpatterns = [
    path("register/send-otp/", views.RegistrationSendOtpView.as_view(), name="auth-register-send-otp"),
    path("register/verify-otp/", views.RegistrationVerifyOtpView.as_view(), name="auth-register-verify-otp"),
    path("register/", views.RegisterView.as_view(), name="auth-register"),
    path("login/", views.LoginView.as_view(), name="auth-login"),
    path("logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("refresh/", views.RefreshView.as_view(), name="auth-refresh"),
    path("me/", views.MeView.as_view(), name="auth-me"),
    path("password-change/", views.PasswordChangeView.as_view(), name="auth-password-change"),
    path("forgot-password/", views.PasswordResetRequestView.as_view(), name="auth-forgot-password"),
    path("forgot-password/verify/", views.PasswordResetVerifyView.as_view(), name="auth-forgot-password-verify"),
    path("reset-password/", views.PasswordResetConfirmView.as_view(), name="auth-reset-password"),
]

# Mounted at /api/admin/login/  (email + password, then the e-mailed 6-digit code at 2fa/verify/)
admin_login_urlpatterns = [
    path("", views.AdminLoginView.as_view(), name="auth-admin-login"),
    path("2fa/verify/", views.TwoFactorVerifyView.as_view(), name="auth-2fa-verify"),
]

# Mounted at /api/admin/profile/
admin_profile_urlpatterns = [
    path("", views.AdminProfileView.as_view(), name="admin-profile"),
]

# Mounted at /api/admin/students/  (list, detail, suspend, reinstate)
admin_student_urlpatterns = [
    path("", views.AdminUserListView.as_view(), name="admin-user-list"),
    path("<uuid:user_id>/", views.AdminUserDetailView.as_view(), name="admin-user-detail"),
    path("<uuid:user_id>/suspend/", views.AdminUserSuspendView.as_view(), name="admin-user-suspend"),
    path("<uuid:user_id>/reinstate/", views.AdminUserReactivateView.as_view(), name="admin-user-reinstate"),
]

# Mounted at /api/admin/students/approval-requests/  (registrations waiting for an admin decision; pending by default,
# ?status=<status> or ?status=all to see others)
admin_approval_urlpatterns = [
    path("", views.AdminRegistrationListView.as_view(default_status="pending"), name="admin-approval-request-list"),
    path("<uuid:user_id>/", views.AdminRegistrationDetailView.as_view(), name="admin-approval-request-detail"),
    path(
        "<uuid:user_id>/approve/", views.AdminRegistrationApproveView.as_view(), name="admin-approval-request-approve"
    ),
    path("<uuid:user_id>/reject/", views.AdminRegistrationRejectView.as_view(), name="admin-approval-request-reject"),
]

# DEPRECATED alias, mounted at /api/admin/students/registrations/ until the frontend uses approval-requests/.
# Same views and the same behaviour as before (the list shows every student unless ?status= is given).
admin_registration_alias_urlpatterns = [
    path("", views.AdminRegistrationListView.as_view(), name="admin-registration-list"),
    path("<uuid:user_id>/", views.AdminRegistrationDetailView.as_view(), name="admin-registration-detail"),
    path("<uuid:user_id>/approve/", views.AdminRegistrationApproveView.as_view(), name="admin-registration-approve"),
    path("<uuid:user_id>/reject/", views.AdminRegistrationRejectView.as_view(), name="admin-registration-reject"),
]

# --- What this app contributes to the two portals. Paths are relative to /api/student/ and /api/admin/ and are
# --- combined in portal/student_urls.py and portal/admin_urls.py; the final public URLs are the ones in the comments above.
student_portal_urlpatterns = [
    # Canonical student entry points: /api/student/register/ (3 steps: send-otp, verify-otp, create) and /login/.
    path("register/send-otp/", views.RegistrationSendOtpView.as_view(), name="student-register-send-otp"),
    path("register/verify-otp/", views.RegistrationVerifyOtpView.as_view(), name="student-register-verify-otp"),
    path("register/", views.RegisterView.as_view(), name="student-register"),
    path("login/", views.LoginView.as_view(), name="student-login"),
    path("profile/", views.MeView.as_view(permission_classes=[IsStudentRole]), name="student-profile"),
]
admin_portal_urlpatterns = [
    path("login/", include(admin_login_urlpatterns)),
    path("profile/", include(admin_profile_urlpatterns)),
    path("students/approval-requests/", include(admin_approval_urlpatterns)),
    path("students/registrations/", include(admin_registration_alias_urlpatterns)),  # deprecated alias
]
# The general students/ group is composed last (after students/access/ and students/payments/).
admin_portal_students_urlpatterns = [
    path("students/", include(admin_student_urlpatterns)),
]
