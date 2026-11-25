"""Django admin configuration for accounts and universities."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import University, UniversityAdminProfile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "full_name", "role", "onboarding_completed", "is_active", "is_staff")
    list_filter = ("role", "onboarding_completed", "is_active")
    search_fields = ("email", "full_name")
    ordering = ("-created_at",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Info", {"fields": ("full_name", "role", "onboarding_completed")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login",)}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "role", "password1", "password2"),
            },
        ),
    )


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "city", "country", "is_verified")
    list_filter = ("is_verified", "country")
    search_fields = ("name", "code", "city")


@admin.register(UniversityAdminProfile)
class UniversityAdminProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "university", "designation", "department")
    list_filter = ("university",)
    search_fields = ("user__email", "user__full_name", "university__name")
