"""Django admin configuration for Applications and Status Logs."""

from django.contrib import admin

from .models import Application, ApplicationStatusLog


class ApplicationStatusLogInline(admin.TabularInline):
    model = ApplicationStatusLog
    extra = 0
    readonly_fields = ("from_status", "to_status", "changed_by", "note", "created_at")


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("student", "opportunity", "status", "match_score_snapshot", "applied_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("student__user__full_name", "opportunity__title", "opportunity__company__company_name")
    inlines = [ApplicationStatusLogInline]
