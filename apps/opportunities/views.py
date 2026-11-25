"""Views for opportunity feeds, company posting CRUD, and university approvals."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.accounts.models import UserRole
from apps.core.mixins import OnboardingRequiredMixin, RoleRequiredMixin, is_htmx, render_htmx_or_full
from apps.profiles.models import StudentProfile
from .forms import OpportunityForm
from .models import (
    ApprovalStatus,
    Opportunity,
    OpportunityStatus,
    OpportunityType,
    WorkMode,
)
from .selectors.postings import (
    base_opportunity_queryset,
    get_company_opportunities,
    get_student_opportunity_feed,
    get_university_opportunity_queue,
)
from .services.postings import (
    review_opportunity_by_university,
    save_opportunity_with_skills,
    transition_opportunity_status,
)
from .services.recommendation import default_recommendation_engine


class OpportunityFeedView(OnboardingRequiredMixin, View):
    """Searchable opportunity feed ranked by skill-based Match Score for students."""

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_company:
            return redirect("opportunities:company_list")
        if request.user.is_university_admin:
            return redirect("opportunities:university_approvals")

        student = get_object_or_404(
            StudentProfile.objects.select_related("university").prefetch_related("student_skills__skill"),
            user=request.user,
        )
        query = request.GET.get("q", "").strip()
        opp_type = request.GET.get("type", "").strip()
        work_mode = request.GET.get("mode", "").strip()
        min_match_raw = request.GET.get("min_match", "").strip()

        opportunities = get_student_opportunity_feed(
            student=student,
            query=query,
            opportunity_type=opp_type,
            work_mode=work_mode,
        )
        ranked = default_recommendation_engine.rank_opportunities_for_student(student, opportunities)

        if min_match_raw.isdigit():
            min_match = int(min_match_raw)
            ranked = [(opp, match) for opp, match in ranked if match.score >= min_match]

        applied_ids: set[int] = set()
        applications_rel = getattr(student, "applications", None)
        if applications_rel is not None:
            applied_ids = set(applications_rel.values_list("opportunity_id", flat=True))

        context = {
            "ranked_opportunities": ranked,
            "applied_ids": applied_ids,
            "query": query,
            "selected_type": opp_type,
            "selected_mode": work_mode,
            "min_match": min_match_raw,
            "opportunity_types": OpportunityType.choices,
            "work_modes": WorkMode.choices,
        }
        return render_htmx_or_full(
            request,
            partial_template="opportunities/partials/feed_list.html",
            full_template="opportunities/feed.html",
            context=context,
        )


class OpportunityDetailView(OnboardingRequiredMixin, View):
    """Detailed opportunity view with match breakdown (students) or matched candidates (company)."""

    template_name = "opportunities/detail.html"

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        opportunity = get_object_or_404(base_opportunity_queryset(), pk=pk)
        context: dict = {"opportunity": opportunity}

        if request.user.is_student:
            student = get_object_or_404(
                StudentProfile.objects.select_related("university").prefetch_related("student_skills__skill"),
                user=request.user,
            )
            if (
                opportunity.status != OpportunityStatus.ACTIVE
                or opportunity.approval_status != ApprovalStatus.APPROVED
                or (opportunity.target_university_id and opportunity.target_university_id != student.university_id)
            ):
                raise PermissionDenied("This opportunity is not available for your campus.")
            match = default_recommendation_engine.score_pair(student, opportunity)
            existing_application = None
            applications_rel = getattr(student, "applications", None)
            if applications_rel is not None:
                existing_application = applications_rel.filter(opportunity=opportunity).first()
            context["match"] = match
            context["existing_application"] = existing_application
        elif request.user.is_company:
            if opportunity.company_id != request.user.company_profile.id:
                raise PermissionDenied("You can only view match details for your own postings.")
            candidates_qs = StudentProfile.objects.select_related("user", "university").prefetch_related(
                "student_skills__skill"
            )
            if opportunity.target_university_id:
                candidates_qs = candidates_qs.filter(university_id=opportunity.target_university_id)
            context["top_candidates"] = default_recommendation_engine.rank_students_for_opportunity(
                candidates_qs, opportunity
            )[:10]

        return render(request, self.template_name, context)


class CompanyOpportunityListView(RoleRequiredMixin, View):
    """Company management console for its own internship/placement postings."""

    allowed_roles = (UserRole.COMPANY,)
    template_name = "opportunities/company_list.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        company = request.user.company_profile
        opportunities = get_company_opportunities(company)
        return render(
            request,
            self.template_name,
            {"company": company, "opportunities": opportunities},
        )


class OpportunityCreateView(RoleRequiredMixin, View):
    """Create a new opportunity posting for a Company."""

    allowed_roles = (UserRole.COMPANY,)
    template_name = "opportunities/form.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, self.template_name, {"form": OpportunityForm(), "is_edit": False})

    def post(self, request: HttpRequest) -> HttpResponse:
        form = OpportunityForm(request.POST)
        if form.is_valid():
            opportunity = form.save(commit=False)
            opportunity.company = request.user.company_profile
            opportunity.eligible_grad_years = form.cleaned_data["eligible_grad_years_input"]
            save_opportunity_with_skills(
                opportunity=opportunity,
                required_skills=form.cleaned_data["required_skills"],
                bonus_skills=form.cleaned_data["bonus_skills"],
                min_required_proficiency=form.cleaned_data["min_required_proficiency"],
            )
            messages.success(request, f"Opportunity '{opportunity.title}' published.")
            return redirect("opportunities:company_list")
        return render(request, self.template_name, {"form": form, "is_edit": False})


class OpportunityEditView(RoleRequiredMixin, View):
    """Edit an existing company-owned opportunity posting."""

    allowed_roles = (UserRole.COMPANY,)
    template_name = "opportunities/form.html"

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        opportunity = get_object_or_404(base_opportunity_queryset(), pk=pk)
        if opportunity.company_id != request.user.company_profile.id:
            raise PermissionDenied("You do not own this posting.")
        return render(
            request,
            self.template_name,
            {"form": OpportunityForm(instance=opportunity), "opportunity": opportunity, "is_edit": True},
        )

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        opportunity = get_object_or_404(base_opportunity_queryset(), pk=pk)
        if opportunity.company_id != request.user.company_profile.id:
            raise PermissionDenied("You do not own this posting.")
        form = OpportunityForm(request.POST, instance=opportunity)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.eligible_grad_years = form.cleaned_data["eligible_grad_years_input"]
            save_opportunity_with_skills(
                opportunity=updated,
                required_skills=form.cleaned_data["required_skills"],
                bonus_skills=form.cleaned_data["bonus_skills"],
                min_required_proficiency=form.cleaned_data["min_required_proficiency"],
            )
            messages.success(request, f"Updated '{updated.title}'.")
            return redirect("opportunities:company_list")
        return render(
            request,
            self.template_name,
            {"form": form, "opportunity": opportunity, "is_edit": True},
        )


class OpportunityStatusUpdateView(RoleRequiredMixin, View):
    """HTMX/POST endpoint to pause, activate, or close a company's posting."""

    allowed_roles = (UserRole.COMPANY,)

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        opportunity = get_object_or_404(base_opportunity_queryset(), pk=pk)
        if opportunity.company_id != request.user.company_profile.id:
            raise PermissionDenied("You do not own this posting.")
        new_status = request.POST.get("status", OpportunityStatus.PAUSED)
        transition_opportunity_status(opportunity, new_status)
        if is_htmx(request):
            opportunity.applicant_count = opportunity.applications.count() if hasattr(opportunity, "applications") else 0
            return render(
                request,
                "opportunities/partials/company_opportunity_row.html",
                {"opp": opportunity},
            )
        messages.success(request, f"Posting status updated to {opportunity.get_status_display()}.")
        return redirect("opportunities:company_list")


