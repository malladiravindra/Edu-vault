from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.pagination import paginate
from .permissions import IsAdminRole
from core.responses import success
from core.utils import get_client_ip, query_value

from . import serializers as s
from . import services
from .models import User


class PublicAuthView(APIView):
    """Unauthenticated endpoint with scoped rate limiting."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]


class RegistrationSendOtpView(PublicAuthView):
    throttle_scope = "otp"

    def post(self, request):
        data = s.RegistrationOtpRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        otp = services.send_registration_otp(email=data.validated_data["email"], ip=get_client_ip(request))
        res_data = {"message": "Verification OTP sent successfully."}
        from django.conf import settings
        if settings.DEBUG and otp:
            res_data["dev_otp"] = otp
        return success(res_data)


class RegistrationVerifyOtpView(PublicAuthView):
    throttle_scope = "otp_verify"

    def post(self, request):
        data = s.RegistrationOtpVerifySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.verify_registration_otp(**data.validated_data, ip=get_client_ip(request))
        return success({"message": "Email verified successfully.", "email_verified": True})


class RegisterView(PublicAuthView):
    """Final registration step: the e-mail must have been verified with an OTP. Sign in afterwards."""

    throttle_scope = "register"

    def post(self, request):
        data = s.RegisterSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = services.register_student(**data.validated_data, ip=get_client_ip(request))
        return success(
            {"message": "Student account created successfully.", "student": s.StudentSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class LoginView(PublicAuthView):
    throttle_scope = "login"

    def post(self, request):
        data = s.LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user, tokens = services.login_student(**data.validated_data, ip=get_client_ip(request))
        return success({"user": s.UserSerializer(user).data, "tokens": tokens})


class RefreshView(PublicAuthView):
    throttle_scope = "login"

    def post(self, request):
        data = s.RefreshSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return success({"tokens": services.refresh_tokens(data.validated_data["refresh"])})


class LogoutView(APIView):
    def post(self, request):
        data = s.RefreshSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.logout(
            user=request.user,
            refresh_str=data.validated_data["refresh"],
            access_sid=request.auth.get("sid"),
            ip=get_client_ip(request),
        )
        return success({"detail": "Logged out."})


class MeView(APIView):
    def get(self, request):
        return success(s.UserSerializer(request.user).data)

    def patch(self, request):
        data = s.ProfileUpdateSerializer(data=request.data, context={"user": request.user})
        data.is_valid(raise_exception=True)
        user = services.update_profile(user=request.user, **data.validated_data, ip=get_client_ip(request))
        return success(s.UserSerializer(user).data)


class AdminProfileView(MeView):
    """The signed-in admin's own profile (same data and rules as /accounts/me/, admin accounts only)."""

    permission_classes = [IsAdminRole]


class PasswordChangeView(APIView):
    def post(self, request):
        data = s.PasswordChangeSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        tokens = services.change_password(
            user=request.user,
            current_password=data.validated_data["current_password"],
            new_password=data.validated_data["new_password"],
            ip=get_client_ip(request),
        )
        return success({"tokens": tokens})


class PasswordResetRequestView(PublicAuthView):
    throttle_scope = "password_reset"

    def post(self, request):
        data = s.PasswordResetRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.request_password_reset(email=data.validated_data["email"], ip=get_client_ip(request))
        return success({"detail": "If an account exists for this email, a reset link has been sent."})


class PasswordResetVerifyView(PublicAuthView):
    throttle_scope = "password_reset"

    def post(self, request):
        data = s.PasswordResetVerifySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        token = services.verify_reset_otp(**data.validated_data, ip=get_client_ip(request))
        return success({"reset_token": token})


class PasswordResetConfirmView(PublicAuthView):
    throttle_scope = "password_reset"

    def post(self, request):
        data = s.PasswordResetConfirmSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.confirm_password_reset(**data.validated_data, ip=get_client_ip(request))
        return success({"detail": "Password has been reset."})


class AdminLoginView(PublicAuthView):
    throttle_scope = "login"

    def post(self, request):
        data = s.LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return success(services.admin_login(**data.validated_data, ip=get_client_ip(request)))


class TwoFactorVerifyView(PublicAuthView):
    throttle_scope = "two_factor"

    def post(self, request):
        data = s.TwoFactorVerifySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user, tokens = services.two_factor_verify(**data.validated_data, ip=get_client_ip(request))
        return success({"user": s.UserSerializer(user).data, "tokens": tokens})


class AdminUserListView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        qs = User.objects.select_related("reviewed_by")
        for field in ("role", "status"):
            if query_value(request, field):
                qs = qs.filter(**{field: query_value(request, field)})
        if request.query_params.get("q"):
            q = request.query_params["q"]
            qs = qs.filter(Q(email__icontains=q) | Q(full_name__icontains=q))
        return paginate(request, qs, s.AdminUserSerializer)


class AdminUserDetailView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request, user_id):
        return success(s.AdminUserSerializer(_get_user(user_id)).data)

    def patch(self, request, user_id):
        user = _get_user(user_id)
        data = s.AdminUserUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = services.admin_update_user(
            actor=request.user, user=user, ip=get_client_ip(request), **data.validated_data
        )
        return success(s.AdminUserSerializer(user).data)

    def delete(self, request, user_id):
        services.delete_user(actor=request.user, user=_get_user(user_id), ip=get_client_ip(request))
        return success({"detail": "User deleted."})


class AdminUserSuspendView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request, user_id):
        user = services.suspend_user(actor=request.user, user=_get_user(user_id), ip=get_client_ip(request))
        return success(s.AdminUserSerializer(user).data)


class AdminUserReactivateView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request, user_id):
        user = services.reactivate_user(actor=request.user, user=_get_user(user_id), ip=get_client_ip(request))
        return success(s.AdminUserSerializer(user).data)


class AdminRegistrationListView(APIView):
    """Registrations / approval requests. `default_status` (set per route) applies when `?status=` is absent."""

    permission_classes = [IsAdminRole]
    default_status = None

    def get(self, request):
        qs = User.objects.filter(role=User.Role.STUDENT).select_related("reviewed_by")
        wanted = query_value(request, "status") or self.default_status
        if wanted and wanted != "all":
            qs = qs.filter(status=wanted)
        return paginate(request, qs, s.AdminUserSerializer)


class AdminRegistrationDetailView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request, user_id):
        return success(s.RegistrationDetailSerializer(_get_student(user_id)).data)


class AdminRegistrationApproveView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request, user_id):
        user = services.approve_registration(
            actor=request.user, user=_get_student(user_id), ip=get_client_ip(request)
        )
        return success(s.AdminUserSerializer(user).data)


class AdminRegistrationRejectView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request, user_id):
        user = _get_student(user_id)
        data = s.RegistrationRejectSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = services.reject_registration(
            actor=request.user, user=user, reason=data.validated_data["reason"], ip=get_client_ip(request)
        )
        return success(s.AdminUserSerializer(user).data)


def _get_user(user_id):
    return get_object_or_404(User.objects.select_related("reviewed_by"), pk=user_id)


def _get_student(user_id):
    return get_object_or_404(User.objects.select_related("reviewed_by"), pk=user_id, role=User.Role.STUDENT)
