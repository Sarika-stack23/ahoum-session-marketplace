"""
Booking tests — edge cases and invariant verification.

These tests verify:
1. Successful booking
2. Session full (capacity protection)
3. Duplicate booking prevention
4. Started session rejection
5. Unauthenticated booking rejection
6. Active vs past bookings classification
7. Idempotency key behavior
8. Error response format stability
"""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from sessions_app.models import Session
from bookings.models import Booking, BookingEvent


class BookingTestCase(TestCase):
    """Core booking behavior tests."""

    def setUp(self):
        self.client = APIClient()
        self.creator = User.objects.create_user(
            username="creator", password="pass123", role=User.Role.CREATOR,
        )
        self.user = User.objects.create_user(
            username="booker", password="pass123", role=User.Role.USER,
        )
        self.user2 = User.objects.create_user(
            username="booker2", password="pass123", role=User.Role.USER,
        )
        self.session = Session.objects.create(
            creator=self.creator,
            title="Test Session",
            start_time=timezone.now() + timedelta(days=1),
            capacity=2,
        )
        self._auth_as(self.user)

    def _auth_as(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_successful_booking(self):
        """User can book a session with available capacity."""
        response = self.client.post(f"/api/bookings/session/{self.session.id}/book/")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Booking.objects.filter(status="CONFIRMED").count(), 1)

    def test_booking_creates_event(self):
        """Successful booking creates a BOOKING_CONFIRMED event."""
        self.client.post(f"/api/bookings/session/{self.session.id}/book/")
        self.assertTrue(
            BookingEvent.objects.filter(
                event_type=BookingEvent.EventType.BOOKING_CONFIRMED
            ).exists()
        )

    def test_session_full_rejection(self):
        """Booking is rejected when session is at capacity."""
        # Fill session (capacity=2)
        Booking.objects.create(user=self.user, session=self.session, status="CONFIRMED")
        Booking.objects.create(user=self.user2, session=self.session, status="CONFIRMED")

        user3 = User.objects.create_user(username="booker3", password="pass123")
        self._auth_as(user3)
        response = self.client.post(f"/api/bookings/session/{self.session.id}/book/")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "SESSION_FULL")

    def test_duplicate_booking_rejection(self):
        """Same user cannot book same session twice."""
        self.client.post(f"/api/bookings/session/{self.session.id}/book/")
        response = self.client.post(f"/api/bookings/session/{self.session.id}/book/")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "DUPLICATE_BOOKING")

    def test_started_session_rejection(self):
        """Cannot book a session that has already started."""
        past_session = Session.objects.create(
            creator=self.creator,
            title="Already Started",
            start_time=timezone.now() - timedelta(hours=1),
            capacity=10,
        )
        response = self.client.post(f"/api/bookings/session/{past_session.id}/book/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "SESSION_STARTED")

    def test_nonexistent_session_returns_404(self):
        """Booking a non-existent session returns SESSION_NOT_FOUND."""
        response = self.client.post("/api/bookings/session/99999/book/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"]["code"], "SESSION_NOT_FOUND")

    def test_cancelled_booking_does_not_block_new_booking(self):
        """A cancelled booking frees the duplicate constraint."""
        # Book then cancel
        self.client.post(f"/api/bookings/session/{self.session.id}/book/")
        booking = Booking.objects.first()
        booking.status = Booking.Status.CANCELLED
        booking.save()

        # Should be able to book again
        response = self.client.post(f"/api/bookings/session/{self.session.id}/book/")
        self.assertEqual(response.status_code, 201)

    def test_cancelled_booking_frees_capacity(self):
        """Cancelled bookings don't count toward capacity."""
        # Fill capacity
        Booking.objects.create(user=self.user, session=self.session, status="CONFIRMED")
        Booking.objects.create(user=self.user2, session=self.session, status="CONFIRMED")

        # Cancel one
        b = Booking.objects.filter(user=self.user).first()
        b.status = Booking.Status.CANCELLED
        b.save()

        # New user should be able to book
        user3 = User.objects.create_user(username="booker3", password="pass123")
        self._auth_as(user3)
        response = self.client.post(f"/api/bookings/session/{self.session.id}/book/")
        self.assertEqual(response.status_code, 201)


