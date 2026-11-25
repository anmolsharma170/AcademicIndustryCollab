"""Phase 5 tests: Role-specific dashboards and campus analytics selectors."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import University, UniversityAdminProfile, User, UserRole
from apps.applications.models import Application, ApplicationStatus
from apps.dashboards.selectors.analytics import (
    get_company_dashboard_data,
    get_student_dashboard_data,
    get_university_dashboard_data,
)
from apps.opportunities.models import (
    ApprovalStatus,
    CompensationUnit,
    Opportunity,
    OpportunityStatus,
    OpportunityType,
)
from apps.profiles.models import CompanyProfile, StudentProfile


@pytest.mark.django_db
def test_dashboards_render_and_compute_analytics(client):
    uni = University.objects.create(name="Apex University", code="APEX", city="Bengaluru")
    admin_user = User.objects.create_user(
        email="admin@apex.edu", password="Password123!", full_name="Admin", role=UserRole.UNIVERSITY_ADMIN, onboarding_completed=True
    )
    UniversityAdminProfile.objects.create(user=admin_user, university=uni)

    company_user = User.objects.create_user(
        email="hr@novadata.io", password="Password123!", full_name="HR", role=UserRole.COMPANY, onboarding_completed=True
    )
    company = CompanyProfile.objects.create(
        user=company_user, company_name="NovaData", industry="Data", headquarters="BLR"
    )

    student_user = User.objects.create_user(
        email="meera@apex.edu", password="Password123!", full_name="Meera K", role=UserRole.STUDENT, onboarding_completed=True
    )
    student = StudentProfile.objects.create(
        user=student_user, university=uni, department="CSE", graduation_year=2026, cgpa=Decimal("9.10")
    )

    opp = Opportunity.objects.create(
        company=company,
        target_university=uni,
        title="Data Engineering Intern",
        opportunity_type=OpportunityType.INTERNSHIP,
        stipend_min=40000,
        stipend_max=50000,
        compensation_unit=CompensationUnit.MONTHLY,
        deadline=timezone.localdate() + timedelta(days=10),
        description="ETL pipelines",
        status=OpportunityStatus.ACTIVE,
        approval_status=ApprovalStatus.APPROVED,
    )
    Application.objects.create(
        student=student,
        opportunity=opp,
        status=ApplicationStatus.ACCEPTED,
        match_score_snapshot=92,
    )

    uni_data = get_university_dashboard_data(uni)
    assert uni_data["placement_rate"] == 100.0
    assert uni_data["avg_monthly_stipend"] == 50000

    comp_data = get_company_dashboard_data(company)
    assert comp_data["total_applicants"] == 1
    assert comp_data["offers_extended"] == 1

    stu_data = get_student_dashboard_data(student)
    assert stu_data["offers_count"] == 1

    for user, url_name in (
        (student_user, "dashboards:student"),
        (company_user, "dashboards:company"),
        (admin_user, "dashboards:university"),
    ):
        client.force_login(user)
        assert client.get(reverse(url_name)).status_code == 200
