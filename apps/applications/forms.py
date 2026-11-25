"""Forms for student applications and ATS status transitions."""

from __future__ import annotations

from django import forms

from apps.accounts.forms import TailwindFormMixin


class ApplicationSubmitForm(TailwindFormMixin, forms.Form):
    """Optional tailored cover note submitted with an application."""

    cover_note = forms.CharField(
        required=False,
        label="Tailored Cover Note (Optional)",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Share why your projects and skills fit this role...",
            }
        ),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.apply_tailwind_styles()
