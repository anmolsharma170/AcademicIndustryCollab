"""Optimized read queries for ATS timelines and candidate pipelines."""

from __future__ import annotations

from django.db.models import Count, QuerySet

from apps.applications.models import Application, ApplicationStatus
from apps.opportunities.models import Opportunity
from apps.profiles.models import StudentProfile


def get_student_applications(student: StudentProfile) -> QuerySet[Application]:
    """Return a student's applications with opportunity, company, and audit logs preloaded."""
    return (
        Application.objects.filter(student=student)
        .select_related("opportunity", "opportunity__company")
        .prefetch_related("status_logs__changed_by")
        .order_by("-updated_at")
    )


def get_opportunity_pipeline(
    *,
    opportunity: Opportunity,
    status_filter: str = "",
) -> QuerySet[Application]:
    """Return applications for an opportunity sorted by Match Score descending."""
    qs = (
        Application.objects.filter(opportunity=opportunity)
        .select_related("student__user", "student__university")
        .prefetch_related("student__student_skills__skill", "status_logs__changed_by")
    )
    if status_filter:
        qs = qs.filter(status=status_filter)
    return qs.order_by("-match_score_snapshot", "-applied_at")


def get_pipeline_stage_counts(opportunity: Opportunity) -> dict[str, int]:
    """Return applicant counts per ATS stage for an opportunity."""
    rows = (
        Application.objects.filter(opportunity=opportunity)
        .values("status")
        .annotate(total=Count("id"))
    )
    counts = {status: 0 for status in ApplicationStatus.values}
    for row in rows:
        counts[row["status"]] = row["total"]
    return counts
