"""Domain models for Industry Opportunities and Skill Requirements."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils.text import slugify

from apps.accounts.models import University
from apps.profiles.models import CompanyProfile
from apps.skills.models import ProficiencyLevel, Skill


class OpportunityType(models.TextChoices):
    INTERNSHIP = "INTERNSHIP", "Internship"
    FULL_TIME = "FULL_TIME", "Full-Time Placement"
    CAPSTONE = "CAPSTONE", "Research Capstone"


class WorkMode(models.TextChoices):
    REMOTE = "REMOTE", "Remote"
    HYBRID = "HYBRID", "Hybrid"
    ONSITE = "ONSITE", "On-Site"


class CompensationUnit(models.TextChoices):
    MONTHLY = "MONTHLY", "Monthly Stipend (₹/mo)"
    ANNUAL = "ANNUAL", "Annual CTC (₹/yr)"


class OpportunityStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    PAUSED = "PAUSED", "Paused"
    CLOSED = "CLOSED", "Closed"


class ApprovalStatus(models.TextChoices):
    PENDING = "PENDING", "Pending University Review"
    APPROVED = "APPROVED", "University Approved"
    REJECTED = "REJECTED", "Rejected"


class RequirementType(models.TextChoices):
    REQUIRED = "REQUIRED", "Required"
    BONUS = "BONUS", "Bonus / Good to Have"


class Opportunity(models.Model):
    """Internship, Full-Time Placement, or Capstone posting created by a Company."""

    company = models.ForeignKey(
        CompanyProfile,
        on_delete=models.CASCADE,
        related_name="opportunities",
    )
    target_university = models.ForeignKey(
        University,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="targeted_opportunities",
        help_text="Leave blank to open to all partner campuses.",
    )
    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=210, blank=True)
    opportunity_type = models.CharField(
        max_length=20,
        choices=OpportunityType.choices,
        default=OpportunityType.INTERNSHIP,
        db_index=True,
    )
    work_mode = models.CharField(
        max_length=15,
        choices=WorkMode.choices,
        default=WorkMode.HYBRID,
    )
    location = models.CharField(max_length=140, default="Bengaluru, India")
    description = models.TextField()
    eligibility_notes = models.TextField(blank=True)
    stipend_min = models.PositiveIntegerField(default=0)
    stipend_max = models.PositiveIntegerField(default=0)
    compensation_unit = models.CharField(
        max_length=15,
        choices=CompensationUnit.choices,
        default=CompensationUnit.MONTHLY,
    )
    min_cgpa = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )
    eligible_grad_years = models.JSONField(
        default=list,
        blank=True,
        help_text="List of eligible graduation years, e.g., [2026, 2027]. Empty = all years.",
    )
    deadline = models.DateField(db_index=True)
    status = models.CharField(
        max_length=15,
        choices=OpportunityStatus.choices,
        default=OpportunityStatus.ACTIVE,
        db_index=True,
    )
    approval_status = models.CharField(
        max_length=15,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        db_index=True,
    )
    is_featured = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_opportunities",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Opportunities"
        indexes = [
            models.Index(fields=["status", "approval_status", "deadline"]),
            models.Index(fields=["company", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(stipend_min__lte=F("stipend_max")),
                name="opportunity_stipend_min_lte_max",
            ),
            models.CheckConstraint(
                condition=Q(min_cgpa__gte=0) & Q(min_cgpa__lte=10),
                name="opportunity_min_cgpa_between_0_and_10",
            ),
        ]
        ordering = ["-is_featured", "-created_at"]

    def clean(self) -> None:
        super().clean()
        if self.stipend_min > self.stipend_max:
            raise ValidationError("Minimum compensation cannot exceed maximum compensation.")

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.title)[:200]
        super().save(*args, **kwargs)

    @property
    def formatted_compensation(self) -> str:
        """Return compact human-readable stipend or CTC string."""
        if self.stipend_max == 0:
            return "Unpaid / Academic Credit"
        if self.compensation_unit == CompensationUnit.ANNUAL:
            low_lpa = self.stipend_min / 100000
            high_lpa = self.stipend_max / 100000
            if self.stipend_min == self.stipend_max:
                return f"₹{high_lpa:.1f} LPA"
            return f"₹{low_lpa:.1f}–{high_lpa:.1f} LPA"
        if self.stipend_min == self.stipend_max:
            return f"₹{self.stipend_max:,}/mo"
        return f"₹{self.stipend_min:,}–₹{self.stipend_max:,}/mo"

    @property
    def required_skills(self) -> list["OpportunitySkill"]:
        return [s for s in self.opportunity_skills.all() if s.requirement_type == RequirementType.REQUIRED]

    @property
    def bonus_skills(self) -> list["OpportunitySkill"]:
        return [s for s in self.opportunity_skills.all() if s.requirement_type == RequirementType.BONUS]

    def __str__(self) -> str:
        return f"{self.title} @ {self.company.company_name}"


class OpportunitySkill(models.Model):
    """Required or bonus standardized skill for an Opportunity."""

    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name="opportunity_skills",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name="opportunity_entries",
    )
    requirement_type = models.CharField(
        max_length=12,
        choices=RequirementType.choices,
        default=RequirementType.REQUIRED,
    )
    min_proficiency = models.PositiveSmallIntegerField(
        choices=ProficiencyLevel.choices,
        default=ProficiencyLevel.INTERMEDIATE,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["opportunity", "skill"],
                name="unique_opportunity_skill",
            ),
        ]
        indexes = [
            models.Index(fields=["opportunity", "requirement_type"]),
        ]
        ordering = ["requirement_type", "skill__name"]

    def __str__(self) -> str:
        return f"{self.opportunity.title} — {self.skill.name} ({self.requirement_type})"
