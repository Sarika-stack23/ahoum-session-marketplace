"""
Concurrency tests using Django's TransactionTestCase.

WHY TransactionTestCase:
    Django's default TestCase wraps each test in a transaction and
    rolls it back. This means SELECT FOR UPDATE and concurrent
    transaction behavior cannot be tested — the lock is held by
    the test wrapper itself, and all operations happen in a single
    connection/transaction.

    TransactionTestCase uses real commits, which means:
    1. Each database operation is committed immediately
    2. Multiple threads can open separate connections
    3. SELECT FOR UPDATE actually blocks as it would in production

    The downside is slower tests (no transaction rollback), but
    concurrency correctness requires this trade-off.

These tests exercise the REAL booking service against PostgreSQL.
They use genuine concurrent threads, not sequential loops.

See DECISIONS.md for full concurrency strategy documentation.
"""
import threading
from datetime import timedelta

from django.test import TransactionTestCase
from django.utils import timezone

from accounts.models import User
from sessions_app.models import Session
from bookings.models import Booking
from bookings.services import create_booking


class ConcurrencyTestCase(TransactionTestCase):
    """
    Test booking concurrency safety with real PostgreSQL transactions.

    Uses TransactionTestCase (not TestCase) because:
    - TestCase wraps everything in a single transaction, defeating
      SELECT FOR UPDATE
    - We need multiple threads with separate DB connections to
      simulate real concurrent requests
    """

    def _create_users(self, count):
        """Create test users for concurrent booking attempts."""
        users = []
        for i in range(count):
            user = User.objects.create_user(
                username=f"concurrent_user_{i}",
                password="testpass123",
                role=User.Role.USER,
            )
            users.append(user)
        return users

    def test_scenario_a_capacity_1_attempts_2(self):
        """
        SCENARIO A: Capacity=1, 2 concurrent attempts.
        INVARIANT: final confirmed bookings <= 1
        """
        creator = User.objects.create_user(
            username="creator_a", password="pass", role=User.Role.CREATOR,
        )
        session = Session.objects.create(
            creator=creator,
            title="Scenario A",
            start_time=timezone.now() + timedelta(days=1),
            capacity=1,
        )
        users = self._create_users(2)
        results = []
        barrier = threading.Barrier(2)

        def attempt(user):
            barrier.wait()  # Synchronize start
            try:
                result = create_booking(user=user, session_id=session.id)
                results.append(result)
            finally:
                from django.db import connection; connection.close()

        threads = [threading.Thread(target=attempt, args=(u,)) for u in users]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # INVARIANT CHECK: query actual database state
        confirmed = Booking.objects.filter(
            session=session, status="CONFIRMED"
        ).count()
        self.assertLessEqual(confirmed, 1, f"INVARIANT VIOLATED: {confirmed} > 1")
        self.assertEqual(confirmed, 1, "Expected exactly 1 confirmed booking")

    def test_scenario_b_capacity_1_attempts_10(self):
        """
        SCENARIO B: Capacity=1, 10 concurrent attempts.
        INVARIANT: final confirmed bookings <= 1
        """
        creator = User.objects.create_user(
            username="creator_b", password="pass", role=User.Role.CREATOR,
        )
        session = Session.objects.create(
            creator=creator,
            title="Scenario B",
            start_time=timezone.now() + timedelta(days=1),
            capacity=1,
        )
        users = self._create_users(10)
        barrier = threading.Barrier(10)

        def attempt(user):
            barrier.wait()
            try:
                create_booking(user=user, session_id=session.id)
            finally:
                from django.db import connection; connection.close()

        threads = [threading.Thread(target=attempt, args=(u,)) for u in users]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        confirmed = Booking.objects.filter(
            session=session, status="CONFIRMED"
        ).count()
        self.assertLessEqual(confirmed, 1, f"INVARIANT VIOLATED: {confirmed} > 1")

    def test_scenario_c_capacity_5_attempts_10(self):
        """
        SCENARIO C: Capacity=5, 10+ concurrent attempts.
        INVARIANT: final confirmed bookings <= 5
        """
        creator = User.objects.create_user(
            username="creator_c", password="pass", role=User.Role.CREATOR,
        )
        session = Session.objects.create(
            creator=creator,
            title="Scenario C",
            start_time=timezone.now() + timedelta(days=1),
            capacity=5,
        )
        users = self._create_users(12)
        barrier = threading.Barrier(12)

        def attempt(user):
            barrier.wait()
            try:
                create_booking(user=user, session_id=session.id)
            finally:
                from django.db import connection; connection.close()

        threads = [threading.Thread(target=attempt, args=(u,)) for u in users]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        confirmed = Booking.objects.filter(
            session=session, status="CONFIRMED"
        ).count()
        self.assertLessEqual(confirmed, 5, f"INVARIANT VIOLATED: {confirmed} > 5")
        self.assertEqual(confirmed, 5, "Expected exactly 5 confirmed bookings")

    def test_scenario_d_already_full(self):
        """
        SCENARIO D: Session already full, concurrent attempts.
        INVARIANT: no new confirmed bookings.
        """
        creator = User.objects.create_user(
            username="creator_d", password="pass", role=User.Role.CREATOR,
        )
        session = Session.objects.create(
            creator=creator,
            title="Scenario D",
            start_time=timezone.now() + timedelta(days=1),
            capacity=1,
        )
        # Pre-fill the session
        existing_user = User.objects.create_user(
            username="existing", password="pass",
        )
        Booking.objects.create(
            user=existing_user, session=session, status="CONFIRMED",
        )

        users = self._create_users(5)
        barrier = threading.Barrier(5)

        def attempt(user):
            barrier.wait()
            try:
                create_booking(user=user, session_id=session.id)
            finally:
                from django.db import connection; connection.close()

        threads = [threading.Thread(target=attempt, args=(u,)) for u in users]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        confirmed = Booking.objects.filter(
            session=session, status="CONFIRMED"
        ).count()
        self.assertEqual(confirmed, 1, "No new bookings should be created")

    def test_scenario_e_already_started(self):
        """
        SCENARIO E: Session already started, concurrent attempts.
        INVARIANT: no new bookings at all.
        """
        creator = User.objects.create_user(
            username="creator_e", password="pass", role=User.Role.CREATOR,
        )
        session = Session.objects.create(
            creator=creator,
            title="Scenario E - Started",
            start_time=timezone.now() - timedelta(hours=1),
            capacity=10,
        )
        users = self._create_users(5)
        barrier = threading.Barrier(5)

        def attempt(user):
            barrier.wait()
            try:
                create_booking(user=user, session_id=session.id)
            finally:
                from django.db import connection; connection.close()

        threads = [threading.Thread(target=attempt, args=(u,)) for u in users]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        confirmed = Booking.objects.filter(
            session=session, status="CONFIRMED"
        ).count()
        self.assertEqual(confirmed, 0, "Started session should reject all bookings")

    def test_scenario_f_same_user_concurrent(self):
        """
        SCENARIO F: Same user, repeated concurrent booking attempts.
        INVARIANT: one active booking maximum.
        """
        creator = User.objects.create_user(
            username="creator_f", password="pass", role=User.Role.CREATOR,
        )
        session = Session.objects.create(
            creator=creator,
            title="Scenario F",
            start_time=timezone.now() + timedelta(days=1),
            capacity=10,
        )
        user = User.objects.create_user(
            username="duplicate_tester", password="pass",
        )
        barrier = threading.Barrier(5)

        def attempt():
            barrier.wait()
            try:
                create_booking(user=user, session_id=session.id)
            finally:
                from django.db import connection; connection.close()

        threads = [threading.Thread(target=attempt) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        confirmed = Booking.objects.filter(
            user=user, session=session, status="CONFIRMED"
        ).count()
        self.assertLessEqual(confirmed, 1, f"DUPLICATE VIOLATED: {confirmed} > 1")
        self.assertEqual(confirmed, 1, "Expected exactly 1 booking for same user")
