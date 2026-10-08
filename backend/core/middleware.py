from django.conf import settings
from django.http import Http404
from django.http.request import split_domain_port


class AdminSiteHostGuardMiddleware:
    """The built-in Django admin (/admin/) is internal: serve it only on the hostnames in DJANGO_ADMIN_ALLOWED_HOSTS.

    Its sign-in is a Django session (password only, throttled by the shared login lockout), so it is an internal tool: it must not be reachable through a public tunnel or domain.
    The EduVault admin API under /api/admin/ is a different thing and is not affected.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info == "/admin" or request.path_info.startswith("/admin/"):
            host, _port = split_domain_port(request.get_host())
            if host not in settings.DJANGO_ADMIN_ALLOWED_HOSTS:
                raise Http404
        return self.get_response(request)
