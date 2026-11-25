"""Phase 3 tests: Recommendation scoring engine math, eligibility cutoffs, and opportunity RBAC."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import University, User, UserRole
from apps.opportunities.models import (
    ApprovalStatus,
    Opportunity,
    OpportunitySkill,
    OpportunityStatus,
    OpportunityType,
    RequirementType,
)
from apps.opportunities.services.recommendation import RecommendationEngine
from apps.profiles.models import CompanyProfile, StudentProfile
from apps.skills.models import ProficiencyLevel, Skill, SkillCategory, StudentSkill


@pytest.mark.django_db
def test_recommendation_engine_scoring_and_gap_breakdown():
    uni = University.objects.create(name="NIT Demo", code="NITD", city="Surathkal")
    company_user = User.objects.create_user(
        email="hr@cloud.io", password="Password123!", full_name="HR", role=UserRole.COMPANY, onboarding_completed=True
    )
    company = CompanyProfile.objects.create(
        user=company_user, company_name="CloudScale", industry="SaaS", headquarters="Bengaluru"
    )
    student_user = User.objects.create_user(
        email="dev@nitd.edu", password="Password123!", full_name="Dev Student", role=UserRole.STUDENT, onboarding_completed=True
    )
    student = StudentProfile.objects.create(
        user=student_user, university=uni, department="CSE", graduation_year=2026, cgpa=Decimal("8.50")
    )

    py = Skill.objects.create(name="Python", category=SkillCategory.BACKEND)
    dj = Skill.objects.create(name="Django", category=SkillCategory.BACKEND)
    docker = Skill.objects.create(name="Docker", category=SkillCategory.CLOUD_DEVOPS)
    redis = Skill.objects.create(name="Redis", category=SkillCategory.BACKEND)

    StudentSkill.objects.create(student=student, skill=py, proficiency_level=ProficiencyLevel.ADVANCED, is_verified=True)
    StudentSkill.objects.create(student=student, skill=dj, proficiency_level=ProficiencyLevel.BEGINNER)

    opp = Opportunity.objects.create(
        company=company,
        title="Backend Intern",
        opportunity_type=OpportunityType.INTERNSHIP,
        min_cgpa=Decimal("7.50"),
        eligible_grad_years=[2026],
        deadline=timezone.localdate() + timedelta(days=15),
        description="Build APIs",
        status=OpportunityStatus.ACTIVE,
        approval_status=ApprovalStatus.APPROVED,
    )
    OpportunitySkill.objects.create(opportunity=opp, skill=py, requirement_type=RequirementType.REQUIRED, min_proficiency=ProficiencyLevel.INTERMEDIATE)
    OpportunitySkill.objects.create(opportunity=opp, skill=dj, requirement_type=RequirementType.REQUIRED, min_proficiency=ProficiencyLevel.INTERMEDIATE)
    OpportunitySkill.objects.create(opportunity=opp, skill=docker, requirement_type=RequirementType.REQUIRED, min_proficiency=ProficiencyLevel.INTERMEDIATE)
    OpportunitySkill.objects.create(opportunity=opp, skill=redis, requirement_type=RequirementType.BONUS, min_proficiency=ProficiencyLevel.BEGINNER)

    engine = RecommendationEngine()
    result = engine.score_pair(student, opp)

    assert result.is_eligible is True
    assert result.matched_required == ["Python"]
    assert len(result.partial_required) == 1 and "Django" in result.partial_required[0]
    assert result.missing_required == ["Docker"]
    assert "Matches 2/3 required skills" in result.summary_text
    assert "Missing: Docker" in result.summary_text
    assert 40 <= result.score <= 80

    # Test ineligible CGPA
    student.cgpa = Decimal("6.50")
    student.save()
    ineligible_res = engine.score_pair(student, opp)
    assert ineligible_res.is_eligible is False
    assert "Eligibility gap" in ineligible_res.summary_text


@pytest.mark.django_db
def test_company_cannot_edit_other_company_opportunity(client):
    c1_user = User.objects.create_user(email="c1@co.com", password="Password123!", full_name="C1", role=UserRole.COMPANY, onboarding_completed=True)
    c2_user = User.objects.create_user(email="c2@co.com", password="Password123!", full_name="C2", role=UserRole.COMPANY, onboarding_completed=True)
    c1 = CompanyProfile.objects.create(user=c1_user, company_name="One Co", industry="AI", headquarters="HYD")
    CompanyProfile.objects.create(user=c2_user, company_name="Two Co", industry="AI", headquarters="HYD")

    opp = Opportunity.objects.create(
        company=c1,
        title="ML Intern",
        deadline=timezone.localdate() + timedelta(days=10),
        description="ML work",
    )

    client.force_login(c2_user)
    assert client.get(reverse("opportunities:edit", args=[opp.pk])).status_code == 403
    assert client.post(reverse("opportunities:status_update", args=[opp.pk]), {"status": OpportunityStatus.PAUSED}).status_code == 403
