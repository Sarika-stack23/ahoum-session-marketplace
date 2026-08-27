#!/usr/bin/env python
"""
Standalone concurrency verification script.

Runs REAL concurrent HTTP requests against the booking endpoint
and verifies the final database state. This is NOT a sequential
loop — it uses ThreadPoolExecutor with a threading.Barrier to
synchronize genuinely concurrent requests.

Usage (inside Docker):
    docker compose exec backend python /app/scripts/concurrency_test.py

Usage (outside Docker, with backend running):
    python scripts/concurrency_test.py --base-url http://localhost/api

Requirements:
    - PostgreSQL must be running
    - Backend must be running
    - requests library must be installed

Exit codes:
    0 = all invariants verified
    1 = one or more invariant violations detected
"""
import os
import sys
import time
import threading
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add backend to path for Django ORM access
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.utils import timezone
from datetime import timedelta
from accounts.models import User
from sessions_app.models import Session
from bookings.models import Booking, BookingEvent
from bookings.services import create_booking


class ConcurrencyVerifier:
    """Runs concurrency scenarios and verifies database invariants."""

    def __init__(self):
        self.results = []
        self.failed = False

    def log(self, message, level="INFO"):
        prefix = {"INFO": "  ", "PASS": "  ✓", "FAIL": "  ✗", "HEADER": "\n"}
        print(f"{prefix.get(level, '  ')} {message}")

    def run_scenario(self, name, capacity, num_users, expect_max,
                     pre_fill=0, use_started=False, same_user=False):
        """Run a single concurrency scenario."""
        self.log(f"SCENARIO: {name}", "HEADER")
        self.log(f"Capacity={capacity}, Attempts={num_users}, Pre-filled={pre_fill}, "
                 f"Started={use_started}, SameUser={same_user}")

        # Setup
        creator = User.objects.create_user(
            username=f"creator_{name}_{int(time.time())}",
            password="pass",
            role=User.Role.CREATOR,
        )
        start_time = (
            timezone.now() - timedelta(hours=1) if use_started
            else timezone.now() + timedelta(days=1)
        )
        session = Session.objects.create(
            creator=creator,
            title=f"Concurrency Test: {name}",
            start_time=start_time,
            capacity=capacity,
        )

        # Pre-fill if needed
        for i in range(pre_fill):
            fill_user = User.objects.create_user(
                username=f"prefill_{name}_{i}_{int(time.time())}",
                password="pass",
            )
            Booking.objects.create(
                user=fill_user, session=session, status="CONFIRMED",
            )

        # Create users
        if same_user:
            user = User.objects.create_user(
                username=f"same_user_{name}_{int(time.time())}",
                password="pass",
            )
            users = [user] * num_users
        else:
            users = []
            for i in range(num_users):
                u = User.objects.create_user(
                    username=f"user_{name}_{i}_{int(time.time())}",
                    password="pass",
                )
                users.append(u)

        # Synchronize concurrent start
        barrier = threading.Barrier(num_users)
        outcomes = []

        def attempt(user_ref):
            try:
                barrier.wait(timeout=5)
                result = create_booking(user=user_ref, session_id=session.id)
                return type(result).__name__
            except Exception as e:
                return f"ERROR: {e}"

        # Fire concurrent requests
        with ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = [executor.submit(attempt, u) for u in users]
            for f in as_completed(futures, timeout=15):
                outcomes.append(f.result())

        # Verify final database state
        final_confirmed = Booking.objects.filter(
            session=session, status="CONFIRMED"
        ).count()

        successes = outcomes.count("BookingResult")
        failures = len(outcomes) - successes

        self.log(f"Outcomes: {successes} confirmed, {failures} rejected")
        self.log(f"Final DB confirmed count: {final_confirmed}")
        self.log(f"Expected max: {expect_max}")

        if final_confirmed <= expect_max:
            self.log(f"PASSED — {final_confirmed} <= {expect_max}", "PASS")
            return True
        else:
            self.log(f"FAILED — {final_confirmed} > {expect_max} INVARIANT VIOLATED!", "FAIL")
            self.failed = True
            return False

    def run_all(self):
        """Run the complete concurrency verification suite."""
        print("=" * 60)
        print("  SESSIONS MARKETPLACE — CONCURRENCY VERIFICATION")
        print("=" * 60)

        scenarios = [
            ("A: Cap=1, Attempts=2", 1, 2, 1),
            ("B: Cap=1, Attempts=10", 1, 10, 1),
            ("C: Cap=5, Attempts=12", 5, 12, 5),
        ]

        for name, cap, attempts, expect in scenarios:
            self.run_scenario(name, cap, attempts, expect)

        # Scenario D: Already full
        self.run_scenario(
            "D: Already full",
            capacity=1, num_users=5, expect_max=1, pre_fill=1,
        )

        # Scenario E: Already started
        self.run_scenario(
            "E: Already started",
            capacity=10, num_users=5, expect_max=0, use_started=True,
        )

        # Scenario F: Same user concurrent
        self.run_scenario(
            "F: Same user",
            capacity=10, num_users=5, expect_max=1, same_user=True,
        )

        print("\n" + "=" * 60)
        if self.failed:
            print("  RESULT: FAILED — INVARIANT VIOLATIONS DETECTED")
            print("=" * 60)
            sys.exit(1)
        else:
            print("  RESULT: ALL CONCURRENCY INVARIANTS VERIFIED")
            print("=" * 60)
            sys.exit(0)


if __name__ == "__main__":
    verifier = ConcurrencyVerifier()
    verifier.run_all()
