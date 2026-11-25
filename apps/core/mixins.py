"""Reusable RBAC mixins, decorators, and HTMX response helpers."""

from __future__ import annotations

from functools import wraps
from typing import Callable, Iterable

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy


class OnboardingRequiredMixin(LoginRequiredMixin):
    """Ensure authenticated users have completed role-specific onboarding."""

    onboarding_url = reverse_lazy("accounts:onboarding")

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.onboarding_completed and not request.user.is_superuser:
            return redirect(self.onboarding_url)
        return super().dispatch(request, *args, **kwargs)


class RoleRequiredMixin(OnboardingRequiredMixin):
    """Restrict class-based views to specific UserRole values."""

    allowed_roles: Iterable[str] = ()

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.onboarding_completed and not request.user.is_superuser:
            return redirect(self.onboarding_url)
        if self.allowed_roles and request.user.role not in self.allowed_roles:
            raise PermissionDenied("You do not have permission to access this resource.")
        return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)


def role_required(*roles: str, require_onboarding: bool = True) -> Callable:
    """Decorator restricting function-based views to specific user roles."""

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def _wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            if not request.user.is_authenticated:
                return redirect("accounts:login")
            if require_onboarding and not request.user.onboarding_completed and not request.user.is_superuser:
                return redirect("accounts:onboarding")
            if roles and request.user.role not in roles:
                raise PermissionDenied("You do not have permission to access this resource.")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def is_htmx(request: HttpRequest) -> bool:
    """Return True if the request originated from HTMX."""
    return request.headers.get("HX-Request", "").lower() == "true"


def render_htmx_or_full(
    request: HttpRequest,
    *,
    partial_template: str,
    full_template: str,
    context: dict,
) -> HttpResponse:
    """Render a partial fragment for HTMX requests or the full page otherwise."""
    template_name = partial_template if is_htmx(request) else full_template
    return render(request, template_name, context)
