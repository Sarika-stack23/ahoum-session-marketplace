"""
Session model — the core marketplace entity.

Each session belongs to exactly one Creator.
Ownership is enforced server-side in views/permissions.
"""
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator


class Session(models.Model):
    """A bookable session created by a Creator."""

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_sessions",
        db_index=True,
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    start_time = models.DateTimeField(db_index=True)
    capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Maximum number of bookings allowed.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sessions"
        ordering = ["start_time"]
        indexes = [
            models.Index(fields=["start_time", "created_at"], name="idx_session_start_created"),
        ]

    def __str__(self):
        return f"{self.title} by {self.creator.username}"
