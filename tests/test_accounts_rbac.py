"""Phase 1 tests: Authentication, Onboarding, and RBAC permission boundaries."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.accounts.models import University, User, UserRole
from apps.core.validators import validate_pdf_file
from apps.profiles.models import StudentProfile


@pytest.mark.django_db
def test_register_and_university_admin_onboarding(client):
    register_url = reverse("accounts:register")
    resp = client.post(
        register_url,
        {
            "full_name": "Dr. Priya Nair",
            "email": "priya@nitc.edu",
            "role": UserRole.UNIVERSITY_ADMIN,
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        },
    )
    assert resp.status_code == 302
    assert resp.url == reverse("accounts:onboarding")

    user = User.objects.get(email="priya@nitc.edu")
    assert user.role == UserRole.UNIVERSITY_ADMIN
    assert not user.onboarding_completed

    # Incomplete onboarding redirects away from dashboard
    dash_resp = client.get(reverse("dashboards:university"))
    assert dash_resp.status_code == 302
    assert dash_resp.url == reverse("accounts:onboarding")

    # Complete onboarding by registering a new university
    onboard_resp = client.post(
        reverse("accounts:onboarding"),
        {
            "new_university_name": "National Institute of Technology Calicut",
            "new_university_code": "nitc",
            "new_university_city": "Kozhikode",
            "designation": "Dean of Placements",
            "department": "Training & Placement Cell",
        },
    )
    assert onboard_resp.status_code == 302
    user.refresh_from_db()
    assert user.onboarding_completed is True
    assert University.objects.filter(code="NITC").exists()


@pytest.mark.django_db
def test_cross_role_rbac_denied(client):
    uni = University.objects.create(name="RBAC Uni", code="RBACU", city="Mumbai")
    student = User.objects.create_user(
        email="student1@uni.edu",
        password="Password123!",
        full_name="Student One",
        role=UserRole.STUDENT,
        onboarding_completed=True,
    )
    StudentProfile.objects.create(
        user=student,
        university=uni,
        department="CSE",
        graduation_year=2026,
        cgpa="8.40",
    )
    client.force_login(student)

    assert client.get(reverse("dashboards:student")).status_code == 200
    assert client.get(reverse("dashboards:company")).status_code == 403
    assert client.get(reverse("dashboards:university")).status_code == 403


def test_pdf_validator_rejects_spoofed_and_oversized_files():
    valid_pdf = SimpleUploadedFile("resume.pdf", b"%PDF-1.4\n%fake body", content_type="application/pdf")
    validate_pdf_file(valid_pdf)

    wrong_ext = SimpleUploadedFile("resume.exe", b"%PDF-1.4", content_type="application/pdf")
    with pytest.raises(ValidationError):
        validate_pdf_file(wrong_ext)

    spoofed_pdf = SimpleUploadedFile("resume.pdf", b"MZ\x90\x00not-a-pdf", content_type="application/pdf")
    with pytest.raises(ValidationError):
        validate_pdf_file(spoofed_pdf)
