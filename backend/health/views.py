from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Liveness check — application is running."""
    return Response({"status": "healthy"})


@api_view(["GET"])
@permission_classes([AllowAny])
def readiness(request):
    """Readiness check — PostgreSQL is available."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return Response({"status": "ready", "database": "connected"})
    except Exception:
        return Response(
            {"status": "not ready", "database": "unavailable"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
