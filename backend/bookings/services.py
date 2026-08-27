"""
Transaction-safe booking service.

This is the AUTHORITATIVE booking path. All capacity, duplicate,
and start-time invariants are enforced HERE inside an atomic
PostgreSQL transaction with row-level locking.

Flow:
    REQUEST → Authenticate → Validate input → Resolve request ID
    → Resolve idempotency key → BEGIN TRANSACTION
    → Lock session row (SELECT FOR UPDATE)
    → Check start time → Check duplicate → Count confirmed → Check capacity
    → Create booking → Create event → COMMIT → Return result

WHY SELECT FOR UPDATE:
    Without row locking, two concurrent transactions can both read
    capacity=1, confirmed=0, both decide "1 seat available", and both
    INSERT a booking — violating the capacity invariant.

    SELECT ... FOR UPDATE acquires a row-level exclusive lock on the
    session row. The second transaction blocks until the first commits
    or rolls back, then re-reads the updated count. This guarantees
    confirmed_bookings <= capacity.

See DECISIONS.md for full concurrency strategy documentation.
"""
import logging
import uuid

from django.db import transaction, IntegrityError
from django.utils import timezone

from sessions_app.models import Session
from .models import Booking, BookingEvent, IdempotencyRecord

logger = logging.getLogger("bookings")


class BookingError:
    """Structured error for booking failures."""

    def __init__(self, code, message, status_code, request_id=""):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.request_id = request_id

    def to_response_body(self):
        body = {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }
        if self.request_id:
            body["error"]["request_id"] = self.request_id
        return body


class BookingResult:
    """Structured result for successful bookings."""

    def __init__(self, booking, request_id="", was_idempotent_replay=False):
        self.booking = booking
        self.request_id = request_id
        self.was_idempotent_replay = was_idempotent_replay


