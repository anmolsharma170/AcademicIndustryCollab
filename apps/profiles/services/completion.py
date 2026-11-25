"""Services for student profile strength calculation and verification workflows."""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.profiles.models import PartnershipStatus, StudentProfile, UniversityCompanyPartnership


@dataclass(frozen=True)
class ProfileStrengthReport:
    """Breakdown of a student's profile completion percentage and next actions."""

    percentage: int
    completed_items: list[str]
    missing_items: list[str]


def compute_student_profile_strength(
    student: StudentProfile,
    *,
    persist: bool = True,
) -> ProfileStrengthReport:
    """Compute weighted profile completion score (0-100) for a student."""
    completed: list[str] = []
    missing: list[str] = []
    score = 0

    checks = [
        (bool(student.department and student.cgpa is not None), 20, "Academic details & CGPA"),
        (bool((student.bio or "").strip()), 15, "Professional bio"),
        (bool(student.resume), 20, "PDF resume uploaded"),
        (bool(student.github_url or student.linkedin_url or student.portfolio_url), 15, "GitHub, LinkedIn, or portfolio link"),
        (student.projects.exists(), 15, "At least 1 project showcase"),
        (student.student_skills.count() >= 3, 15, "At least 3 listed skills"),
    ]

    for passed, weight, label in checks:
        if passed:
            score += weight
            completed.append(label)
        else:
            missing.append(label)

    if persist and student.profile_completion_pct != score:
        student.profile_completion_pct = score
        student.save(update_fields=["profile_completion_pct", "updated_at"])

    return ProfileStrengthReport(
        percentage=score,
        completed_items=completed,
        missing_items=missing,
    )


@transaction.atomic
def verify_student_by_university(
    *,
    student: StudentProfile,
    admin_user: User,
    verified: bool = True,
) -> StudentProfile:
    """Toggle university verification status for a student profile."""
    student.is_verified_by_university = verified
    student.verified_by = admin_user if verified else None
    student.verified_at = timezone.now() if verified else None
    student.save(update_fields=["is_verified_by_university", "verified_by", "verified_at", "updated_at"])
    return student


@transaction.atomic
def update_partnership_status(
    *,
    partnership: UniversityCompanyPartnership,
    new_status: str,
    admin_user: User,
    notes: str = "",
) -> UniversityCompanyPartnership:
    """Approve or suspend a company partnership with a university."""
    if new_status not in PartnershipStatus.values:
        raise ValueError(f"Unsupported partnership status: {new_status}")
    partnership.status = new_status
    partnership.reviewed_by = admin_user
    partnership.reviewed_at = timezone.now()
    if notes:
        partnership.notes = notes
    partnership.save(update_fields=["status", "reviewed_by", "reviewed_at", "notes"])
    if new_status == PartnershipStatus.APPROVED and not partnership.company.is_verified:
        partnership.company.is_verified = True
        partnership.company.save(update_fields=["is_verified", "updated_at"])
    return partnership
