"""Core shared form styling mixin and account/onboarding forms."""

from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import University, UniversityAdminProfile, User, UserRole

INPUT_CSS = (
    "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 "
    "placeholder-slate-400 shadow-xs transition focus:border-indigo-500 focus:outline-none "
    "focus:ring-2 focus:ring-indigo-500/20"
)
CHECKBOX_CSS = (
    "h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
)


class TailwindFormMixin:
    """Apply consistent Linear/Stripe-inspired Tailwind classes to form widgets."""

    def apply_tailwind_styles(self) -> None:
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect, forms.CheckboxSelectMultiple)):
                if isinstance(widget, forms.CheckboxInput):
                    widget.attrs.setdefault("class", CHECKBOX_CSS)
            else:
                existing = widget.attrs.get("class", "")
                if INPUT_CSS not in existing:
                    widget.attrs["class"] = f"{INPUT_CSS} {existing}".strip()


class EmailAuthenticationForm(TailwindFormMixin, AuthenticationForm):
    """Authentication form with styled email and password inputs."""

    username = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={"placeholder": "you@university.edu", "autofocus": True}),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"placeholder": "Enter your password"}),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.apply_tailwind_styles()


class RegisterForm(TailwindFormMixin, UserCreationForm):
    """Multi-role registration form for Students, Companies, and University Admins."""

    role = forms.ChoiceField(
        choices=UserRole.choices,
        widget=forms.RadioSelect,
        initial=UserRole.STUDENT,
        label="I am joining as a",
    )

    class Meta:
        model = User
        fields = ("full_name", "email", "role")
        widgets = {
            "full_name": forms.TextInput(attrs={"placeholder": "Alex Morgan"}),
            "email": forms.EmailInput(attrs={"placeholder": "alex@example.edu"}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.apply_tailwind_styles()

    def clean_email(self) -> str:
        return self.cleaned_data["email"].strip().lower()


class UniversityAdminOnboardingForm(TailwindFormMixin, forms.Form):
    """Onboarding form linking a University Admin to an existing or new University."""

    university = forms.ModelChoiceField(
        queryset=University.objects.all(),
        required=False,
        empty_label="Select your university (or register a new one below)",
    )
    new_university_name = forms.CharField(
        max_length=200,
        required=False,
        label="Or Register New University Name",
        widget=forms.TextInput(attrs={"placeholder": "e.g., National Institute of Technology"}),
    )
    new_university_code = forms.CharField(
        max_length=20,
        required=False,
        label="University Code",
        widget=forms.TextInput(attrs={"placeholder": "e.g., NITC"}),
    )
    new_university_city = forms.CharField(
        max_length=100,
        required=False,
        label="City",
        widget=forms.TextInput(attrs={"placeholder": "e.g., Bengaluru"}),
    )
    designation = forms.CharField(
        max_length=120,
        initial="Placement Officer",
    )
    department = forms.CharField(
        max_length=120,
        initial="Career & Placement Cell",
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.apply_tailwind_styles()

    def clean(self) -> dict:
        cleaned = super().clean()
        selected_uni = cleaned.get("university")
        new_name = (cleaned.get("new_university_name") or "").strip()
        new_code = (cleaned.get("new_university_code") or "").strip().upper()
        new_city = (cleaned.get("new_university_city") or "").strip()

        if not selected_uni and not new_name:
            raise forms.ValidationError(
                "Please select an existing university or enter details to register a new one."
            )
        if not selected_uni and new_name:
            if not new_code or not new_city:
                raise forms.ValidationError(
                    "University code and city are required when registering a new university."
                )
            if University.objects.filter(code=new_code).exists():
                raise forms.ValidationError(f"A university with code '{new_code}' already exists.")
        return cleaned

    def save(self, user: User) -> UniversityAdminProfile:
        selected_uni = self.cleaned_data.get("university")
        if not selected_uni:
            selected_uni = University.objects.create(
                name=self.cleaned_data["new_university_name"].strip(),
                code=self.cleaned_data["new_university_code"].strip().upper(),
                city=self.cleaned_data["new_university_city"].strip(),
                is_verified=True,
            )
        profile, _ = UniversityAdminProfile.objects.update_or_create(
            user=user,
            defaults={
                "university": selected_uni,
                "designation": self.cleaned_data["designation"].strip(),
                "department": self.cleaned_data["department"].strip(),
            },
        )
        user.onboarding_completed = True
        user.save(update_fields=["onboarding_completed"])
        return profile
