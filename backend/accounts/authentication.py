from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication


class SessionAwareJWTAuthentication(JWTAuthentication):
    """JWT auth that also enforces server-side inactivity timeout (state kept in Redis)."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        from . import (
            services,  # deferred: services -> core.exceptions -> rest_framework.views
        )

        user, token = result
        if not services.token_session_is_live(user.id, token):
            raise exceptions.AuthenticationFailed("Session expired due to inactivity.", code="session_expired")
        return result