def create_booking(user, session_id, request_id="", idempotency_key=None):
    """
    Create a booking inside a transaction-safe atomic block.

    Returns BookingResult on success, BookingError on failure.

    This function is the SINGLE authoritative path for booking creation.
    No booking should be created outside this function.
    """
    if not request_id:
        request_id = f"req_{uuid.uuid4().hex[:12]}"

    logger.info(
        "Booking attempt: user=%s session=%s request_id=%s idempotency_key=%s",
        user.id, session_id, request_id,
        idempotency_key[:8] + "..." if idempotency_key else "none",
    )

    # ── Idempotency check (before transaction) ────────────────
    if idempotency_key:
        try:
            existing = IdempotencyRecord.objects.get(key=idempotency_key, user=user)
            # Same key found — check if it's for the same session
            existing_session_id = existing.session_id or existing.response_body.get("original_session_id")
            if existing_session_id and existing_session_id != session_id:
                return BookingError(
                    code="IDEMPOTENCY_CONFLICT",
                    message="This idempotency key was already used for a different session.",
                    status_code=409,
                    request_id=request_id,
                )
            # Replay — return the original result
            logger.info("Idempotency replay: key=%s request_id=%s", idempotency_key[:8], request_id)
            if existing.booking:
                return BookingResult(
                    booking=existing.booking,
                    request_id=request_id,
                    was_idempotent_replay=True,
                )
            else:
                # Original request was a rejection — replay the rejection
                return BookingError(
                    code=existing.response_body.get("error", {}).get("code", "UNKNOWN"),
                    message=existing.response_body.get("error", {}).get("message", "Booking was previously rejected."),
                    status_code=existing.response_status,
                    request_id=request_id,
                )
        except IdempotencyRecord.DoesNotExist:
            pass  # New key — proceed normally

    # ── Atomic transaction with row locking ───────────────────
    try:
        with transaction.atomic():
            # Lock the session row — this is the critical concurrency control.
            # Any concurrent transaction trying to book the same session
            # will BLOCK here until this transaction completes.
            try:
                session = (
                    Session.objects
                    .select_for_update()
                    .get(pk=session_id)
                )
            except Session.DoesNotExist:
                _record_idempotency(idempotency_key, user, session_id, None, 404, "SESSION_NOT_FOUND", request_id)
                return BookingError(
                    code="SESSION_NOT_FOUND",
                    message="Session not found.",
                    status_code=404,
                    request_id=request_id,
                )

            # Check 1: Has the session already started?
            now = timezone.now()
            if session.start_time <= now:
                BookingEvent.objects.create(
                    event_type=BookingEvent.EventType.BOOKING_REJECTED_STARTED,
                    session=session,
                    user=user,
                    request_id=request_id,
                )
                _record_idempotency(idempotency_key, user, session_id, None, 400, "SESSION_STARTED", request_id)
                return BookingError(
                    code="SESSION_STARTED",
                    message="This session has already started and cannot be booked.",
                    status_code=400,
                    request_id=request_id,
                )

            # Check 2: Does this user already have an active booking?
            if Booking.objects.filter(
                user=user,
                session=session,
                status=Booking.Status.CONFIRMED,
            ).exists():
                BookingEvent.objects.create(
                    event_type=BookingEvent.EventType.BOOKING_REJECTED_DUPLICATE,
                    session=session,
                    user=user,
                    request_id=request_id,
                )
                _record_idempotency(idempotency_key, user, session_id, None, 409, "DUPLICATE_BOOKING", request_id)
                return BookingError(
                    code="DUPLICATE_BOOKING",
                    message="You already have an active booking for this session.",
                    status_code=409,
                    request_id=request_id,
                )

            # Check 3: Is there capacity remaining?
            confirmed_count = Booking.objects.filter(
                session=session,
                status=Booking.Status.CONFIRMED,
            ).count()

            if confirmed_count >= session.capacity:
                BookingEvent.objects.create(
                    event_type=BookingEvent.EventType.BOOKING_REJECTED_CAPACITY,
                    session=session,
                    user=user,
                    request_id=request_id,
                )
                _record_idempotency(idempotency_key, user, session_id, None, 409, "SESSION_FULL", request_id)
                return BookingError(
                    code="SESSION_FULL",
                    message="This session is full. Another booking completed before your request.",
                    status_code=409,
                    request_id=request_id,
                )

            # All checks passed — create the booking
            booking = Booking.objects.create(
                user=user,
                session=session,
                status=Booking.Status.CONFIRMED,
                idempotency_key=idempotency_key or "",
                request_id=request_id,
            )

            BookingEvent.objects.create(
                event_type=BookingEvent.EventType.BOOKING_CONFIRMED,
                session=session,
                booking=booking,
                user=user,
                request_id=request_id,
            )

            # Record idempotency for successful booking
            if idempotency_key:
                IdempotencyRecord.objects.create(
                    key=idempotency_key,
                    user=user,
                    booking=booking,
                    session=session,
                    response_status=201,
                    response_body={
                        "id": booking.id,
                        "session_id": session.id,
                        "status": "CONFIRMED",
                    },
                )

            logger.info(
                "Booking confirmed: booking=%s user=%s session=%s request_id=%s (count: %d/%d)",
                booking.id, user.id, session.id, request_id,
                confirmed_count + 1, session.capacity,
            )

            return BookingResult(
                booking=booking,
                request_id=request_id,
            )

    except IntegrityError as e:
        # Database constraint caught a race condition that passed
        # application-level checks. This is the safety net.
        logger.warning(
            "IntegrityError during booking (safety net caught race): user=%s session=%s error=%s",
            user.id, session_id, str(e)[:100],
        )
        if "unique_confirmed_booking_per_user_session" in str(e):
            return BookingError(
                code="DUPLICATE_BOOKING",
                message="You already have an active booking for this session.",
                status_code=409,
                request_id=request_id,
            )
        return BookingError(
            code="SESSION_FULL",
            message="This session just became full. Another booking completed before your request.",
            status_code=409,
            request_id=request_id,
        )


def _record_idempotency(key, user, session_id, booking, status_code, error_code, request_id):
    """Record idempotency for rejected attempts too."""
    if not key:
        return
    try:
        original_session_id = session_id
        # If the session doesn't exist, we can't use its ID for the foreign key.
        if error_code == "SESSION_NOT_FOUND":
            session_id = None
            
        IdempotencyRecord.objects.get_or_create(
            key=key,
            user=user,
            defaults={
                "booking": booking,
                "session_id": session_id,
                "response_status": status_code,
                "response_body": {
                    "original_session_id": original_session_id,
                    "error": {
                        "code": error_code,
                        "message": "",
                        "request_id": request_id,
                    }
                },
            },
        )
    except Exception:
        logger.exception("Failed to record idempotency for key=%s", key[:8] if key else "none")
