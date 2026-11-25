"""Forms for managing student skills."""

from __future__ import annotations

from django import forms

from apps.accounts.forms import TailwindFormMixin
from .models import ProficiencyLevel, Skill, StudentSkill


class StudentSkillAddForm(TailwindFormMixin, forms.Form):
    """Add or update a standardized skill on a student's portfolio."""

    skill = forms.ModelChoiceField(
        queryset=Skill.objects.all(),
        empty_label="Select a standardized skill...",
    )
    proficiency_level = forms.TypedChoiceField(
        choices=ProficiencyLevel.choices,
        coerce=int,
        initial=ProficiencyLevel.INTERMEDIATE,
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.apply_tailwind_styles()
