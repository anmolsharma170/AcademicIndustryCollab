"""Django admin configuration for standardized skills and student skills."""

from django.contrib import admin

from .models import Skill, StudentSkill


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "category")
    list_filter = ("category",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(StudentSkill)
class StudentSkillAdmin(admin.ModelAdmin):
    list_display = ("student", "skill", "proficiency_level", "is_verified", "verified_by")
    list_filter = ("is_verified", "proficiency_level", "skill__category")
    search_fields = ("student__user__full_name", "skill__name")
