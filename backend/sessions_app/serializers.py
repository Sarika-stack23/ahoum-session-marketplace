"""
Session serializers.

booked_count and remaining_seats are computed from confirmed bookings.
These are INFORMATIONAL — the backend transaction is authoritative.
"""
from django.utils import timezone
from rest_framework import serializers
from .models import Session


class SessionListSerializer(serializers.ModelSerializer):
    """Compact representation for catalog listing."""

    creator_name = serializers.CharField(source="creator.username", read_only=True)
    booked_count = serializers.SerializerMethodField()
    remaining_seats = serializers.SerializerMethodField()
    has_started = serializers.SerializerMethodField()

    class Meta:
        model = Session
        fields = [
            "id", "title", "description", "start_time", "capacity",
            "creator_name", "booked_count", "remaining_seats",
            "has_started", "created_at",
        ]

    def get_booked_count(self, obj):
        return obj.bookings.filter(status="CONFIRMED").count()

    def get_remaining_seats(self, obj):
        return max(0, obj.capacity - self.get_booked_count(obj))

    def get_has_started(self, obj):
        return obj.start_time <= timezone.now()


class SessionDetailSerializer(SessionListSerializer):
    """Full detail including creator info."""

    creator_avatar = serializers.CharField(source="creator.avatar_url", read_only=True)

    class Meta(SessionListSerializer.Meta):
        fields = SessionListSerializer.Meta.fields + ["creator_avatar", "updated_at"]


class SessionCreateUpdateSerializer(serializers.ModelSerializer):
    """For Creator CRUD operations. Creator is set server-side."""

    class Meta:
        model = Session
        fields = ["title", "description", "start_time", "capacity"]

    def validate_start_time(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("Start time must be in the future.")
        return value

    def validate_capacity(self, value):
        if value < 1:
            raise serializers.ValidationError("Capacity must be at least 1.")
        return value
