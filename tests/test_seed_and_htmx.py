"""Phase 6 integration tests: Idempotent seed_data and full HTTP/HTMX end-to-end smoke suite."""

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.models import User
from apps.applications.models import Application
from apps.opportunities.models import Opportunity


@pytest.mark.django_db
def test_seed_data_idempotent_and_all_role_pages_render(client):
    call_command("seed_data")
    first_opp_count = Opportunity.objects.count()
    first_app_count = Application.objects.count()
    assert first_opp_count >= 7
    assert first_app_count >= 10

    # Re-running seed_data must remain idempotent
    call_command("seed_data")
    assert Opportunity.objects.count() == first_opp_count
    assert Application.objects.count() == first_app_count

    # Student flow + HTMX opportunity search
    student_user = User.objects.get(email="student@nitk.edu")
    client.force_login(student_user)
    for url in (
        reverse("dashboards:student"),
        reverse("opportunities:feed"),
        reverse("applications:my_list"),
        reverse("profiles:student_edit"),
        reverse("skills:manage"),
        reverse("notifications:inbox"),
        reverse("notifications:dropdown"),
    ):
        assert client.get(url).status_code == 200

    htmx_feed = client.get(
        reverse("opportunities:feed"),
        {"q": "Backend"},
        HTTP_HX_REQUEST="true",
    )
    assert htmx_feed.status_code == 200
    assert b"Backend Platform Intern" in htmx_feed.content

    # Company flow + ATS pipeline
    company_user = User.objects.get(email="hr@cloudscale.io")
    client.force_login(company_user)
    company_opp = Opportunity.objects.filter(company__user=company_user).first()
    for url in (
        reverse("dashboards:company"),
        reverse("opportunities:company_list"),
        reverse("opportunities:create"),
        reverse("profiles:company_edit"),
        reverse("applications:company_pipeline", args=[company_opp.pk]),
    ):
        assert client.get(url).status_code == 200

    # University Admin flow
    admin_user = User.objects.get(email="admin@nitk.edu")
    client.force_login(admin_user)
    for url in (
        reverse("dashboards:university"),
        reverse("opportunities:university_approvals"),
        reverse("skills:verify_queue"),
        reverse("profiles:university_verifications"),
    ):
        assert client.get(url).status_code == 200
