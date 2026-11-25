"""Domain signals decoupling ATS events from notification delivery."""

from django.dispatch import Signal

application_submitted = Signal()
application_status_changed = Signal()
