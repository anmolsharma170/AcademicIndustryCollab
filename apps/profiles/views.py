"""Views for student portfolios, company profiles, verification, and partnerships."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.accounts.models import University, UserRole
from apps.core.mixins import OnboardingRequiredMixin, RoleRequiredMixin, is_htmx
from .forms import CompanyOnboardingForm, ProjectShowcaseForm, StudentProfileForm
from .models import (
    CompanyProfile,
    PartnershipStatus,
    ProjectShowcase,
    StudentProfile,
    UniversityCompanyPartnership,
)
from .services.completion import (
    compute_student_profile_strength,
    update_partnership_status,
    verify_student_by_university,
)


class StudentProfileEditView(RoleRequiredMixin, View):
    """Allow a student to update their portfolio, upload resume, and add projects."""

    allowed_roles = (UserRole.STUDENT,)
    template_name = "profiles/student_edit.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        student = get_object_or_404(
            StudentProfile.objects.select_related("university").prefetch_related("projects", "student_skills__skill"),
            user=request.user,
        )
        strength = compute_student_profile_strength(student)
        return render(
            request,
            self.template_name,
            {
                "student": student,
                "form": StudentProfileForm(instance=student),
                "project_form": ProjectShowcaseForm(),
                "strength": strength,
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        student = get_object_or_404(StudentProfile, user=request.user)
        form = StudentProfileForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            student = form.save()
            compute_student_profile_strength(student, persist=True)
            messages.success(request, "Your student profile has been updated.")
            return redirect("profiles:student_edit")

        strength = compute_student_profile_strength(student, persist=False)
        return render(
            request,
            self.template_name,
            {
                "student": student,
                "form": form,
                "project_form": ProjectShowcaseForm(),
                "strength": strength,
            },
        )


class ProjectShowcaseCreateView(RoleRequiredMixin, View):
    """Add a project showcase entry to the logged-in student's portfolio."""

    allowed_roles = (UserRole.STUDENT,)

    def post(self, request: HttpRequest) -> HttpResponse:
        student = get_object_or_404(StudentProfile, user=request.user)
        form = ProjectShowcaseForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.student = student
            project.save()
            compute_student_profile_strength(student, persist=True)
            messages.success(request, "Project added to your showcase.")
        else:
            messages.error(request, "Could not add project. Please check the fields.")
        return redirect("profiles:student_edit")


class ProjectShowcaseDeleteView(RoleRequiredMixin, View):
    """Remove a project showcase owned by the logged-in student."""

    allowed_roles = (UserRole.STUDENT,)

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        project = get_object_or_404(ProjectShowcase, pk=pk, student__user=request.user)
        student = project.student
        project.delete()
        compute_student_profile_strength(student, persist=True)
        messages.success(request, "Project removed.")
        return redirect("profiles:student_edit")


class StudentProfileDetailView(OnboardingRequiredMixin, View):
    """Read-only portfolio view accessible to the student, companies, and their university admin."""

    template_name = "profiles/student_detail.html"

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        student = get_object_or_404(
            StudentProfile.objects.select_related("user", "university").prefetch_related(
                "projects",
                "student_skills__skill",
            ),
            pk=pk,
        )
        if request.user.is_student and student.user_id != request.user.id:
            raise PermissionDenied("You cannot view another student's private profile.")
        if request.user.is_university_admin:
            admin_profile = getattr(request.user, "university_admin_profile", None)
            if not admin_profile or admin_profile.university_id != student.university_id:
                raise PermissionDenied("You can only view students from your university.")

        strength = compute_student_profile_strength(student, persist=False)
        return render(
            request,
            self.template_name,
            {"student": student, "strength": strength},
        )


