"""Phase 4 tests: Application duplicate prevention, ATS state machine, RBAC, and notifications."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import University, User, UserRole
from apps.applications.models import Application, ApplicationStatus, ApplicationStatusLog
from apps.applications.services.transitions import submit_application, transition_application_status
from apps.notifications.models import Notification
from apps.opportunities.models import ApprovalStatus, Opportunity, OpportunityStatus
from apps.profiles.models import CompanyProfile, StudentProfile


@pytest.mark.django_db(transaction=True)
def test_ats_lifecycle_audit_log_and_notifications(client):
    uni = University.objects.create(name="NIT Surathkal", code="NITK", city="Surathkal")
    company_user = User.objects.create_user(
        email="talent@fintech.io", password="Password123!", full_name="Talent Lead", role=UserRole.COMPANY, onboarding_completed=True
    )
    company = CompanyProfile.objects.create(
        user=company_user, company_name="FinPulse", industry="FinTech", headquarters="Mumbai"
    )
    other_company_user = User.objects.create_user(
        email="other@co.io", password="Password123!", full_name="Other Co", role=UserRole.COMPANY, onboarding_completed=True
    )
    CompanyProfile.objects.create(
        user=other_company_user, company_name="OtherCo", industry="SaaS", headquarters="Delhi"
    )

    student_user = User.objects.create_user(
        email="arjun@nitk.edu", password="Password123!", full_name="Arjun Verma", role=UserRole.STUDENT, onboarding_completed=True
    )
    student = StudentProfile.objects.create(
        user=student_user, university=uni, department="IT", graduation_year=2026, cgpa=Decimal("8.80")
    )

    opp = Opportunity.objects.create(
        company=company,
        title="Platform Engineering Intern",
        deadline=timezone.localdate() + timedelta(days=20),
        description="Build reliable services.",
        status=OpportunityStatus.ACTIVE,
        approval_status=ApprovalStatus.APPROVED,
    )

    # Submit application
    app = submit_application(student=student, opportunity=opp, cover_note="Excited to contribute!")
    assert app.status == ApplicationStatus.APPLIED
    assert ApplicationStatusLog.objects.filter(application=app, to_status=ApplicationStatus.APPLIED).exists()
    assert Notification.objects.filter(recipient=company_user).count() == 1

    # Prevent duplicate application
    with pytest.raises(ValidationError):
        submit_application(student=student, opportunity=opp)

    # Company cannot directly set ACCEPTED (PermissionDenied) or skip APPLIED -> OFFERED (ValidationError)
    with pytest.raises(PermissionDenied):
        transition_application_status(application_id=app.pk, to_status=ApplicationStatus.ACCEPTED, actor=company_user)
    with pytest.raises(ValidationError):
        transition_application_status(application_id=app.pk, to_status=ApplicationStatus.OFFERED, actor=company_user)

    # Cross-company authorization denial
    with pytest.raises(PermissionDenied):
        transition_application_status(application_id=app.pk, to_status=ApplicationStatus.SHORTLISTED, actor=other_company_user)

    # Valid pipeline progression: APPLIED -> SHORTLISTED -> OFFERED -> ACCEPTED
    app = transition_application_status(application_id=app.pk, to_status=ApplicationStatus.SHORTLISTED, actor=company_user)
    app = transition_application_status(application_id=app.pk, to_status=ApplicationStatus.OFFERED, actor=company_user)
    assert Notification.objects.filter(recipient=student_user).count() == 2

    # Student accepts offer
    app = transition_application_status(application_id=app.pk, to_status=ApplicationStatus.ACCEPTED, actor=student_user)
    assert app.status == ApplicationStatus.ACCEPTED
    assert app.status_logs.count() == 4
    assert Notification.objects.filter(recipient=company_user).count() == 2

    # Terminal state cannot transition further
    with pytest.raises(ValidationError):
        transition_application_status(application_id=app.pk, to_status=ApplicationStatus.REJECTED, actor=company_user)
