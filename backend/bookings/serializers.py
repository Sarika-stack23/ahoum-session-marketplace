from rest_framework import serializers
from .models import Booking, BookingEvent


class BookingSerializer(serializers.ModelSerializer):
    session_title = serializers.CharField(source="session.title", read_only=True)
    session_start_time = serializers.DateTimeField(source="session.start_time", read_only=True)
    session_id = serializers.IntegerField(source="session.id", read_only=True)
    creator_name = serializers.CharField(source="session.creator.username", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "session_id", "session_title", "session_start_time",
            "creator_name", "status", "request_id", "created_at",
        ]


class BookingEventSerializer(serializers.ModelSerializer):
    session_title = serializers.CharField(source="session.title", read_only=True)

    class Meta:
        model = BookingEvent
        fields = ["id", "event_type", "session_title", "request_id", "created_at"]
