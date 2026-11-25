"""Forms for Student, Project, Company, and Partnership management."""

from __future__ import annotations

from django import forms

from apps.accounts.forms import TailwindFormMixin
from .models import CompanyProfile, ProjectShowcase, StudentProfile


class StudentOnboardingForm(TailwindFormMixin, forms.ModelForm):
    """Initial academic profile setup during Student onboarding."""

    class Meta:
        model = StudentProfile
        fields = ("university", "roll_number", "department", "graduation_year", "cgpa", "academic_standing")
        widgets = {
            "roll_number": forms.TextInput(attrs={"placeholder": "e.g., 21CS104"}),
            "department": forms.TextInput(attrs={"placeholder": "e.g., Computer Science & Engineering"}),
            "graduation_year": forms.NumberInput(attrs={"min": 2020, "max": 2035, "placeholder": "2027"}),
            "cgpa": forms.NumberInput(attrs={"step": "0.01", "min": "0", "max": "10", "placeholder": "8.65"}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.apply_tailwind_styles()


class StudentProfileForm(TailwindFormMixin, forms.ModelForm):
    """Full editable portfolio form for Students."""

    class Meta:
        model = StudentProfile
        fields = (
            "university",
            "roll_number",
            "department",
            "graduation_year",
            "cgpa",
            "academic_standing",
            "bio",
            "resume",
            "github_url",
            "linkedin_url",
            "portfolio_url",
        )
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 3, "placeholder": "Summarize your technical interests, coursework, and career goals..."}),
            "github_url": forms.URLInput(attrs={"placeholder": "https://github.com/username"}),
            "linkedin_url": forms.URLInput(attrs={"placeholder": "https://linkedin.com/in/username"}),
            "portfolio_url": forms.URLInput(attrs={"placeholder": "https://yourportfolio.dev"}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.apply_tailwind_styles()


class ProjectShowcaseForm(TailwindFormMixin, forms.ModelForm):
    """Form to add a project showcase to a student's portfolio."""

    class Meta:
        model = ProjectShowcase
        fields = ("title", "summary", "tech_stack", "repo_url", "live_url")
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Distributed Telemetry Pipeline"}),
            "summary": forms.Textarea(attrs={"rows": 3, "placeholder": "Describe problem solved, architecture, and measurable impact..."}),
            "tech_stack": forms.TextInput(attrs={"placeholder": "Python, Django, PostgreSQL, Redis"}),
            "repo_url": forms.URLInput(attrs={"placeholder": "https://github.com/username/project"}),
            "live_url": forms.URLInput(attrs={"placeholder": "https://demo.example.com"}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.apply_tailwind_styles()


class CompanyOnboardingForm(TailwindFormMixin, forms.ModelForm):
    """Company profile form used during onboarding and profile editing."""

    class Meta:
        model = CompanyProfile
        fields = ("company_name", "industry", "company_size", "headquarters", "website", "description")
        widgets = {
            "company_name": forms.TextInput(attrs={"placeholder": "Apex Cloud Systems"}),
            "industry": forms.TextInput(attrs={"placeholder": "Cloud Infrastructure / SaaS"}),
            "headquarters": forms.TextInput(attrs={"placeholder": "Bengaluru, India"}),
            "website": forms.URLInput(attrs={"placeholder": "https://apexcloud.example.com"}),
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Tell universities and students about your engineering culture and mission..."}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.apply_tailwind_styles()
