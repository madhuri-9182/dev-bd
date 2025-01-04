from rest_framework.views import exception_handler
from rest_framework.exceptions import PermissionDenied


def permission_denied_custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        if isinstance(exc, PermissionDenied):
            response.data = {
                "status": "failed",
                "message": "Permission denied",
                "errors": response.data.get("detail", "Permission denied"),
            }

    return response
