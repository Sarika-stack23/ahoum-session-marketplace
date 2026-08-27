"""
Request ID middleware.

Assigns a unique request ID (req_xxx) to every request for
correlation in logs and error responses. Clients can also send
X-Request-ID to correlate their own requests.

Never logs tokens, secrets, or sensitive data.
"""
import uuid


class RequestIDMiddleware:
    """Attach a request_id to every request for tracing."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Use client-provided ID or generate one
        request_id = request.headers.get("X-Request-ID", "")
        if not request_id:
            request_id = f"req_{uuid.uuid4().hex[:12]}"

        request.request_id = request_id

        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response