class CompanyProfileEditView(RoleRequiredMixin, View):
    """Allow an industry partner to edit their company profile."""

    allowed_roles = (UserRole.COMPANY,)
    template_name = "profiles/company_edit.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        company = get_object_or_404(CompanyProfile, user=request.user)
        partnerships = company.partnerships.select_related("university").order_by("university__name")
        available_universities = University.objects.exclude(
            id__in=partnerships.values_list("university_id", flat=True)
        )
        return render(
            request,
            self.template_name,
            {
                "company": company,
                "form": CompanyOnboardingForm(instance=company),
                "partnerships": partnerships,
                "available_universities": available_universities,
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        company = get_object_or_404(CompanyProfile, user=request.user)
        form = CompanyOnboardingForm(request.POST, instance=company)
        if form.is_valid():
            form.save()
            messages.success(request, "Company profile saved.")
            return redirect("profiles:company_edit")
        partnerships = company.partnerships.select_related("university")
        return render(
            request,
            self.template_name,
            {"company": company, "form": form, "partnerships": partnerships},
        )


class CompanyProfileDetailView(OnboardingRequiredMixin, View):
    """Public/authenticated profile page for a Company."""

    template_name = "profiles/company_detail.html"

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        company = get_object_or_404(CompanyProfile.objects.select_related("user"), pk=pk)
        return render(request, self.template_name, {"company": company})


class CompanyPartnershipRequestView(RoleRequiredMixin, View):
    """Allow a company to request campus partnership with a university."""

    allowed_roles = (UserRole.COMPANY,)

    def post(self, request: HttpRequest) -> HttpResponse:
        company = get_object_or_404(CompanyProfile, user=request.user)
        university = get_object_or_404(University, pk=request.POST.get("university_id"))
        _, created = UniversityCompanyPartnership.objects.get_or_create(
            university=university,
            company=company,
            defaults={"status": PartnershipStatus.PENDING},
        )
        if created:
            messages.success(request, f"Partnership request sent to {university.name}.")
        else:
            messages.info(request, f"A partnership record with {university.name} already exists.")
        return redirect("profiles:company_edit")


class UniversityVerificationQueueView(RoleRequiredMixin, View):
    """University Admin queue to verify campus students and approve company partnerships."""

    allowed_roles = (UserRole.UNIVERSITY_ADMIN,)
    template_name = "profiles/university_verifications.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        admin_profile = request.user.university_admin_profile
        students = (
            StudentProfile.objects.filter(university=admin_profile.university)
            .select_related("user", "university")
            .prefetch_related("student_skills__skill")
            .order_by("is_verified_by_university", "-cgpa")
        )
        partnerships = (
            UniversityCompanyPartnership.objects.filter(university=admin_profile.university)
            .select_related("company", "reviewed_by")
            .order_by("status", "-created_at")
        )
        return render(
            request,
            self.template_name,
            {
                "university": admin_profile.university,
                "students": students,
                "partnerships": partnerships,
            },
        )


class ToggleStudentVerificationView(RoleRequiredMixin, View):
    """HTMX/POST action for University Admin to verify or unverify a student from their campus."""

    allowed_roles = (UserRole.UNIVERSITY_ADMIN,)

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        admin_profile = request.user.university_admin_profile
        student = get_object_or_404(StudentProfile, pk=pk)
        if student.university_id != admin_profile.university_id:
            raise PermissionDenied("You can only verify students from your own university.")
        verify_student_by_university(
            student=student,
            admin_user=request.user,
            verified=not student.is_verified_by_university,
        )
        if is_htmx(request):
            return render(request, "profiles/partials/student_verify_row.html", {"student": student})
        messages.success(request, f"Updated verification for {student.user.full_name}.")
        return redirect("profiles:university_verifications")


class UpdatePartnershipStatusView(RoleRequiredMixin, View):
    """HTMX/POST action for University Admin to approve or suspend a company partnership."""

    allowed_roles = (UserRole.UNIVERSITY_ADMIN,)

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        admin_profile = request.user.university_admin_profile
        partnership = get_object_or_404(
            UniversityCompanyPartnership.objects.select_related("company", "university"),
            pk=pk,
        )
        if partnership.university_id != admin_profile.university_id:
            raise PermissionDenied("You can only manage partnerships for your own university.")
        new_status = request.POST.get("status", PartnershipStatus.APPROVED)
        update_partnership_status(
            partnership=partnership,
            new_status=new_status,
            admin_user=request.user,
        )
        if is_htmx(request):
            return render(request, "profiles/partials/partnership_row.html", {"partnership": partnership})
        messages.success(request, f"{partnership.company.company_name} marked as {partnership.get_status_display()}.")
        return redirect("profiles:university_verifications")
