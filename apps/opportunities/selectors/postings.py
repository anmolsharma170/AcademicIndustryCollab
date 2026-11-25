"""Optimized read queries for opportunity feeds, company listings, and university approval queues."""

from __future__ import annotations

from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from apps.accounts.models import University
from apps.opportunities.models import ApprovalStatus, Opportunity, OpportunityStatus
from apps.profiles.models import CompanyProfile, StudentProfile


def base_opportunity_queryset() -> QuerySet[Opportunity]:
    """Return base queryset preloading company, university, and skill taxonomy."""
    return Opportunity.objects.select_related("company", "target_university", "approved_by").prefetch_related(
        "opportunity_skills__skill"
    )


def get_student_opportunity_feed(
    *,
    student: StudentProfile,
    query: str = "",
    opportunity_type: str = "",
    work_mode: str = "",
) -> QuerySet[Opportunity]:
    """Return active, university-approved opportunities visible to a given student."""
    today = timezone.localdate()
    qs = (
        base_opportunity_queryset()
        .filter(
            status=OpportunityStatus.ACTIVE,
            approval_status=ApprovalStatus.APPROVED,
            deadline__gte=today,
        )
        .filter(Q(target_university__isnull=True) | Q(target_university=student.university))
    )

    if query:
        q = query.strip()
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(company__company_name__icontains=q)
            | Q(location__icontains=q)
            | Q(opportunity_skills__skill__name__icontains=q)
        ).distinct()

    if opportunity_type:
        qs = qs.filter(opportunity_type=opportunity_type)

    if work_mode:
        qs = qs.filter(work_mode=work_mode)

    return qs.order_by("-is_featured", "deadline", "-created_at")


def get_company_opportunities(company: CompanyProfile) -> QuerySet[Opportunity]:
    """Return all postings owned by a company with applicant count annotation."""
    return (
        base_opportunity_queryset()
        .filter(company=company)
        .annotate(applicant_count=Count("applications", distinct=True))
        .order_by("-created_at")
    )


def get_university_opportunity_queue(university: University) -> QuerySet[Opportunity]:
    """Return postings targeted at this university or open across campuses for review."""
    return (
        base_opportunity_queryset()
        .filter(Q(target_university=university) | Q(target_university__isnull=True))
        .annotate(applicant_count=Count("applications", distinct=True))
        .order_by("approval_status", "-is_featured", "-created_at")
    )
