"""
Custom exception handler for consistent API error responses.

All errors follow this structure:
{
    "error": {
        "code": "ERROR_CODE",
        "message": "Human-readable message",
        "request_id": "req_abc123"
    }
}
"""
from rest_framework.views import exception_handler
from rest_framework import status


# Map DRF exception codes to our error codes
STATUS_CODE_MAP = {
    status.HTTP_401_UNAUTHORIZED: "INVALID_TOKEN",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
    status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
}


def custom_exception_handler(exc, context):
    """
    Wraps DRF's default exception handler to produce consistent
    error response structure with request IDs.
    """
    response = exception_handler(exc, context)

    if response is None:
        return response

    request = context.get("request")
    request_id = getattr(request, "request_id", None) if request else None

    # Determine error code
    error_code = STATUS_CODE_MAP.get(response.status_code, "VALIDATION_ERROR")

    # Extract message from DRF response
    if isinstance(response.data, dict):
        detail = response.data.get("detail", "")
        if detail:
            message = str(detail)
        else:
            # Field validation errors — flatten to readable message
            messages = []
            for field, errors in response.data.items():
                if isinstance(errors, list):
                    for err in errors:
                        messages.append(f"{field}: {err}")
                else:
                    messages.append(f"{field}: {errors}")
            message = "; ".join(messages) if messages else "Validation error"
            error_code = "VALIDATION_ERROR"
    elif isinstance(response.data, list):
        message = "; ".join(str(e) for e in response.data)
    else:
        message = str(response.data)

    # Check for expired token specifically
    if response.status_code == 401:
        code_value = ""
        if isinstance(response.data, dict):
            code_value = response.data.get("code", "")
        if code_value == "token_not_valid":
            error_code = "TOKEN_EXPIRED"
            message = "Your session has expired. Please log in again."

    error_body = {
        "error": {
            "code": error_code,
            "message": message,
        }
    }

    if request_id:
        error_body["error"]["request_id"] = request_id

    response.data = error_body
    return response
