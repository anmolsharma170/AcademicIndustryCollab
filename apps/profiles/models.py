"""Domain models for Student profiles, Project showcases, Companies, and Partnerships."""

from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.accounts.models import University
from apps.core.validators import validate_pdf_file


class AcademicStanding(models.TextChoices):
    GOOD_STANDING = "GOOD_STANDING", "Good Standing"
    DEANS_LIST = "DEANS_LIST", "Dean's List"
    HONORS = "HONORS", "Honors"
    PROBATION = "PROBATION", "Academic Probation"


class CompanySize(models.TextChoices):
    STARTUP = "1-50", "1–50 employees"
    GROWTH = "51-200", "51–200 employees"
    MID_MARKET = "201-1000", "201–1,000 employees"
    ENTERPRISE = "1000+", "1,000+ employees"


class PartnershipStatus(models.TextChoices):
    PENDING = "PENDING", "Pending Approval"
    APPROVED = "APPROVED", "Approved Partner"
    SUSPENDED = "SUSPENDED", "Suspended"


class StudentProfile(models.Model):
    """Comprehensive academic and career portfolio for a Student user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )
    university = models.ForeignKey(
        University,
        on_delete=models.PROTECT,
        related_name="students",
    )
    roll_number = models.CharField(max_length=50, blank=True)
    department = models.CharField(max_length=120)
    graduation_year = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(2020), MaxValueValidator(2035)],
    )
    cgpa = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Cumulative GPA on a 0.00–10.00 scale.",
    )
    academic_standing = models.CharField(
        max_length=20,
        choices=AcademicStanding.choices,
        default=AcademicStanding.GOOD_STANDING,
    )
    bio = models.TextField(blank=True)
    resume = models.FileField(
        upload_to="resumes/%Y/%m/",
        blank=True,
        validators=[validate_pdf_file],
    )
    github_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    portfolio_url = models.URLField(blank=True)
    is_verified_by_university = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_student_profiles",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    profile_completion_pct = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["university", "graduation_year", "is_verified_by_university"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(cgpa__gte=0) & Q(cgpa__lte=10),
                name="student_cgpa_between_0_and_10",
            ),
        ]
        ordering = ["-cgpa", "user__full_name"]

    def __str__(self) -> str:
        return f"{self.user.full_name} ({self.university.code} '{str(self.graduation_year)[-2:]})"


class ProjectShowcase(models.Model):
    """Portfolio project entry attached to a student profile."""

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    title = models.CharField(max_length=160)
    summary = models.TextField()
    tech_stack = models.CharField(
        max_length=250,
        help_text="Comma-separated technologies, e.g., Python, Django, PostgreSQL",
    )
    repo_url = models.URLField(blank=True)
    live_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["student", "-created_at"]),
        ]
        ordering = ["-created_at"]

    def tech_list(self) -> list[str]:
        return [item.strip() for item in self.tech_stack.split(",") if item.strip()]

    def __str__(self) -> str:
        return f"{self.title} — {self.student.user.full_name}"


class CompanyProfile(models.Model):
    """Organization profile for an Industry Partner user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="company_profile",
    )
    company_name = models.CharField(max_length=180)
    industry = models.CharField(max_length=120)
    company_size = models.CharField(
        max_length=20,
        choices=CompanySize.choices,
        default=CompanySize.GROWTH,
    )
    headquarters = models.CharField(max_length=150)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["company_name"]),
            models.Index(fields=["is_verified", "industry"]),
        ]
        ordering = ["company_name"]

    def __str__(self) -> str:
        return self.company_name


class UniversityCompanyPartnership(models.Model):
    """Campus partnership approval linking a University and a Company."""

    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name="partnerships",
    )
    company = models.ForeignKey(
        CompanyProfile,
        on_delete=models.CASCADE,
        related_name="partnerships",
    )
    status = models.CharField(
        max_length=20,
        choices=PartnershipStatus.choices,
        default=PartnershipStatus.PENDING,
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_partnerships",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["university", "company"],
                name="unique_university_company_partnership",
            ),
        ]
        indexes = [
            models.Index(fields=["university", "status"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.company.company_name} ↔ {self.university.code} ({self.status})"
