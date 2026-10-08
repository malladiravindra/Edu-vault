from django.http import JsonResponse


def _error(code, message, status):
    return JsonResponse({"success": False, "error": {"code": code, "message": message, "details": {}}}, status=status)


def not_found(request, exception=None):
    """Unknown URLs get the same JSON envelope as every other error (used when DEBUG is off)."""
    return _error("NOT_FOUND", "The requested resource was not found.", 404)


def server_error(request):
    return _error("INTERNAL_ERROR", "An unexpected error occurred.", 500)
