"""Phase 2 tests: Student/Company profiles, completion score, skill verification, and cross-campus isolation."""

from decimal import Decimal
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.models import University, UniversityAdminProfile, User, UserRole
from apps.profiles.models import CompanyProfile, ProjectShowcase, StudentProfile
from apps.profiles.services.completion import compute_student_profile_strength
from apps.skills.models import ProficiencyLevel, Skill, SkillCategory, StudentSkill


@pytest.mark.django_db
def test_student_onboarding_and_profile_completion(client):
    uni = University.objects.create(name="Metro Tech", code="MTU", city="Pune")
    student_user = User.objects.create_user(
        email="riya@mtu.edu",
        password="Password123!",
        full_name="Riya Sharma",
        role=UserRole.STUDENT,
        onboarding_completed=False,
    )
    client.force_login(student_user)

    resp = client.post(
        reverse("accounts:onboarding"),
        {
            "university": uni.pk,
            "roll_number": "21CS09",
            "department": "Computer Science",
            "graduation_year": 2026,
            "cgpa": "8.90",
            "academic_standing": "DEANS_LIST",
        },
    )
    assert resp.status_code == 302
    student_user.refresh_from_db()
    assert student_user.onboarding_completed is True

    profile = student_user.student_profile
    report = compute_student_profile_strength(profile)
    assert report.percentage == 20  # academic details only

    # Add bio, links, resume, project, and 3 skills -> 100%
    profile.bio = "Backend engineer focused on distributed Python services."
    profile.github_url = "https://github.com/riyasharma"
    profile.resume = SimpleUploadedFile("riya.pdf", b"%PDF-1.4\nresume", content_type="application/pdf")
    profile.save()
    ProjectShowcase.objects.create(
        student=profile,
        title="Query Engine",
        summary="Built a lightweight SQL planner.",
        tech_stack="Python, SQLite",
    )
    for name in ("Python", "Django", "PostgreSQL"):
        skill = Skill.objects.create(name=name, category=SkillCategory.BACKEND)
        StudentSkill.objects.create(student=profile, skill=skill, proficiency_level=ProficiencyLevel.ADVANCED)

    full_report = compute_student_profile_strength(profile)
    assert full_report.percentage == 100
    assert full_report.missing_items == []


@pytest.mark.django_db
def test_university_admin_cannot_verify_other_campus_student_or_skill(client):
    uni_a = University.objects.create(name="Uni Alpha", code="UNIA", city="Chennai")
    uni_b = University.objects.create(name="Uni Beta", code="UNIB", city="Delhi")

    admin_a = User.objects.create_user(
        email="admin@unia.edu",
        password="Password123!",
        full_name="Admin A",
        role=UserRole.UNIVERSITY_ADMIN,
        onboarding_completed=True,
    )
    UniversityAdminProfile.objects.create(user=admin_a, university=uni_a)

    student_b_user = User.objects.create_user(
        email="bob@unib.edu",
        password="Password123!",
        full_name="Bob B",
        role=UserRole.STUDENT,
        onboarding_completed=True,
    )
    student_b = StudentProfile.objects.create(
        user=student_b_user,
        university=uni_b,
        department="ECE",
        graduation_year=2026,
        cgpa=Decimal("8.20"),
    )
    skill = Skill.objects.create(name="Docker", category=SkillCategory.CLOUD_DEVOPS)
    student_skill_b = StudentSkill.objects.create(student=student_b, skill=skill)

    client.force_login(admin_a)
    resp_student = client.post(reverse("profiles:toggle_student_verify", args=[student_b.pk]))
    assert resp_student.status_code == 403

    resp_skill = client.post(reverse("skills:toggle_verify", args=[student_skill_b.pk]))
    assert resp_skill.status_code == 403
