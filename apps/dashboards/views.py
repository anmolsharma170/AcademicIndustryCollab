"""Dashboard routing and role-specific workspace views."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.accounts.models import UserRole
from apps.core.mixins import OnboardingRequiredMixin, RoleRequiredMixin
from apps.profiles.models import CompanyProfile, StudentProfile
from .selectors.analytics import (
    get_company_dashboard_data,
    get_student_dashboard_data,
    get_university_dashboard_data,
)


class LandingView(View):
    """Public landing page for the Academia-Industry Collaboration Portal."""

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect("dashboards:home")
        return render(request, "dashboards/landing.html")


class DashboardHomeView(OnboardingRequiredMixin, View):
    """Redirect authenticated users to their role-specific dashboard."""

    def get(self, request: HttpRequest) -> HttpResponse:
        role = request.user.role
        if role == UserRole.COMPANY:
            return redirect("dashboards:company")
        if role == UserRole.UNIVERSITY_ADMIN:
            return redirect("dashboards:university")
        return redirect("dashboards:student")


class StudentDashboardView(RoleRequiredMixin, View):
    """Student workspace overview with profile meter, top matches, and skill gaps."""

    allowed_roles = (UserRole.STUDENT,)

    def get(self, request: HttpRequest) -> HttpResponse:
        student = get_object_or_404(
            StudentProfile.objects.select_related("university", "user").prefetch_related(
                "student_skills__skill", "projects"
            ),
            user=request.user,
        )
        context = get_student_dashboard_data(student)
        return render(request, "dashboards/student_dashboard.html", context)


class CompanyDashboardView(RoleRequiredMixin, View):
    """Company talent acquisition workspace with pipeline funnel and matched candidates."""

    allowed_roles = (UserRole.COMPANY,)

    def get(self, request: HttpRequest) -> HttpResponse:
        company = get_object_or_404(CompanyProfile, user=request.user)
        context = get_company_dashboard_data(company)
        return render(request, "dashboards/company_dashboard.html", context)


class UniversityDashboardView(RoleRequiredMixin, View):
    """University placement cell & partnership analytics overview."""

    allowed_roles = (UserRole.UNIVERSITY_ADMIN,)

    def get(self, request: HttpRequest) -> HttpResponse:
        university = request.user.university_admin_profile.university
        context = get_university_dashboard_data(university)
        return render(request, "dashboards/university_dashboard.html", context)
