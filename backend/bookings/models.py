"""
Booking models with database-level invariant enforcement.

INVARIANT 1: confirmed_bookings <= session.capacity
  → Enforced by: transaction + SELECT FOR UPDATE in services.py

INVARIANT 2: One active booking per (user, session)
  → Enforced by: PostgreSQL partial unique index + application validation

INVARIANT 3: No booking after session start_time
  → Enforced by: Application validation inside transaction

INVARIANT 4: Only authenticated users can book
  → Enforced by: DRF IsAuthenticated permission

INVARIANT 5: Booking results reflect committed database state
  → Enforced by: Atomic transaction with proper isolation

See DECISIONS.md for full invariant ownership documentation.
"""
from django.conf import settings
from django.db import models


class Booking(models.Model):
    """
    A confirmed seat reservation.

    The partial unique index on (user, session) WHERE status='CONFIRMED'
    is the database-level safety net for duplicate prevention.
    Application code checks first for friendly errors, but the
    constraint is the final guarantee.
    """

    class Status(models.TextChoices):
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    session = models.ForeignKey(
        "sessions_app.Session",
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.CONFIRMED,
        db_index=True,
    )
    idempotency_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="Client-provided key for safe retries.",
    )
    request_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Correlation ID for debugging.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bookings"
        indexes = [
            models.Index(fields=["user", "session"], name="idx_booking_user_session"),
        ]
        constraints = [
            # DATABASE-LEVEL duplicate prevention:
            # Only one CONFIRMED booking per (user, session).
            # This is the final safety net — application code checks first
            # for friendly error messages, but this constraint guarantees
            # correctness even under race conditions.
            models.UniqueConstraint(
                fields=["user", "session"],
                condition=models.Q(status="CONFIRMED"),
                name="unique_confirmed_booking_per_user_session",
            ),
        ]

    def __str__(self):
        return f"Booking #{self.id}: {self.user.username} → {self.session.title} ({self.status})"


class BookingEvent(models.Model):
    """
    Lightweight audit trail for booking outcomes.

    Records both successful and rejected booking attempts with
    enough context for debugging. Not an enterprise audit system —
    just enough to understand what happened.
    """

    class EventType(models.TextChoices):
        BOOKING_CONFIRMED = "BOOKING_CONFIRMED", "Booking Confirmed"
        BOOKING_REJECTED_CAPACITY = "BOOKING_REJECTED_CAPACITY", "Rejected: Capacity Full"
        BOOKING_REJECTED_DUPLICATE = "BOOKING_REJECTED_DUPLICATE", "Rejected: Duplicate"
        BOOKING_REJECTED_STARTED = "BOOKING_REJECTED_STARTED", "Rejected: Session Started"
        BOOKING_CANCELLED = "BOOKING_CANCELLED", "Booking Cancelled"

    event_type = models.CharField(max_length=30, choices=EventType.choices, db_index=True)
    session = models.ForeignKey(
        "sessions_app.Session",
        on_delete=models.CASCADE,
        related_name="booking_events",
    )
    booking = models.ForeignKey(
        Booking,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="booking_events",
    )
    request_id = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "booking_events"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event_type} | {self.user.username} | {self.session.title}"


class IdempotencyRecord(models.Model):
    """
    Tracks idempotency keys to prevent duplicate booking creation
    from retries, double-clicks, or network issues.

    Scoped to (user, key) — different users can use the same key string.
    """

    key = models.CharField(max_length=255)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="idempotency_records",
    )
    booking = models.ForeignKey(
        Booking,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    session = models.ForeignKey(
        "sessions_app.Session",
        on_delete=models.CASCADE,
    )
    response_status = models.IntegerField()
    response_body = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "idempotency_records"
        constraints = [
            models.UniqueConstraint(
                fields=["key", "user"],
                name="unique_idempotency_key_per_user",
            ),
        ]

    def __str__(self):
        return f"Idempotency: {self.key} | {self.user.username}"
