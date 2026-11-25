"""Authentication and role-specific onboarding views."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View

from apps.profiles.forms import CompanyOnboardingForm, StudentOnboardingForm
from apps.profiles.services.completion import compute_student_profile_strength
from .forms import EmailAuthenticationForm, RegisterForm, UniversityAdminOnboardingForm
from .models import UserRole


class PortalLoginView(LoginView):
    """Sign in view redirecting authenticated users to onboarding or dashboard."""

    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self) -> str:
        user = self.request.user
        if not user.onboarding_completed and not user.is_superuser:
            return str(reverse_lazy("accounts:onboarding"))
        return str(reverse_lazy("dashboards:home"))


class PortalRegisterView(View):
    """Multi-role user registration view."""

    template_name = "accounts/register.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect("dashboards:home")
        return render(request, self.template_name, {"form": RegisterForm()})

    def post(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect("dashboards:home")
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created! Complete your profile setup to continue.")
            return redirect("accounts:onboarding")
        return render(request, self.template_name, {"form": form})


class PortalLogoutView(LogoutView):
    """Logout view accepting POST requests."""

    next_page = reverse_lazy("dashboards:landing")


class OnboardingView(LoginRequiredMixin, View):
    """Role-specific onboarding router and form handler."""

    template_name = "accounts/onboarding.html"

    def _get_form_for_role(self, role: str, data=None, files=None):
        if role == UserRole.UNIVERSITY_ADMIN:
            return UniversityAdminOnboardingForm(data)
        if role == UserRole.COMPANY:
            return CompanyOnboardingForm(data, files)
        return StudentOnboardingForm(data, files)

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.onboarding_completed:
            return redirect("dashboards:home")
        form = self._get_form_for_role(request.user.role)
        return render(request, self.template_name, {"role": request.user.role, "form": form})

    def post(self, request: HttpRequest) -> HttpResponse:
        user = request.user
        if user.onboarding_completed:
            return redirect("dashboards:home")

        form = self._get_form_for_role(user.role, data=request.POST, files=request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"role": user.role, "form": form})

        if user.role == UserRole.UNIVERSITY_ADMIN:
            form.save(user)
            messages.success(request, "University admin workspace is ready.")
        elif user.role == UserRole.COMPANY:
            company = form.save(commit=False)
            company.user = user
            company.save()
            user.onboarding_completed = True
            user.save(update_fields=["onboarding_completed"])
            messages.success(request, "Company profile created! You can now post opportunities.")
        else:
            student = form.save(commit=False)
            student.user = user
            student.save()
            compute_student_profile_strength(student, persist=True)
            user.onboarding_completed = True
            user.save(update_fields=["onboarding_completed"])
            messages.success(request, "Student profile created! Add skills and resume to boost your Match Score.")

        return redirect("dashboards:home")
