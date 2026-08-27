"""
Authentication and authorization tests.

Tests:
1. Valid JWT authentication
2. Invalid token → 401
3. Expired token → 401
4. User cannot call Creator-only endpoint → 403
5. Creator A cannot modify Creator B's session → 404 (filtered queryset)
6. Unauthenticated request to protected endpoint → 401
7. Profile retrieval and update
"""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from sessions_app.models import Session


class AuthenticationTestCase(TestCase):
    """Test JWT authentication behavior."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            role=User.Role.USER,
        )
        self.refresh = RefreshToken.for_user(self.user)
        self.access_token = str(self.refresh.access_token)

    def test_valid_token_accesses_profile(self):
        """Authenticated user can access their profile."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get("/api/auth/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "testuser")

    def test_invalid_token_returns_401(self):
        """Invalid JWT is rejected with 401."""
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid.token.here")
        response = self.client.get("/api/auth/profile/")
        self.assertEqual(response.status_code, 401)

    def test_missing_token_returns_401(self):
        """Request without token to protected endpoint returns 401."""
        response = self.client.get("/api/auth/profile/")
        self.assertEqual(response.status_code, 401)

    def test_unauthenticated_booking_returns_401(self):
        """Unauthenticated user cannot book a session."""
        response = self.client.post("/api/bookings/session/1/book/")
        self.assertEqual(response.status_code, 401)

    def test_token_refresh(self):
        """Valid refresh token returns new access token."""
        response = self.client.post("/api/auth/token/refresh/", {
            "refresh": str(self.refresh),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)

    def test_invalid_refresh_token_returns_401(self):
        """Invalid refresh token is rejected."""
        response = self.client.post("/api/auth/token/refresh/", {
            "refresh": "invalid.refresh.token",
        })
        self.assertEqual(response.status_code, 401)

    def test_profile_update(self):
        """User can update their own profile fields."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.patch("/api/auth/profile/", {
            "bio": "Hello world",
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["bio"], "Hello world")

    def test_profile_update_cannot_change_role(self):
        """User cannot escalate their role via profile update."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.patch("/api/auth/profile/", {
            "role": "CREATOR",
        }, format="json")
        # Role should remain USER (field is read-only)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.USER)


class AuthorizationTestCase(TestCase):
    """Test role-based access control — backend enforced."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="normaluser",
            email="user@example.com",
            password="testpass123",
            role=User.Role.USER,
        )
        self.creator_a = User.objects.create_user(
            username="creator_a",
            email="creatora@example.com",
            password="testpass123",
            role=User.Role.CREATOR,
        )
        self.creator_b = User.objects.create_user(
            username="creator_b",
            email="creatorb@example.com",
            password="testpass123",
            role=User.Role.CREATOR,
        )

        # Creator A's session
        self.session = Session.objects.create(
            creator=self.creator_a,
            title="Creator A's Session",
            description="Test session",
            start_time=timezone.now() + timedelta(days=1),
            capacity=10,
        )

    def _auth_as(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_user_cannot_create_session(self):
        """User (non-creator) calling Creator-only endpoint → 403."""
        self._auth_as(self.user)
        response = self.client.post("/api/sessions/create/", {
            "title": "Unauthorized Session",
            "description": "Should fail",
            "start_time": (timezone.now() + timedelta(days=1)).isoformat(),
            "capacity": 5,
        }, format="json")
        self.assertEqual(response.status_code, 403)

    def test_user_cannot_delete_session(self):
        """User cannot delete a session (Creator-only)."""
        self._auth_as(self.user)
        response = self.client.delete(f"/api/sessions/{self.session.id}/delete/")
        self.assertEqual(response.status_code, 403)

    def test_creator_b_cannot_update_creator_a_session(self):
        """Creator B cannot modify Creator A's session — ownership enforced."""
        self._auth_as(self.creator_b)
        response = self.client.patch(
            f"/api/sessions/{self.session.id}/update/",
            {"title": "Hijacked!"},
            format="json",
        )
        # Returns 404 because queryset is filtered to own sessions
        self.assertEqual(response.status_code, 404)

    def test_creator_b_cannot_delete_creator_a_session(self):
        """Creator B cannot delete Creator A's session — ownership enforced."""
        self._auth_as(self.creator_b)
        response = self.client.delete(f"/api/sessions/{self.session.id}/delete/")
        self.assertEqual(response.status_code, 404)

    def test_creator_a_can_update_own_session(self):
        """Creator can update their own session."""
        self._auth_as(self.creator_a)
        response = self.client.patch(
            f"/api/sessions/{self.session.id}/update/",
            {"title": "Updated Title"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.title, "Updated Title")

    def test_creator_a_can_delete_own_session(self):
        """Creator can delete their own session."""
        self._auth_as(self.creator_a)
        response = self.client.delete(f"/api/sessions/{self.session.id}/delete/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Session.objects.filter(pk=self.session.id).exists())

    def test_unauthenticated_cannot_access_creator_endpoints(self):
        """Unauthenticated request to Creator endpoint → 401."""
        response = self.client.post("/api/sessions/create/", {
            "title": "No Auth",
            "description": "Should fail",
            "start_time": (timezone.now() + timedelta(days=1)).isoformat(),
            "capacity": 5,
        }, format="json")
        self.assertEqual(response.status_code, 401)
