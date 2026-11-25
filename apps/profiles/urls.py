"""URL routes for student profiles, company profiles, and campus verifications."""

from django.urls import path

from .views import (
    CompanyPartnershipRequestView,
    CompanyProfileDetailView,
    CompanyProfileEditView,
    ProjectShowcaseCreateView,
    ProjectShowcaseDeleteView,
    StudentProfileDetailView,
    StudentProfileEditView,
    ToggleStudentVerificationView,
    UniversityVerificationQueueView,
    UpdatePartnershipStatusView,
)

app_name = "profiles"

urlpatterns = [
    path("student/edit/", StudentProfileEditView.as_view(), name="student_edit"),
    path("student/<int:pk>/", StudentProfileDetailView.as_view(), name="student_detail"),
    path("student/projects/add/", ProjectShowcaseCreateView.as_view(), name="project_add"),
    path("student/projects/<int:pk>/delete/", ProjectShowcaseDeleteView.as_view(), name="project_delete"),
    path("company/edit/", CompanyProfileEditView.as_view(), name="company_edit"),
    path("company/<int:pk>/", CompanyProfileDetailView.as_view(), name="company_detail"),
    path("company/partnerships/request/", CompanyPartnershipRequestView.as_view(), name="partnership_request"),
    path("university/verifications/", UniversityVerificationQueueView.as_view(), name="university_verifications"),
    path("university/students/<int:pk>/toggle-verify/", ToggleStudentVerificationView.as_view(), name="toggle_student_verify"),
    path("university/partnerships/<int:pk>/status/", UpdatePartnershipStatusView.as_view(), name="update_partnership_status"),
]
