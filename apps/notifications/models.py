"""Domain model for in-app notifications."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class NotificationCategory(models.TextChoices):
    APPLICATION = "APPLICATION", "New Application"
    STATUS_UPDATE = "STATUS_UPDATE", "ATS Status Update"
    VERIFICATION = "VERIFICATION", "Verification"
    PARTNERSHIP = "PARTNERSHIP", "Partnership"
    SYSTEM = "SYSTEM", "System"


class Notification(models.Model):
    """In-app notification delivered to a user's bell popover and inbox."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_notifications",
    )
    category = models.CharField(
        max_length=20,
        choices=NotificationCategory.choices,
        default=NotificationCategory.SYSTEM,
    )
    title = models.CharField(max_length=160)
    message = models.TextField()
    target_url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"[{self.category}] {self.recipient.email}: {self.title}"
