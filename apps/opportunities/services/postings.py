"""Transactional services for Opportunity CRUD, lifecycle status, and campus approvals."""

from __future__ import annotations

from typing import Iterable

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.opportunities.models import (
    ApprovalStatus,
    Opportunity,
    OpportunitySkill,
    OpportunityStatus,
    RequirementType,
)
from apps.profiles.models import PartnershipStatus, UniversityCompanyPartnership
from apps.skills.models import ProficiencyLevel, Skill


@transaction.atomic
def save_opportunity_with_skills(
    *,
    opportunity: Opportunity,
    required_skills: Iterable[Skill],
    bonus_skills: Iterable[Skill],
    min_required_proficiency: int = ProficiencyLevel.INTERMEDIATE,
) -> Opportunity:
    """Persist an Opportunity and synchronize its required/bonus skill requirements."""
    # Auto-approve if target university already has an approved partnership with this company
    if opportunity.pk is None and opportunity.target_university_id:
        is_partner = UniversityCompanyPartnership.objects.filter(
            university_id=opportunity.target_university_id,
            company=opportunity.company,
            status=PartnershipStatus.APPROVED,
        ).exists()
        if is_partner:
            opportunity.approval_status = ApprovalStatus.APPROVED

    opportunity.save()

    OpportunitySkill.objects.filter(opportunity=opportunity).delete()
    req_ids = {s.pk for s in required_skills}
    entries: list[OpportunitySkill] = [
        OpportunitySkill(
            opportunity=opportunity,
            skill=skill,
            requirement_type=RequirementType.REQUIRED,
            min_proficiency=min_required_proficiency,
        )
        for skill in required_skills
    ]
    for skill in bonus_skills:
        if skill.pk not in req_ids:
            entries.append(
                OpportunitySkill(
                    opportunity=opportunity,
                    skill=skill,
                    requirement_type=RequirementType.BONUS,
                    min_proficiency=ProficiencyLevel.BEGINNER,
                )
            )
    if entries:
        OpportunitySkill.objects.bulk_create(entries)
    return opportunity


@transaction.atomic
def transition_opportunity_status(opportunity: Opportunity, new_status: str) -> Opportunity:
    """Pause, activate, or close a company's opportunity posting."""
    if new_status not in OpportunityStatus.values:
        raise ValueError(f"Invalid opportunity status: {new_status}")
    opportunity.status = new_status
    opportunity.save(update_fields=["status", "updated_at"])
    return opportunity


@transaction.atomic
def review_opportunity_by_university(
    *,
    opportunity: Opportunity,
    approval_status: str,
    is_featured: bool,
    admin_user: User,
) -> Opportunity:
    """Approve, reject, or feature an opportunity for campus visibility."""
    if approval_status not in ApprovalStatus.values:
        raise ValueError(f"Invalid approval status: {approval_status}")
    opportunity.approval_status = approval_status
    opportunity.is_featured = is_featured and approval_status == ApprovalStatus.APPROVED
    opportunity.approved_by = admin_user
    opportunity.approved_at = timezone.now()
    opportunity.save(
        update_fields=[
            "approval_status",
            "is_featured",
            "approved_by",
            "approved_at",
            "updated_at",
        ]
    )
    return opportunity
