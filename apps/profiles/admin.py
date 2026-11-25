"""Django admin registration for profiles and campus partnerships."""

from django.contrib import admin

from .models import CompanyProfile, ProjectShowcase, StudentProfile, UniversityCompanyPartnership


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "university", "department", "graduation_year", "cgpa", "is_verified_by_university")
    list_filter = ("university", "graduation_year", "is_verified_by_university", "academic_standing")
    search_fields = ("user__full_name", "user__email", "roll_number", "department")


@admin.register(ProjectShowcase)
class ProjectShowcaseAdmin(admin.ModelAdmin):
    list_display = ("title", "student", "tech_stack", "created_at")
    search_fields = ("title", "student__user__full_name", "tech_stack")


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ("company_name", "industry", "company_size", "headquarters", "is_verified")
    list_filter = ("industry", "company_size", "is_verified")
    search_fields = ("company_name", "industry", "headquarters")


@admin.register(UniversityCompanyPartnership)
class UniversityCompanyPartnershipAdmin(admin.ModelAdmin):
    list_display = ("company", "university", "status", "reviewed_by", "reviewed_at")
    list_filter = ("status", "university")
    search_fields = ("company__company_name", "university__name")
