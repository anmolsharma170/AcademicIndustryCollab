"""Domain models for authentication, RBAC roles, and university tenants."""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserRole(models.TextChoices):
    """Supported roles in the Academia-Industry Collaboration Portal."""

    STUDENT = "STUDENT", "Student"
    COMPANY = "COMPANY", "Company"
    UNIVERSITY_ADMIN = "UNIVERSITY_ADMIN", "University Admin"


class UserManager(BaseUserManager):
    """Custom manager using email as the unique authentication identifier."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields) -> "User":
        if not email:
            raise ValueError("An email address must be provided.")
        normalized_email = self.normalize_email(email).lower()
        user = self.model(email=normalized_email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields) -> "User":
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", UserRole.UNIVERSITY_ADMIN)
        extra_fields.setdefault("onboarding_completed", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom user model supporting Student, Company, and University Admin roles."""

    username = None
    email = models.EmailField("email address", unique=True)
    full_name = models.CharField(max_length=150)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.STUDENT,
        db_index=True,
    )
    onboarding_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    objects = UserManager()

    class Meta:
        indexes = [
            models.Index(fields=["role", "is_active"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.email})"

    @property
    def is_student(self) -> bool:
        return self.role == UserRole.STUDENT

    @property
    def is_company(self) -> bool:
        return self.role == UserRole.COMPANY

    @property
    def is_university_admin(self) -> bool:
        return self.role == UserRole.UNIVERSITY_ADMIN


class University(models.Model):
    """Partner academic institution registered on the portal."""

    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=20, unique=True, help_text="Short institutional code, e.g., NITK")
    domain = models.CharField(max_length=120, blank=True, help_text="Official email domain, e.g., nit.edu")
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default="India")
    website = models.URLField(blank=True)
    is_verified = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Universities"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["is_verified", "name"]),
        ]

    def save(self, *args, **kwargs) -> None:
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class UniversityAdminProfile(models.Model):
    """Profile linking a university administrator to their institution."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="university_admin_profile",
    )
    university = models.ForeignKey(
        University,
        on_delete=models.PROTECT,
        related_name="admins",
    )
    designation = models.CharField(max_length=120, default="Placement Officer")
    department = models.CharField(max_length=120, default="Career & Placement Cell")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["university"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.full_name} — {self.university.code}"
