"""Views for Student skill management and University Admin skill verification."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.accounts.models import UserRole
from apps.core.mixins import RoleRequiredMixin, is_htmx
from apps.profiles.models import StudentProfile
from apps.profiles.services.completion import compute_student_profile_strength
from .forms import StudentSkillAddForm
from .models import Skill, SkillCategory, StudentSkill


class StudentSkillsManageView(RoleRequiredMixin, View):
    """Allow students to add, update proficiency, and view verification badges on skills."""

    allowed_roles = (UserRole.STUDENT,)
    template_name = "skills/manage_skills.html"

    def _context(self, student: StudentProfile, form: StudentSkillAddForm | None = None) -> dict:
        student_skills = student.student_skills.select_related("skill", "verified_by").all()
        return {
            "student": student,
            "student_skills": student_skills,
            "form": form or StudentSkillAddForm(),
            "categories": SkillCategory.choices,
            "catalog_skills": Skill.objects.all(),
        }

    def get(self, request: HttpRequest) -> HttpResponse:
        student = get_object_or_404(StudentProfile, user=request.user)
        return render(request, self.template_name, self._context(student))

    def post(self, request: HttpRequest) -> HttpResponse:
        student = get_object_or_404(StudentProfile, user=request.user)
        form = StudentSkillAddForm(request.POST)
        if form.is_valid():
            skill = form.cleaned_data["skill"]
            proficiency = form.cleaned_data["proficiency_level"]
            obj, created = StudentSkill.objects.get_or_create(
                student=student,
                skill=skill,
                defaults={"proficiency_level": proficiency},
            )
            if not created:
                obj.proficiency_level = proficiency
                obj.save(update_fields=["proficiency_level"])
            compute_student_profile_strength(student, persist=True)
            if is_htmx(request):
                return render(
                    request,
                    "skills/partials/student_skill_list.html",
                    self._context(student),
                )
            messages.success(request, f"Saved {skill.name} on your skill profile.")
            return redirect("skills:manage")

        if is_htmx(request):
            return render(
                request,
                "skills/partials/student_skill_list.html",
                self._context(student, form=form),
            )
        return render(request, self.template_name, self._context(student, form=form))


class StudentSkillDeleteView(RoleRequiredMixin, View):
    """Remove a skill from the logged-in student's profile."""

    allowed_roles = (UserRole.STUDENT,)

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        student = get_object_or_404(StudentProfile, user=request.user)
        student_skill = get_object_or_404(StudentSkill, pk=pk, student=student)
        student_skill.delete()
        compute_student_profile_strength(student, persist=True)
        if is_htmx(request):
            student_skills = student.student_skills.select_related("skill", "verified_by").all()
            return render(
                request,
                "skills/partials/student_skill_list.html",
                {"student": student, "student_skills": student_skills},
            )
        messages.success(request, "Skill removed from your profile.")
        return redirect("skills:manage")


class UniversitySkillVerifyQueueView(RoleRequiredMixin, View):
    """University Admin queue to verify student skills within their campus."""

    allowed_roles = (UserRole.UNIVERSITY_ADMIN,)
    template_name = "skills/verify_queue.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        admin_profile = request.user.university_admin_profile
        status_filter = request.GET.get("status", "pending")
        qs = (
            StudentSkill.objects.filter(student__university=admin_profile.university)
            .select_related("student__user", "skill", "verified_by")
            .order_by("is_verified", "student__user__full_name", "skill__name")
        )
        if status_filter == "pending":
            qs = qs.filter(is_verified=False)
        elif status_filter == "verified":
            qs = qs.filter(is_verified=True)

        return render(
            request,
            self.template_name,
            {
                "university": admin_profile.university,
                "student_skills": qs,
                "status_filter": status_filter,
            },
        )


class ToggleSkillVerificationView(RoleRequiredMixin, View):
    """Verify or unverify a student's skill if they belong to the admin's university."""

    allowed_roles = (UserRole.UNIVERSITY_ADMIN,)

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        admin_profile = request.user.university_admin_profile
        student_skill = get_object_or_404(
            StudentSkill.objects.select_related("student__user", "skill"),
            pk=pk,
        )
        if student_skill.student.university_id != admin_profile.university_id:
            raise PermissionDenied("You can only verify skills for students at your university.")

        new_state = not student_skill.is_verified
        student_skill.is_verified = new_state
        student_skill.verified_by = request.user if new_state else None
        student_skill.verified_at = timezone.now() if new_state else None
        student_skill.save(update_fields=["is_verified", "verified_by", "verified_at"])

        if is_htmx(request):
            return render(
                request,
                "skills/partials/skill_verify_row.html",
                {"entry": student_skill},
            )
        messages.success(request, "Skill verification status updated.")
        return redirect("skills:verify_queue")
