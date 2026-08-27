"""
Booking views.

All booking creation goes through the booking service which
handles transactions, locking, and invariant enforcement.
Views are thin wrappers for HTTP interface.
"""
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import Booking
from .serializers import BookingSerializer
from .services import create_booking, BookingError, BookingResult


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def book_session(request, session_id):
    """
    Book a session.

    Optional headers:
        Idempotency-Key: client-generated key for safe retries
        X-Request-ID: client correlation ID

    The actual booking logic (capacity, duplicates, locking) is in
    services.py — this view is just the HTTP interface.
    """
    idempotency_key = request.headers.get("Idempotency-Key", "")
    request_id = getattr(request, "request_id", "")

    result = create_booking(
        user=request.user,
        session_id=session_id,
        request_id=request_id,
        idempotency_key=idempotency_key or None,
    )

    if isinstance(result, BookingError):
        return Response(result.to_response_body(), status=result.status_code)

    serializer = BookingSerializer(result.booking)
    response_data = serializer.data
    if result.request_id:
        response_data["request_id"] = result.request_id
    if result.was_idempotent_replay:
        response_data["idempotent_replay"] = True

    return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def my_bookings(request):
    """
    List the authenticated user's bookings.

    Query params:
        status: "active" or "past" (default: all)

    Active = CONFIRMED booking for a session that hasn't started yet.
    Past = CONFIRMED booking for a session that has already started,
           OR any CANCELLED booking.
    """
    bookings = Booking.objects.filter(user=request.user).select_related(
        "session", "session__creator"
    )

    filter_type = request.query_params.get("status", "")
    now = timezone.now()

    if filter_type == "active":
        bookings = bookings.filter(
            status=Booking.Status.CONFIRMED,
            session__start_time__gt=now,
        )
    elif filter_type == "past":
        from django.db.models import Q
        bookings = bookings.filter(
            Q(session__start_time__lte=now) | Q(status=Booking.Status.CANCELLED)
        )

    bookings = bookings.order_by("-created_at")
    serializer = BookingSerializer(bookings, many=True)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def cancel_booking(request, booking_id):
    """Cancel a booking (user can only cancel their own)."""
    try:
        booking = Booking.objects.get(
            pk=booking_id,
            user=request.user,
            status=Booking.Status.CONFIRMED,
        )
    except Booking.DoesNotExist:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "Booking not found."}},
            status=status.HTTP_404_NOT_FOUND,
        )

    booking.status = Booking.Status.CANCELLED
    booking.save(update_fields=["status"])
    return Response({"message": "Booking cancelled successfully."})
