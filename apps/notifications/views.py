"""Views for HTMX notification bell popover and inbox management."""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.core.mixins import is_htmx
from .models import Notification


class NotificationDropdownView(LoginRequiredMixin, View):
    """HTMX fragment rendering latest notifications inside the topbar bell popover."""

    def get(self, request: HttpRequest) -> HttpResponse:
        notifications = request.user.notifications.all()[:8]
        return render(
            request,
            "notifications/partials/dropdown_items.html",
            {"notifications": notifications},
        )


class NotificationListView(LoginRequiredMixin, View):
    """Full notification inbox page."""

    def get(self, request: HttpRequest) -> HttpResponse:
        notifications = request.user.notifications.all()[:50]
        return render(
            request,
            "notifications/inbox.html",
            {"notifications": notifications},
        )


class NotificationMarkReadView(LoginRequiredMixin, View):
    """Mark a single notification as read."""

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])
        if is_htmx(request):
            return render(
                request,
                "notifications/partials/notification_item.html",
                {"n": notification},
            )
        return redirect(notification.target_url or "notifications:inbox")


class NotificationMarkAllReadView(LoginRequiredMixin, View):
    """Mark all unread notifications as read for the logged-in user."""

    def post(self, request: HttpRequest) -> HttpResponse:
        request.user.notifications.filter(is_read=False).update(is_read=True)
        if is_htmx(request):
            notifications = request.user.notifications.all()[:8]
            return render(
                request,
                "notifications/partials/dropdown_items.html",
                {"notifications": notifications},
            )
        return redirect("notifications:inbox")
