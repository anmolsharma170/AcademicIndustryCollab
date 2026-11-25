"""URL routes for application submission, student tracker, and company ATS pipelines."""

from django.urls import path

from .views import (
    ApplicationTransitionView,
    CompanyBulkTransitionView,
    CompanyOpportunityPipelineView,
    StudentApplicationsListView,
    SubmitApplicationView,
)

app_name = "applications"

urlpatterns = [
    path("my/", StudentApplicationsListView.as_view(), name="my_list"),
    path("apply/<int:opportunity_id>/", SubmitApplicationView.as_view(), name="submit"),
    path("opportunity/<int:opportunity_id>/pipeline/", CompanyOpportunityPipelineView.as_view(), name="company_pipeline"),
    path("opportunity/<int:opportunity_id>/bulk-transition/", CompanyBulkTransitionView.as_view(), name="bulk_transition"),
    path("<int:pk>/transition/", ApplicationTransitionView.as_view(), name="transition"),
]
