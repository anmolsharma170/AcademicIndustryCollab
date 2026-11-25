"""URL routes for skill management and university skill verification."""

from django.urls import path

from .views import (
    StudentSkillDeleteView,
    StudentSkillsManageView,
    ToggleSkillVerificationView,
    UniversitySkillVerifyQueueView,
)

app_name = "skills"

urlpatterns = [
    path("manage/", StudentSkillsManageView.as_view(), name="manage"),
    path("manage/<int:pk>/delete/", StudentSkillDeleteView.as_view(), name="delete"),
    path("verify/", UniversitySkillVerifyQueueView.as_view(), name="verify_queue"),
    path("verify/<int:pk>/toggle/", ToggleSkillVerificationView.as_view(), name="toggle_verify"),
]
