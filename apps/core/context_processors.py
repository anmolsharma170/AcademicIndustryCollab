"""Global template context processors for navigation and notifications."""

from __future__ import annotations

from django.http import HttpRequest


def portal_context(request: HttpRequest) -> dict:
    """Provide unread notification count and role helpers across all templates."""
    unread_count = 0
    if request.user.is_authenticated:
        # Populated dynamically once apps.notifications is installed
        notifications_rel = getattr(request.user, "notifications", None)
        if notifications_rel is not None:
            unread_count = notifications_rel.filter(is_read=False).count()

    return {
        "unread_notifications_count": unread_count,
        "current_url_name": (
            request.resolver_match.view_name if getattr(request, "resolver_match", None) else ""
        ),
    }
