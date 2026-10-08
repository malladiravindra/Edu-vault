from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from core.responses import success
from core.utils import get_client_ip

from . import services
from .serializers import PlatformSettingsUpdateSerializer, TestEmailSerializer


def _payload():
    return {
        "settings": services.effective(),
        "overridden": services.overridden(),
        "integrations": services.integrations(),
    }


class AdminSettingsView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        return success(_payload())

    def patch(self, request):
        data = PlatformSettingsUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.update_settings(actor=request.user, data=data.validated_data, ip=get_client_ip(request))
        return success(_payload())


class AdminTestEmailView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request):
        data = TestEmailSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        to = data.validated_data.get("to", request.user.email)
        services.send_test_email(actor=request.user, to=to, ip=get_client_ip(request))
        return success({"detail": f"Test email sent to {to}."})
