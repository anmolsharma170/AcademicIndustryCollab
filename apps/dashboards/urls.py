"""URL routes for landing page and role dashboards."""

from django.urls import path

from .views import (
    CompanyDashboardView,
    DashboardHomeView,
    LandingView,
    StudentDashboardView,
    UniversityDashboardView,
)

app_name = "dashboards"

urlpatterns = [
    path("", LandingView.as_view(), name="landing"),
    path("dashboard/", DashboardHomeView.as_view(), name="home"),
    path("dashboard/student/", StudentDashboardView.as_view(), name="student"),
    path("dashboard/company/", CompanyDashboardView.as_view(), name="company"),
    path("dashboard/university/", UniversityDashboardView.as_view(), name="university"),
]