class UniversityOpportunityApprovalQueueView(RoleRequiredMixin, View):
    """University Admin queue to approve, reject, or feature industry postings."""

    allowed_roles = (UserRole.UNIVERSITY_ADMIN,)
    template_name = "opportunities/university_approvals.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        university = request.user.university_admin_profile.university
        opportunities = get_university_opportunity_queue(university)
        return render(
            request,
            self.template_name,
            {"university": university, "opportunities": opportunities},
        )


class OpportunityApprovalActionView(RoleRequiredMixin, View):
    """HTMX/POST action for University Admin to approve, reject, or feature an opportunity."""

    allowed_roles = (UserRole.UNIVERSITY_ADMIN,)

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        university = request.user.university_admin_profile.university
        opportunity = get_object_or_404(base_opportunity_queryset(), pk=pk)
        if opportunity.target_university_id and opportunity.target_university_id != university.id:
            raise PermissionDenied("This opportunity is targeted at another university.")

        approval_status = request.POST.get("approval_status", opportunity.approval_status)
        is_featured_raw = request.POST.get("is_featured")
        is_featured = (
            is_featured_raw.lower() == "true"
            if is_featured_raw is not None
            else opportunity.is_featured
        )
        review_opportunity_by_university(
            opportunity=opportunity,
            approval_status=approval_status,
            is_featured=is_featured,
            admin_user=request.user,
        )
        if is_htmx(request):
            return render(
                request,
                "opportunities/partials/approval_row.html",
                {"opp": opportunity},
            )
        messages.success(request, f"Updated review status for '{opportunity.title}'.")
        return redirect("opportunities:university_approvals")
