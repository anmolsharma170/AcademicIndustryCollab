"""Views for Student application tracking and Company ATS candidate pipelines."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.accounts.models import UserRole
from apps.core.mixins import RoleRequiredMixin, is_htmx
from apps.opportunities.models import Opportunity
from apps.profiles.models import StudentProfile
from .forms import ApplicationSubmitForm
from .models import Application, ApplicationStatus
from .selectors.pipeline import (
    get_opportunity_pipeline,
    get_pipeline_stage_counts,
    get_student_applications,
)
from .services.transitions import (
    bulk_transition_applications,
    get_valid_next_statuses,
    submit_application,
    transition_application_status,
)


class SubmitApplicationView(RoleRequiredMixin, View):
    """One-click or tailored cover-note application endpoint for Students."""

    allowed_roles = (UserRole.STUDENT,)

    def post(self, request: HttpRequest, opportunity_id: int) -> HttpResponse:
        student = get_object_or_404(
            StudentProfile.objects.select_related("university").prefetch_related("student_skills__skill"),
            user=request.user,
        )
        opportunity = get_object_or_404(
            Opportunity.objects.select_related("company").prefetch_related("opportunity_skills__skill"),
            pk=opportunity_id,
        )
        form = ApplicationSubmitForm(request.POST)
        cover_note = form.cleaned_data.get("cover_note", "") if form.is_valid() else ""

        try:
            application = submit_application(
                student=student,
                opportunity=opportunity,
                cover_note=cover_note,
            )
            if is_htmx(request):
                return render(
                    request,
                    "applications/partials/apply_box.html",
                    {"opportunity": opportunity, "existing_application": application},
                )
            messages.success(request, f"Application submitted to {opportunity.company.company_name}!")
        except ValidationError as exc:
            error_msg = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
            if is_htmx(request):
                existing = Application.objects.filter(student=student, opportunity=opportunity).first()
                return render(
                    request,
                    "applications/partials/apply_box.html",
                    {
                        "opportunity": opportunity,
                        "existing_application": existing,
                        "apply_error": error_msg,
                    },
                )
            messages.error(request, error_msg)

        return redirect("opportunities:detail", pk=opportunity.pk)


class StudentApplicationsListView(RoleRequiredMixin, View):
    """Student ATS tracker showing all active applications, stages, and timelines."""

    allowed_roles = (UserRole.STUDENT,)
    template_name = "applications/my_applications.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        student = get_object_or_404(StudentProfile, user=request.user)
        applications = get_student_applications(student)
        return render(
            request,
            self.template_name,
            {"student": student, "applications": applications},
        )


class CompanyOpportunityPipelineView(RoleRequiredMixin, View):
    """Company ATS candidate pipeline sorted by Match Score with HTMX status updates."""

    allowed_roles = (UserRole.COMPANY,)
    template_name = "applications/company_pipeline.html"

    def get(self, request: HttpRequest, opportunity_id: int) -> HttpResponse:
        company = request.user.company_profile
        opportunity = get_object_or_404(
            Opportunity.objects.select_related("company"),
            pk=opportunity_id,
        )
        if opportunity.company_id != company.id:
            raise PermissionDenied("You can only view pipelines for your own postings.")

        status_filter = request.GET.get("status", "").strip()
        applications = list(
            get_opportunity_pipeline(opportunity=opportunity, status_filter=status_filter)
        )
        for app in applications:
            app.next_choices = get_valid_next_statuses(app, request.user)

        stage_counts = get_pipeline_stage_counts(opportunity)
        return render(
            request,
            self.template_name,
            {
                "opportunity": opportunity,
                "applications": applications,
                "stage_counts": stage_counts,
                "status_filter": status_filter,
                "status_choices": ApplicationStatus.choices,
                "bulk_targets": [
                    (s, label)
                    for s, label in ApplicationStatus.choices
                    if s != ApplicationStatus.APPLIED and s != ApplicationStatus.ACCEPTED
                ],
            },
        )


class ApplicationTransitionView(RoleRequiredMixin, View):
    """HTMX/POST endpoint executing an atomic ATS status transition."""

    allowed_roles = (UserRole.COMPANY, UserRole.STUDENT)

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        to_status = request.POST.get("status", "").strip()
        note = request.POST.get("note", "").strip()
        try:
            application = transition_application_status(
                application_id=pk,
                to_status=to_status,
                actor=request.user,
                note=note,
            )
        except ValidationError as exc:
            err = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
            messages.error(request, err)
            if is_htmx(request):
                return HttpResponse(err, status=400)
            return redirect("dashboards:home")

        if is_htmx(request):
            if request.user.is_company:
                application.next_choices = get_valid_next_statuses(application, request.user)
                return render(
                    request,
                    "applications/partials/company_applicant_row.html",
                    {"app": application},
                )
            return render(
                request,
                "applications/partials/student_application_card.html",
                {"app": application},
            )

        messages.success(request, f"Application updated to {application.get_status_display()}.")
        if request.user.is_company:
            return redirect("applications:company_pipeline", opportunity_id=application.opportunity_id)
        return redirect("applications:my_list")


class CompanyBulkTransitionView(RoleRequiredMixin, View):
    """Bulk-transition selected candidate applications for a company-owned opportunity."""

    allowed_roles = (UserRole.COMPANY,)

    def post(self, request: HttpRequest, opportunity_id: int) -> HttpResponse:
        opportunity = get_object_or_404(Opportunity, pk=opportunity_id)
        if opportunity.company_id != request.user.company_profile.id:
            raise PermissionDenied("You do not own this posting.")

        selected_ids = [int(i) for i in request.POST.getlist("application_ids") if i.isdigit()]
        to_status = request.POST.get("status", "").strip()
        note = request.POST.get("note", "Bulk pipeline update").strip()

        if not selected_ids or not to_status:
            messages.warning(request, "Select at least one applicant and a target stage.")
            return redirect("applications:company_pipeline", opportunity_id=opportunity.pk)

        updated_count = bulk_transition_applications(
            opportunity=opportunity,
            application_ids=selected_ids,
            to_status=to_status,
            actor=request.user,
            note=note,
        )
        messages.success(request, f"Updated {updated_count} application(s).")
        return redirect("applications:company_pipeline", opportunity_id=opportunity.pk)
