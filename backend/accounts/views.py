"""
Authentication views: GitHub OAuth + JWT.

Flow:
1. Frontend redirects user to GitHub's OAuth page
2. GitHub redirects back with ?code=xxx
3. Frontend sends code to /api/auth/github/callback/
4. Backend exchanges code for GitHub access token
5. Backend fetches GitHub user profile
6. Backend creates/updates local User
7. Backend issues JWT access + refresh tokens
8. Frontend stores tokens and uses them for API calls
"""
import logging
import requests
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import UserSerializer, ProfileUpdateSerializer

logger = logging.getLogger(__name__)

GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


@api_view(["POST"])
@permission_classes([AllowAny])
def github_callback(request):
    """
    Exchange GitHub OAuth code for JWT tokens.

    Expects: {"code": "github_auth_code"}
    Returns: {"access": "...", "refresh": "...", "user": {...}}
    """
    code = request.data.get("code")
    if not code:
        return Response(
            {"error": {"code": "VALIDATION_ERROR", "message": "GitHub code is required."}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Step 1: Exchange code for GitHub access token
    try:
        token_response = requests.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
            timeout=10,
        )
        token_data = token_response.json()
    except requests.RequestException:
        logger.exception("Failed to exchange GitHub code for token")
        return Response(
            {"error": {"code": "OAUTH_FAILED", "message": "Could not connect to GitHub."}},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    if "error" in token_data:
        error_desc = token_data.get("error_description", "OAuth authentication failed.")
        logger.warning("GitHub OAuth error: %s", error_desc)
        return Response(
            {"error": {"code": "OAUTH_FAILED", "message": error_desc}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    github_access_token = token_data.get("access_token")
    if not github_access_token:
        return Response(
            {"error": {"code": "OAUTH_FAILED", "message": "No access token received from GitHub."}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Step 2: Fetch GitHub user profile
    try:
        headers = {"Authorization": f"Bearer {github_access_token}"}
        user_response = requests.get(GITHUB_USER_URL, headers=headers, timeout=10)
        github_user = user_response.json()

        # Fetch primary email if not public
        email = github_user.get("email")
        if not email:
            emails_response = requests.get(GITHUB_EMAILS_URL, headers=headers, timeout=10)
            emails = emails_response.json()
            primary = next((e for e in emails if e.get("primary")), None)
            email = primary["email"] if primary else None
    except requests.RequestException:
        logger.exception("Failed to fetch GitHub user profile")
        return Response(
            {"error": {"code": "OAUTH_FAILED", "message": "Could not fetch your GitHub profile."}},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    github_id = github_user.get("id")
    username = github_user.get("login", "")
    avatar_url = github_user.get("avatar_url", "")

    if not github_id:
        return Response(
            {"error": {"code": "OAUTH_FAILED", "message": "Invalid GitHub user data."}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Step 3: Create or update local user
    user, created = User.objects.get_or_create(
        github_id=github_id,
        defaults={
            "username": _unique_username(username),
            "email": email or "",
            "avatar_url": avatar_url,
        },
    )

    if not created:
        # Update profile on each login
        user.avatar_url = avatar_url
        if email:
            user.email = email
        user.save(update_fields=["avatar_url", "email"])

    # Step 4: Auto-assign Creator role if email is in CREATOR_EMAILS
    if created and email and email.lower() in [e.lower() for e in settings.CREATOR_EMAILS]:
        user.role = User.Role.CREATOR
        user.save(update_fields=["role"])
        logger.info("Auto-assigned CREATOR role to %s (email match)", user.username)

    # Step 5: Issue JWT tokens
    refresh = RefreshToken.for_user(user)

    return Response({
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": UserSerializer(user).data,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def token_refresh(request):
    """
    Refresh an access token using a valid refresh token.

    Expects: {"refresh": "..."}
    Returns: {"access": "...", "refresh": "..."}
    """
    refresh_token = request.data.get("refresh")
    if not refresh_token:
        return Response(
            {"error": {"code": "VALIDATION_ERROR", "message": "Refresh token is required."}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        refresh = RefreshToken(refresh_token)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })
    except Exception:
        return Response(
            {"error": {"code": "TOKEN_EXPIRED", "message": "Refresh token is invalid or expired."}},
            status=status.HTTP_401_UNAUTHORIZED,
        )


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def profile(request):
    """
    GET:   Return authenticated user's profile.
    PATCH: Update profile fields (username, bio, avatar_url).
           Role is NOT editable through this endpoint.
    """
    if request.method == "GET":
        return Response(UserSerializer(request.user).data)

    serializer = ProfileUpdateSerializer(
        request.user,
        data=request.data,
        partial=True,
        context={"request": request},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(UserSerializer(request.user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    Blacklist the refresh token to log out.

    Expects: {"refresh": "..."}
    """
    refresh_token = request.data.get("refresh")
    if refresh_token:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            pass  # Token may already be invalid — that's fine for logout
    return Response({"message": "Logged out successfully."})


def _unique_username(base_username):
    """Generate a unique username, appending a suffix if needed."""
    username = base_username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}_{counter}"
        counter += 1
    return username
