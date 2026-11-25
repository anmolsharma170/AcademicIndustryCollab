"""URL routes for opportunity discovery, management, and university review."""

from django.urls import path

from .views import (
    CompanyOpportunityListView,
    OpportunityApprovalActionView,
    OpportunityCreateView,
    OpportunityDetailView,
    OpportunityEditView,
    OpportunityFeedView,
    OpportunityStatusUpdateView,
    UniversityOpportunityApprovalQueueView,
)

app_name = "opportunities"

urlpatterns = [
    path("", OpportunityFeedView.as_view(), name="feed"),
    path("manage/", CompanyOpportunityListView.as_view(), name="company_list"),
    path("create/", OpportunityCreateView.as_view(), name="create"),
    path("<int:pk>/", OpportunityDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", OpportunityEditView.as_view(), name="edit"),
    path("<int:pk>/status/", OpportunityStatusUpdateView.as_view(), name="status_update"),
    path("approvals/", UniversityOpportunityApprovalQueueView.as_view(), name="university_approvals"),
    path("approvals/<int:pk>/review/", OpportunityApprovalActionView.as_view(), name="review"),
]
