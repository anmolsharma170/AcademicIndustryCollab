"""Domain models for Applications and immutable ATS status audit logs."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.opportunities.models import Opportunity
from apps.profiles.models import StudentProfile


class ApplicationStatus(models.TextChoices):
    APPLIED = "APPLIED", "Applied"
    UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
    SHORTLISTED = "SHORTLISTED", "Shortlisted"
    INTERVIEW_SCHEDULED = "INTERVIEW_SCHEDULED", "Interview Scheduled"
    OFFERED = "OFFERED", "Offered"
    ACCEPTED = "ACCEPTED", "Accepted"
    REJECTED = "REJECTED", "Rejected"


class Application(models.Model):
    """Student application to an industry opportunity with match snapshot."""

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    status = models.CharField(
        max_length=25,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.APPLIED,
        db_index=True,
    )
    cover_note = models.TextField(blank=True)
    match_score_snapshot = models.PositiveSmallIntegerField(default=0)
    match_breakdown_snapshot = models.JSONField(default=dict, blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "opportunity"],
                name="unique_student_opportunity_application",
            ),
        ]
        indexes = [
            models.Index(fields=["opportunity", "status", "-match_score_snapshot"]),
            models.Index(fields=["student", "status", "-updated_at"]),
        ]
        ordering = ["-match_score_snapshot", "-applied_at"]

    def __str__(self) -> str:
        return f"{self.student.user.full_name} → {self.opportunity.title} ({self.status})"


class ApplicationStatusLog(models.Model):
    """Audit trail entry recording every ATS pipeline status transition."""

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="status_logs",
    )
    from_status = models.CharField(max_length=25, blank=True)
    to_status = models.CharField(max_length=25, choices=ApplicationStatus.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="application_status_changes",
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["application", "created_at"]),
        ]
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.application_id}: {self.from_status or 'NEW'} → {self.to_status}"
