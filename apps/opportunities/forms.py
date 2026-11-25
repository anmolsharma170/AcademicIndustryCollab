"""Forms for creating and editing industry opportunities."""

from __future__ import annotations

from django import forms
from django.utils import timezone

from apps.accounts.forms import TailwindFormMixin
from apps.skills.models import ProficiencyLevel, Skill
from .models import Opportunity


class OpportunityForm(TailwindFormMixin, forms.ModelForm):
    """Form for companies to create or update an opportunity with skill requirements."""

    required_skills = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select core skills required for this role.",
    )
    bonus_skills = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Optional skills that boost candidate Match Scores.",
    )
    min_required_proficiency = forms.TypedChoiceField(
        choices=ProficiencyLevel.choices,
        coerce=int,
        initial=ProficiencyLevel.INTERMEDIATE,
        label="Minimum Required Proficiency",
    )
    eligible_grad_years_input = forms.CharField(
        required=False,
        label="Eligible Graduation Years",
        help_text="Comma-separated years (e.g., 2026, 2027). Leave blank for all years.",
        widget=forms.TextInput(attrs={"placeholder": "2026, 2027"}),
    )

    class Meta:
        model = Opportunity
        fields = (
            "title",
            "opportunity_type",
            "work_mode",
            "location",
            "target_university",
            "stipend_min",
            "stipend_max",
            "compensation_unit",
            "min_cgpa",
            "deadline",
            "description",
            "eligibility_notes",
        )
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Backend Engineering Intern"}),
            "location": forms.TextInput(attrs={"placeholder": "Bengaluru, India / Remote"}),
            "deadline": forms.DateInput(attrs={"type": "date"}),
            "min_cgpa": forms.NumberInput(attrs={"step": "0.1", "min": "0", "max": "10"}),
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "Describe role scope, team, and mentorship..."}),
            "eligibility_notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Open to B.Tech / M.Tech CS, IT, and ECE students..."}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.apply_tailwind_styles()
        if self.instance and self.instance.pk:
            self.fields["required_skills"].initial = [
                os.skill_id for os in self.instance.required_skills
            ]
            self.fields["bonus_skills"].initial = [
                os.skill_id for os in self.instance.bonus_skills
            ]
            if self.instance.required_skills:
                self.fields["min_required_proficiency"].initial = (
                    self.instance.required_skills[0].min_proficiency
                )
            if self.instance.eligible_grad_years:
                self.fields["eligible_grad_years_input"].initial = ", ".join(
                    str(y) for y in self.instance.eligible_grad_years
                )

    def clean_deadline(self):
        deadline = self.cleaned_data["deadline"]
        if deadline < timezone.localdate():
            raise forms.ValidationError("Application deadline cannot be in the past.")
        return deadline

    def clean_eligible_grad_years_input(self) -> list[int]:
        raw = (self.cleaned_data.get("eligible_grad_years_input") or "").strip()
        if not raw:
            return []
        years: list[int] = []
        for token in raw.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                year = int(token)
            except ValueError as exc:
                raise forms.ValidationError(f"Invalid graduation year: '{token}'.") from exc
            if year < 2020 or year > 2035:
                raise forms.ValidationError(f"Graduation year out of range: {year}.")
            if year not in years:
                years.append(year)
        return years

    def clean(self) -> dict:
        cleaned = super().clean()
        low = cleaned.get("stipend_min") or 0
        high = cleaned.get("stipend_max") or 0
        if low > high:
            raise forms.ValidationError("Minimum compensation cannot exceed maximum compensation.")
        return cleaned
