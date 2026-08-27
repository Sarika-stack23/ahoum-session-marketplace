"""
Session CRUD and public catalog tests.
"""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from sessions_app.models import Session


class SessionPublicTestCase(TestCase):
    """Test public (unauthenticated) session access."""

    def setUp(self):
        self.client = APIClient()
        self.creator = User.objects.create_user(
            username="creator",
            email="creator@example.com",
            password="testpass123",
            role=User.Role.CREATOR,
        )
        self.session = Session.objects.create(
            creator=self.creator,
            title="Public Session",
            description="Description here",
            start_time=timezone.now() + timedelta(days=1),
            capacity=10,
        )

    def test_public_session_list(self):
        """Anyone can view the session catalog."""
        response = self.client.get("/api/sessions/")
        self.assertEqual(response.status_code, 200)

    def test_public_session_detail(self):
        """Anyone can view session detail."""
        response = self.client.get(f"/api/sessions/{self.session.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], "Public Session")
        self.assertIn("booked_count", response.data)
        self.assertIn("remaining_seats", response.data)
        self.assertIn("has_started", response.data)

    def test_nonexistent_session_returns_404(self):
        """Requesting non-existent session returns 404."""
        response = self.client.get("/api/sessions/99999/")
        self.assertEqual(response.status_code, 404)


class SessionCreatorCRUDTestCase(TestCase):
    """Test Creator session management."""

    def setUp(self):
        self.client = APIClient()
        self.creator = User.objects.create_user(
            username="creator",
            email="creator@example.com",
            password="testpass123",
            role=User.Role.CREATOR,
        )
        token = str(RefreshToken.for_user(self.creator).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_creator_create_session(self):
        """Creator can create a session."""
        response = self.client.post("/api/sessions/create/", {
            "title": "New Session",
            "description": "Test description",
            "start_time": (timezone.now() + timedelta(days=1)).isoformat(),
            "capacity": 5,
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Session.objects.count(), 1)
        # Creator is set server-side
        session = Session.objects.first()
        self.assertEqual(session.creator, self.creator)

    def test_creator_cannot_create_session_in_past(self):
        """Session with start_time in the past is rejected."""
        response = self.client.post("/api/sessions/create/", {
            "title": "Past Session",
            "description": "Should fail",
            "start_time": (timezone.now() - timedelta(days=1)).isoformat(),
            "capacity": 5,
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_creator_list_own_sessions(self):
        """Creator can list their own sessions."""
        Session.objects.create(
            creator=self.creator,
            title="My Session",
            start_time=timezone.now() + timedelta(days=1),
            capacity=5,
        )
        response = self.client.get("/api/sessions/mine/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
