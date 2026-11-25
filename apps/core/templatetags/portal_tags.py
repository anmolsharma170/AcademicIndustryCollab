"""Reusable template filters and tags for badges, formatting, and navigation."""

from __future__ import annotations

from django import template

register = template.Library()

STATUS_BADGE_MAP: dict[str, str] = {
    "APPLIED": "bg-slate-100 text-slate-700 border-slate-200",
    "UNDER_REVIEW": "bg-amber-50 text-amber-700 border-amber-200",
    "SHORTLISTED": "bg-sky-50 text-sky-700 border-sky-200",
    "INTERVIEW_SCHEDULED": "bg-indigo-50 text-indigo-700 border-indigo-200",
    "OFFERED": "bg-emerald-50 text-emerald-700 border-emerald-200",
    "ACCEPTED": "bg-emerald-100 text-emerald-800 border-emerald-300",
    "REJECTED": "bg-rose-50 text-rose-700 border-rose-200",
    "ACTIVE": "bg-emerald-50 text-emerald-700 border-emerald-200",
    "PAUSED": "bg-amber-50 text-amber-700 border-amber-200",
    "CLOSED": "bg-slate-100 text-slate-600 border-slate-200",
    "DRAFT": "bg-slate-100 text-slate-600 border-slate-200",
    "PENDING": "bg-amber-50 text-amber-700 border-amber-200",
    "APPROVED": "bg-emerald-50 text-emerald-700 border-emerald-200",
    "SUSPENDED": "bg-rose-50 text-rose-700 border-rose-200",
}


@register.filter
def status_badge_class(status_value: str) -> str:
    """Return Tailwind badge classes for a given status string."""
    return STATUS_BADGE_MAP.get(
        str(status_value).upper(),
        "bg-slate-100 text-slate-700 border-slate-200",
    )


@register.filter
def match_badge_class(score: int | float) -> str:
    """Return Tailwind semantic color classes for a 0-100 match score."""
    numeric = int(score or 0)
    if numeric >= 75:
        return "bg-emerald-50 text-emerald-700 border-emerald-200"
    if numeric >= 50:
        return "bg-indigo-50 text-indigo-700 border-indigo-200"
    return "bg-amber-50 text-amber-700 border-amber-200"


@register.filter
def role_label(role: str) -> str:
    """Return a clean human-readable label for a UserRole value."""
    mapping = {
        "STUDENT": "Student",
        "COMPANY": "Industry Partner",
        "UNIVERSITY_ADMIN": "University Admin",
    }
    return mapping.get(str(role), str(role).replace("_", " ").title())


@register.simple_tag(takes_context=True)
def nav_active(context: dict, *prefixes: str) -> str:
    """Return active nav classes when current URL path matches any prefix."""
    request = context.get("request")
    if not request:
        return ""
    path = request.path
    for prefix in prefixes:
        if prefix == "/" and path == "/":
            return "bg-indigo-50 text-indigo-700 font-medium"
        if prefix != "/" and path.startswith(prefix):
            return "bg-indigo-50 text-indigo-700 font-medium"
    return "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