class BookingListTestCase(TestCase):
    """Test active/past booking classification."""

    def setUp(self):
        self.client = APIClient()
        self.creator = User.objects.create_user(
            username="creator", password="pass123", role=User.Role.CREATOR,
        )
        self.user = User.objects.create_user(
            username="booker", password="pass123", role=User.Role.USER,
        )
        token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_active_bookings(self):
        """Active bookings are confirmed for future sessions."""
        future_session = Session.objects.create(
            creator=self.creator,
            title="Future",
            start_time=timezone.now() + timedelta(days=1),
            capacity=10,
        )
        Booking.objects.create(user=self.user, session=future_session, status="CONFIRMED")

        response = self.client.get("/api/bookings/mine/?status=active")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_past_bookings(self):
        """Past bookings are for sessions that already started."""
        past_session = Session.objects.create(
            creator=self.creator,
            title="Past",
            start_time=timezone.now() - timedelta(hours=1),
            capacity=10,
        )
        Booking.objects.create(user=self.user, session=past_session, status="CONFIRMED")

        response = self.client.get("/api/bookings/mine/?status=past")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)


class IdempotencyTestCase(TestCase):
    """Test idempotency key behavior."""

    def setUp(self):
        self.client = APIClient()
        self.creator = User.objects.create_user(
            username="creator", password="pass123", role=User.Role.CREATOR,
        )
        self.user = User.objects.create_user(
            username="booker", password="pass123", role=User.Role.USER,
        )
        self.session = Session.objects.create(
            creator=self.creator,
            title="Test Session",
            start_time=timezone.now() + timedelta(days=1),
            capacity=5,
        )
        token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_same_idempotency_key_returns_same_booking(self):
        """Repeating a request with the same idempotency key doesn't duplicate."""
        headers = {"HTTP_IDEMPOTENCY_KEY": "test-key-123"}
        r1 = self.client.post(
            f"/api/bookings/session/{self.session.id}/book/",
            **headers,
        )
        self.assertEqual(r1.status_code, 201)

        r2 = self.client.post(
            f"/api/bookings/session/{self.session.id}/book/",
            **headers,
        )
        # Should return the same booking, not create a new one
        self.assertEqual(r2.status_code, 201)
        self.assertTrue(r2.data.get("idempotent_replay"))
        self.assertEqual(Booking.objects.filter(status="CONFIRMED").count(), 1)

    def test_different_session_with_same_key_returns_conflict(self):
        """Using the same idempotency key for a different session → conflict."""
        session2 = Session.objects.create(
            creator=self.creator,
            title="Other Session",
            start_time=timezone.now() + timedelta(days=2),
            capacity=5,
        )
        headers = {"HTTP_IDEMPOTENCY_KEY": "shared-key-456"}
        self.client.post(
            f"/api/bookings/session/{self.session.id}/book/",
            **headers,
        )
        response = self.client.post(
            f"/api/bookings/session/{session2.id}/book/",
            **headers,
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "IDEMPOTENCY_CONFLICT")


class ErrorFormatTestCase(TestCase):
    """Test that error responses follow the consistent format."""

    def setUp(self):
        self.client = APIClient()

    def test_401_error_format(self):
        """Unauthenticated error has correct structure."""
        response = self.client.get("/api/auth/profile/")
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.data)
        self.assertIn("code", response.data["error"])
        self.assertIn("message", response.data["error"])

    def test_booking_error_has_request_id(self):
        """Booking errors include request_id for debugging."""
        user = User.objects.create_user(username="tester", password="pass123")
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.post("/api/bookings/session/99999/book/")
        self.assertEqual(response.status_code, 404)
        self.assertIn("request_id", response.data["error"])
