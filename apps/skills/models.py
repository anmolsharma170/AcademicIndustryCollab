"""Standardized skill taxonomy and student proficiency models."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.profiles.models import StudentProfile


class SkillCategory(models.TextChoices):
    FRONTEND = "FRONTEND", "Frontend"
    BACKEND = "BACKEND", "Backend"
    AI_ML = "AI_ML", "AI / ML"
    CORE_ENG = "CORE_ENG", "Core Engineering"
    DATA = "DATA", "Data & Analytics"
    CLOUD_DEVOPS = "CLOUD_DEVOPS", "Cloud & DevOps"
    MANAGEMENT = "MANAGEMENT", "Management"
    DESIGN = "DESIGN", "Product & UI Design"


class ProficiencyLevel(models.IntegerChoices):
    BEGINNER = 1, "Beginner"
    INTERMEDIATE = 2, "Intermediate"
    ADVANCED = 3, "Advanced"


class Skill(models.Model):
    """Canonical skill entry shared across student profiles and job postings."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    category = models.CharField(
        max_length=20,
        choices=SkillCategory.choices,
        default=SkillCategory.BACKEND,
        db_index=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=["category", "name"]),
        ]
        ordering = ["category", "name"]

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.get_category_display()})"


class StudentSkill(models.Model):
    """Mapping between a student and a skill with proficiency and campus verification."""

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="student_skills",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name="student_entries",
    )
    proficiency_level = models.PositiveSmallIntegerField(
        choices=ProficiencyLevel.choices,
        default=ProficiencyLevel.INTERMEDIATE,
    )
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_student_skills",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "skill"],
                name="unique_student_skill",
            ),
        ]
        indexes = [
            models.Index(fields=["student", "is_verified"]),
        ]
        ordering = ["-is_verified", "-proficiency_level", "skill__name"]

    def __str__(self) -> str:
        return f"{self.student.user.full_name} — {self.skill.name} ({self.get_proficiency_level_display()})"
