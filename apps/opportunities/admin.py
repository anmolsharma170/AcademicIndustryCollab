"""Django admin registration for opportunities and required skills."""

from django.contrib import admin

from .models import Opportunity, OpportunitySkill


class OpportunitySkillInline(admin.TabularInline):
    model = OpportunitySkill
    extra = 1


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "company",
        "opportunity_type",
        "work_mode",
        "status",
        "approval_status",
        "is_featured",
        "deadline",
    )
    list_filter = ("opportunity_type", "work_mode", "status", "approval_status", "is_featured")
    search_fields = ("title", "company__company_name", "location")
    inlines = [OpportunitySkillInline]
