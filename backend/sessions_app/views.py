"""
Session views with backend-enforced ownership.

Public endpoints: list, detail (AllowAny)
Creator endpoints: create, update, delete (IsCreator + ownership check)

Creator A can NEVER modify Creator B's session, even via direct API call.
"""
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from accounts.permissions import IsCreator
from .models import Session
from .serializers import (
    SessionListSerializer,
    SessionDetailSerializer,
    SessionCreateUpdateSerializer,
)


class SessionListView(generics.ListAPIView):
    """Public session catalog — no authentication required."""

    permission_classes = [permissions.AllowAny]
    serializer_class = SessionListSerializer
    queryset = Session.objects.select_related("creator").all()


class SessionDetailView(generics.RetrieveAPIView):
    """Public session detail — no authentication required."""

    permission_classes = [permissions.AllowAny]
    serializer_class = SessionDetailSerializer
    queryset = Session.objects.select_related("creator").all()


class SessionCreateView(generics.CreateAPIView):
    """Creator creates a new session. Creator is set server-side."""

    permission_classes = [permissions.IsAuthenticated, IsCreator]
    serializer_class = SessionCreateUpdateSerializer

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)


class SessionUpdateView(generics.UpdateAPIView):
    """
    Creator updates their OWN session only.
    Ownership is enforced server-side — filtering queryset to
    only the requesting creator's sessions.
    """

    permission_classes = [permissions.IsAuthenticated, IsCreator]
    serializer_class = SessionCreateUpdateSerializer

    def get_queryset(self):
        return Session.objects.filter(creator=self.request.user)

    def handle_no_permission(self):
        """Return 403 instead of generic error."""
        return Response(
            {"error": {"code": "FORBIDDEN", "message": "Only creators can perform this action."}},
            status=status.HTTP_403_FORBIDDEN,
        )


class SessionDeleteView(generics.DestroyAPIView):
    """
    Creator deletes their OWN session only.
    Ownership enforced identically to update.
    """

    permission_classes = [permissions.IsAuthenticated, IsCreator]

    def get_queryset(self):
        return Session.objects.filter(creator=self.request.user)


class CreatorSessionListView(generics.ListAPIView):
    """Creator views their own sessions with booking counts."""

    permission_classes = [permissions.IsAuthenticated, IsCreator]
    serializer_class = SessionDetailSerializer

    def get_queryset(self):
        return Session.objects.filter(creator=self.request.user).select_related("creator")


class SessionIntegrityView(generics.RetrieveAPIView):
    """
    Booking Integrity Console endpoint.
    Only the Creator who owns the session can view this.
    Returns read-only engineering data about capacity and concurrency.
    """

    permission_classes = [permissions.IsAuthenticated, IsCreator]

    def get_queryset(self):
        return Session.objects.filter(creator=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        session = self.get_object()
        
        # Calculate invariant from real DB state
        # We must import Booking here to avoid circular imports if it's not imported at top
        from bookings.models import Booking, BookingEvent
        
        confirmed_bookings = Booking.objects.filter(
            session=session,
            status=Booking.Status.CONFIRMED
        ).count()
        
        invariant_pass = confirmed_bookings <= session.capacity
        
        # Get recent events
        events = BookingEvent.objects.filter(
            session=session
        ).select_related("user").order_by("-created_at")[:50]
        
        events_data = []
        for e in events:
            # We don't expose sensitive info, just request IDs and anonymized/username for tracing
            events_data.append({
                "timestamp": e.created_at,
                "event_type": e.event_type,
                "request_id": e.request_id,
                "booking_id": e.booking_id,
                # Safe debugging identifier
                "username": f"User {e.user.id}",
            })
            
        return Response({
            "session_id": session.id,
            "title": session.title,
            "capacity": session.capacity,
            "confirmed_bookings": confirmed_bookings,
            "remaining_seats": max(0, session.capacity - confirmed_bookings),
            "start_time": session.start_time,
            "invariant": {
                "name": "confirmed_bookings <= capacity",
                "status": "PASS" if invariant_pass else "FAIL",
                "confirmed_bookings": confirmed_bookings,
                "capacity": session.capacity,
            },
            "recent_booking_events": events_data
        })
