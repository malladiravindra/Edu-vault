from rest_framework import status as http
from rest_framework.response import Response


def success(data=None, meta=None, status=http.HTTP_200_OK):
    return Response({"success": True, "data": {} if data is None else data, "meta": meta or {}}, status=status)


def error_response(code, message, status, details=None):
    return Response(
        {"success": False, "error": {"code": code, "message": message, "details": details or {}}},
        status=status,
    )
