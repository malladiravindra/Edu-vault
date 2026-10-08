import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.utils import InterfaceError, OperationalError
from django.http import Http404
from redis.exceptions import RedisError
from rest_framework import exceptions, status
from rest_framework.views import exception_handler

from .responses import error_response

logger = logging.getLogger(__name__)


class ServiceError(exceptions.APIException):
    """Business-rule failure raised from services and rendered in the standard error envelope."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, code, message, status_code=None, details=None):
        super().__init__(detail=message, code=code)
        self.code = code
        self.message = message
        self.details = details or {}
        if status_code is not None:
            self.status_code = status_code


_CODES = {
    exceptions.NotAuthenticated: ("NOT_AUTHENTICATED", "Authentication credentials were not provided or are invalid."),
    exceptions.AuthenticationFailed: ("AUTHENTICATION_FAILED", "Authentication failed."),
    exceptions.PermissionDenied: ("PERMISSION_DENIED", "You do not have permission to perform this action."),
    exceptions.NotFound: ("NOT_FOUND", "The requested resource was not found."),
    exceptions.MethodNotAllowed: ("METHOD_NOT_ALLOWED", "Method not allowed."),
    exceptions.ParseError: ("PARSE_ERROR", "Malformed request body."),
    exceptions.UnsupportedMediaType: ("UNSUPPORTED_MEDIA_TYPE", "Unsupported media type."),
    exceptions.NotAcceptable: ("NOT_ACCEPTABLE", "Not acceptable."),
}


def api_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    if isinstance(exc, DjangoValidationError):
        return error_response(
            "VALIDATION_ERROR", "The request data is invalid.", status.HTTP_400_BAD_REQUEST, {"fields": exc.messages}
        )

    if isinstance(exc, ServiceError):
        return error_response(exc.code, exc.message, exc.status_code, exc.details)

    if isinstance(exc, exceptions.ValidationError):
        return error_response(
            "VALIDATION_ERROR", "The request data is invalid.", status.HTTP_400_BAD_REQUEST, {"fields": exc.detail}
        )

    if isinstance(exc, exceptions.Throttled):
        details = {"retry_after": exc.wait} if exc.wait is not None else {}
        return error_response("RATE_LIMITED", "Too many requests. Please try again later.", 429, details)

    if isinstance(exc, exceptions.APIException):
        # simplejwt invalid-token errors carry their own machine code in the detail.
        code, message = None, None
        for klass, value in _CODES.items():
            if isinstance(exc, klass):
                code, message = value
                break
        if isinstance(exc, (exceptions.AuthenticationFailed, exceptions.NotAuthenticated, exceptions.PermissionDenied)):
            detail = exc.detail
            raw = detail.get("code") if isinstance(detail, dict) else getattr(detail, "code", None)
            if raw and raw not in ("authentication_failed", "not_authenticated", "permission_denied"):
                code = str(raw).upper()
                if not isinstance(detail, dict):
                    message = str(detail)
        response = exception_handler(exc, context)
        status_code = response.status_code if response is not None else exc.status_code
        headers = dict(response.items()) if response is not None else {}
        out = error_response(code or "API_ERROR", message or "The request could not be processed.", status_code)
        for key, value in headers.items():
            out[key] = value
        return out

    if isinstance(exc, (OperationalError, InterfaceError, RedisError)):
        logger.error("Dependency unavailable in %s: %s", context.get("view").__class__.__name__, type(exc).__name__)
        return error_response(
            "SERVICE_UNAVAILABLE", "A required service is temporarily unavailable. Please try again shortly.", 503
        )

    logger.exception("Unhandled exception in %s", context.get("view").__class__.__name__)
    return error_response("INTERNAL_ERROR", "An unexpected error occurred.", status.HTTP_500_INTERNAL_SERVER_ERROR)
