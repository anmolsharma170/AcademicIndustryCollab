"""Atomic ATS submission and state-machine transition services."""

from __future__ import annotations

from typing import Iterable

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.applications.models import Application, ApplicationStatus, ApplicationStatusLog
from apps.applications.signals import application_status_changed, application_submitted
from apps.opportunities.models import ApprovalStatus, Opportunity, OpportunityStatus
from apps.opportunities.services.recommendation import default_recommendation_engine
from apps.profiles.models import StudentProfile

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    ApplicationStatus.APPLIED: {
        ApplicationStatus.UNDER_REVIEW,
        ApplicationStatus.SHORTLISTED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.UNDER_REVIEW: {
        ApplicationStatus.SHORTLISTED,
        ApplicationStatus.INTERVIEW_SCHEDULED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.SHORTLISTED: {
        ApplicationStatus.INTERVIEW_SCHEDULED,
        ApplicationStatus.OFFERED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.INTERVIEW_SCHEDULED: {
        ApplicationStatus.OFFERED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.OFFERED: {
        ApplicationStatus.ACCEPTED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.ACCEPTED: set(),
    ApplicationStatus.REJECTED: set(),
}

COMPANY_ALLOWED_TARGETS: set[str] = {
    ApplicationStatus.UNDER_REVIEW,
    ApplicationStatus.SHORTLISTED,
    ApplicationStatus.INTERVIEW_SCHEDULED,
    ApplicationStatus.OFFERED,
    ApplicationStatus.REJECTED,
}

STUDENT_ALLOWED_TARGETS: set[str] = {
    ApplicationStatus.ACCEPTED,
    ApplicationStatus.REJECTED,
}


def get_valid_next_statuses(application: Application, actor: User) -> list[tuple[str, str]]:
    """Return (value, label) pairs of transitions permitted for the given actor."""
    allowed = ALLOWED_TRANSITIONS.get(application.status, set())
    if actor.is_company and application.opportunity.company_id == getattr(actor.company_profile, "id", None):
        permitted = allowed & COMPANY_ALLOWED_TARGETS
    elif actor.is_student and application.student_id == getattr(actor.student_profile, "id", None):
        permitted = allowed & STUDENT_ALLOWED_TARGETS
    else:
        permitted = set()

    label_map = dict(ApplicationStatus.choices)
    return [(status, label_map[status]) for status in ApplicationStatus.values if status in permitted]


@transaction.atomic
def submit_application(
    *,
    student: StudentProfile,
    opportunity: Opportunity,
    cover_note: str = "",
) -> Application:
    """Validate eligibility, prevent duplicates, snapshot match score, and submit application."""
    if opportunity.status != OpportunityStatus.ACTIVE or opportunity.approval_status != ApprovalStatus.APPROVED:
        raise ValidationError("This opportunity is not currently accepting applications.")
    if opportunity.deadline < timezone.localdate():
        raise ValidationError("The application deadline for this opportunity has passed.")
    if opportunity.target_university_id and opportunity.target_university_id != student.university_id:
        raise PermissionDenied("This opportunity is restricted to another university.")

    if Application.objects.filter(student=student, opportunity=opportunity).exists():
        raise ValidationError("You have already applied to this opportunity.")

    match = default_recommendation_engine.score_pair(student, opportunity)

    try:
        application = Application.objects.create(
            student=student,
            opportunity=opportunity,
            status=ApplicationStatus.APPLIED,
            cover_note=cover_note.strip(),
            match_score_snapshot=match.score,
            match_breakdown_snapshot=match.to_snapshot_dict(),
        )
    except IntegrityError as exc:
        raise ValidationError("You have already applied to this opportunity.") from exc

    ApplicationStatusLog.objects.create(
        application=application,
        from_status="",
        to_status=ApplicationStatus.APPLIED,
        changed_by=student.user,
        note="Application submitted",
    )

    transaction.on_commit(
        lambda: application_submitted.send(
            sender=Application,
            application=application,
            actor=student.user,
        )
    )
    return application


@transaction.atomic
def transition_application_status(
    *,
    application_id: int,
    to_status: str,
    actor: User,
    note: str = "",
) -> Application:
    """Execute an atomic, audited ATS state transition with strict object-level RBAC."""
    application = (
        Application.objects.select_for_update()
        .select_related("student__user", "opportunity__company__user")
        .get(pk=application_id)
    )

    # Object-level authorization check
    if actor.is_company:
        company_profile = getattr(actor, "company_profile", None)
        if not company_profile or application.opportunity.company_id != company_profile.id:
            raise PermissionDenied("You can only manage applicants for your own postings.")
        if to_status not in COMPANY_ALLOWED_TARGETS:
            raise PermissionDenied("Companies cannot directly set that application status.")
    elif actor.is_student:
        student_profile = getattr(actor, "student_profile", None)
        if not student_profile or application.student_id != student_profile.id:
            raise PermissionDenied("You can only respond to your own offers.")
        if application.status != ApplicationStatus.OFFERED or to_status not in STUDENT_ALLOWED_TARGETS:
            raise PermissionDenied("Students can only accept or decline an active offer.")
    else:
        raise PermissionDenied("Your role cannot transition application statuses.")

    allowed_targets = ALLOWED_TRANSITIONS.get(application.status, set())
    if to_status not in allowed_targets:
        raise ValidationError(
            f"Invalid transition from {application.get_status_display()} to {to_status}."
        )

    from_status = application.status
    application.status = to_status
    application.save(update_fields=["status", "updated_at"])

    ApplicationStatusLog.objects.create(
        application=application,
        from_status=from_status,
        to_status=to_status,
        changed_by=actor,
        note=note.strip(),
    )

    transaction.on_commit(
        lambda: application_status_changed.send(
            sender=Application,
            application=application,
            from_status=from_status,
            to_status=to_status,
            actor=actor,
            note=note.strip(),
        )
    )
    return application


@transaction.atomic
def bulk_transition_applications(
    *,
    opportunity: Opportunity,
    application_ids: Iterable[int],
    to_status: str,
    actor: User,
    note: str = "",
) -> int:
    """Bulk-advance selected applications for a single company-owned opportunity."""
    updated = 0
    apps = Application.objects.filter(opportunity=opportunity, pk__in=list(application_ids))
    for app in apps:
        if to_status in ALLOWED_TRANSITIONS.get(app.status, set()):
            transition_application_status(
                application_id=app.pk,
                to_status=to_status,
                actor=actor,
                note=note,
            )
            updated += 1
    return updated
