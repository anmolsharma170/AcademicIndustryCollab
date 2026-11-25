"""URL routes for notifications bell popover and inbox."""

from django.urls import path

from .views import (
    NotificationDropdownView,
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
)

app_name = "notifications"

urlpatterns = [
    path("", NotificationListView.as_view(), name="inbox"),
    path("dropdown/", NotificationDropdownView.as_view(), name="dropdown"),
    path("<int:pk>/read/", NotificationMarkReadView.as_view(), name="mark_read"),
    path("read-all/", NotificationMarkAllReadView.as_view(), name="mark_all_read"),
]
