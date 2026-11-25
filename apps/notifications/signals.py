"""Decoupled signal receivers turning ATS events into in-app notifications."""

from __future__ import annotations

from django.dispatch import receiver
from django.urls import reverse

from apps.applications.models import ApplicationStatus
from apps.applications.signals import application_status_changed, application_submitted
from .models import Notification, NotificationCategory


@receiver(application_submitted)
def notify_company_on_application(sender, application, actor, **kwargs) -> None:
    """Alert the company recruiter when a student applies to their posting."""
    company_user = application.opportunity.company.user
    target_url = reverse("applications:company_pipeline", args=[application.opportunity_id])
    Notification.objects.create(
        recipient=company_user,
        actor=actor,
        category=NotificationCategory.APPLICATION,
        title=f"New Applicant: {application.student.user.full_name}",
        message=(
            f"{application.student.user.full_name} applied to {application.opportunity.title} "
            f"({application.match_score_snapshot}% Match)."
        ),
        target_url=target_url,
    )


@receiver(application_status_changed)
def notify_on_ats_status_change(sender, application, from_status, to_status, actor, note="", **kwargs) -> None:
    """Notify student on company updates, or notify company when student responds to an offer."""
    status_label = dict(ApplicationStatus.choices).get(to_status, to_status)
    if actor.id == application.opportunity.company.user_id:
        Notification.objects.create(
            recipient=application.student.user,
            actor=actor,
            category=NotificationCategory.STATUS_UPDATE,
            title=f"Application Update: {application.opportunity.title}",
            message=f"Your application at {application.opportunity.company.company_name} moved to {status_label}.",
            target_url=reverse("applications:my_list"),
        )
    else:
        Notification.objects.create(
            recipient=application.opportunity.company.user,
            actor=actor,
            category=NotificationCategory.STATUS_UPDATE,
            title=f"Offer Response: {application.student.user.full_name}",
            message=f"{application.student.user.full_name} marked their offer for {application.opportunity.title} as {status_label}.",
            target_url=reverse("applications:company_pipeline", args=[application.opportunity_id]),
        )
