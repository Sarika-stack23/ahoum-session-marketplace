"""
Permission classes for role-based access control.

These are backend-enforced — the frontend may hide UI elements
for UX, but the backend is the authority on what actions are allowed.
"""
from rest_framework.permissions import BasePermission


class IsCreator(BasePermission):
    """
    Only allows access to users with the CREATOR role.
    Returns 403 Forbidden for authenticated non-creators.
    """

    message = "Only creators can perform this action."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "CREATOR"
        )
