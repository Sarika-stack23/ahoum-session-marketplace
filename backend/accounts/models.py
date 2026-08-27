"""
User model with role-based access control.

Roles:
  USER    — can browse sessions and book them
  CREATOR — can also create/manage sessions

Role assignment is controlled, not self-service.
See DECISIONS.md for rationale.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user with role field for RBAC."""

    class Role(models.TextChoices):
        USER = "USER", "User"
        CREATOR = "CREATOR", "Creator"

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.USER,
        db_index=True,
        help_text="USER can browse/book. CREATOR can also manage sessions.",
    )
    github_id = models.IntegerField(unique=True, null=True, blank=True)
    avatar_url = models.URLField(max_length=500, blank=True, default="")
    bio = models.TextField(max_length=500, blank=True, default="")

    class Meta:
        db_table = "users"

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def is_creator(self):
        return self.role == self.Role.CREATOR
