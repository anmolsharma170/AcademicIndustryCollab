"""Optimized ORM aggregations and insights for Student, Company, and University dashboards."""

from __future__ import annotations

from collections import Counter
import json

from django.db.models import Avg, Count, Q

from apps.accounts.models import University
from apps.applications.models import Application, ApplicationStatus
from apps.applications.selectors.pipeline import get_student_applications
from apps.opportunities.models import (
    ApprovalStatus,
    CompensationUnit,
    Opportunity,
    OpportunitySkill,
    OpportunityStatus,
    RequirementType,
)
from apps.opportunities.selectors.postings import get_company_opportunities, get_student_opportunity_feed
from apps.opportunities.services.recommendation import default_recommendation_engine
from apps.profiles.models import (
    CompanyProfile,
    PartnershipStatus,
    StudentProfile,
    UniversityCompanyPartnership,
)
from apps.profiles.services.completion import compute_student_profile_strength
from apps.skills.models import StudentSkill


def get_student_dashboard_data(student: StudentProfile) -> dict:
    """Assemble profile strength, top matched roles, application tracker, and skill-gap insights."""
    strength = compute_student_profile_strength(student, persist=False)
    applications = list(get_student_applications(student))
    applied_ids = {app.opportunity_id for app in applications}

    feed = list(get_student_opportunity_feed(student=student))
    ranked = default_recommendation_engine.rank_opportunities_for_student(student, feed)

    # Compute missing skill frequency across active opportunities
    gap_counter: Counter[str] = Counter()
    for _, match in ranked:
        for skill_name in match.missing_required:
            gap_counter[skill_name] += 1

    top_recommendations = [(opp, match) for opp, match in ranked if opp.pk not in applied_ids][:4]
    if not top_recommendations:
        top_recommendations = ranked[:4]

    active_interviews = sum(
        1 for a in applications if a.status in (ApplicationStatus.SHORTLISTED, ApplicationStatus.INTERVIEW_SCHEDULED)
    )
    offers_count = sum(1 for a in applications if a.status in (ApplicationStatus.OFFERED, ApplicationStatus.ACCEPTED))
    verified_skills_count = sum(1 for ss in student.student_skills.all() if ss.is_verified)

    return {
        "student": student,
        "strength": strength,
        "top_recommendations": top_recommendations,
        "recent_applications": applications[:5],
        "total_applications": len(applications),
        "active_interviews": active_interviews,
        "offers_count": offers_count,
        "verified_skills_count": verified_skills_count,
        "skill_gaps": gap_counter.most_common(5),
    }


def get_company_dashboard_data(company: CompanyProfile) -> dict:
    """Assemble company KPIs, pipeline funnel chart data, and top-matched applicants."""
    opportunities = list(get_company_opportunities(company))
    active_count = sum(1 for o in opportunities if o.status == OpportunityStatus.ACTIVE)

    stage_rows = (
        Application.objects.filter(opportunity__company=company)
        .values("status")
        .annotate(total=Count("id"))
    )
    stage_map = {status: 0 for status in ApplicationStatus.values}
    for row in stage_rows:
        stage_map[row["status"]] = row["total"]

    total_applicants = sum(stage_map.values())
    shortlisted_plus = (
        stage_map[ApplicationStatus.SHORTLISTED]
        + stage_map[ApplicationStatus.INTERVIEW_SCHEDULED]
    )
    offers_extended = stage_map[ApplicationStatus.OFFERED] + stage_map[ApplicationStatus.ACCEPTED]

    top_candidates = (
        Application.objects.filter(opportunity__company=company)
        .select_related("student__user", "student__university", "opportunity")
        .order_by("-match_score_snapshot", "-applied_at")[:6]
    )

    funnel_labels = [label for _, label in ApplicationStatus.choices]
    funnel_values = [stage_map[val] for val, _ in ApplicationStatus.choices]

    return {
        "company": company,
        "opportunities": opportunities[:5],
        "active_postings_count": active_count,
        "total_applicants": total_applicants,
        "shortlisted_plus": shortlisted_plus,
        "offers_extended": offers_extended,
        "top_candidates": top_candidates,
        "funnel_labels_json": json.dumps(funnel_labels),
        "funnel_values_json": json.dumps(funnel_values),
    }


def get_university_dashboard_data(university: University) -> dict:
    """Assemble placement metrics, average stipend/CTC, top hiring companies, and skill demand charts."""
    students_qs = StudentProfile.objects.filter(university=university)
    total_students = students_qs.count()
    verified_students = students_qs.filter(is_verified_by_university=True).count()

    placed_students = (
        Application.objects.filter(
            student__university=university,
            status__in=[ApplicationStatus.ACCEPTED, ApplicationStatus.OFFERED],
        )
        .values("student_id")
        .distinct()
        .count()
    )
    accepted_students = (
        Application.objects.filter(
            student__university=university,
            status=ApplicationStatus.ACCEPTED,
        )
        .values("student_id")
        .distinct()
        .count()
    )
    placement_rate = round((placed_students / total_students) * 100, 1) if total_students else 0.0

    # Average stipend / CTC across active/approved opportunities visible to campus
    campus_opps = Opportunity.objects.filter(
        approval_status=ApprovalStatus.APPROVED,
    ).filter(Q(target_university=university) | Q(target_university__isnull=True))

    avg_monthly_stipend = (
        campus_opps.filter(compensation_unit=CompensationUnit.MONTHLY, stipend_max__gt=0)
        .aggregate(avg_val=Avg("stipend_max"))["avg_val"]
        or 0
    )
    avg_annual_ctc = (
        campus_opps.filter(compensation_unit=CompensationUnit.ANNUAL, stipend_max__gt=0)
        .aggregate(avg_val=Avg("stipend_max"))["avg_val"]
        or 0
    )

    # Top hiring companies by offers/applications at this university
    top_companies_rows = list(
        Application.objects.filter(student__university=university)
        .values("opportunity__company__company_name")
        .annotate(
            total_apps=Count("id"),
            offers=Count("id", filter=Q(status__in=[ApplicationStatus.OFFERED, ApplicationStatus.ACCEPTED])),
        )
        .order_by("-offers", "-total_apps")[:6]
    )

    # Most in-demand skills vs campus student supply
    demand_rows = list(
        OpportunitySkill.objects.filter(
            opportunity__in=campus_opps,
            requirement_type=RequirementType.REQUIRED,
        )
        .values("skill_id", "skill__name")
        .annotate(demand=Count("opportunity_id", distinct=True))
        .order_by("-demand", "skill__name")[:7]
    )
    skill_ids = [r["skill_id"] for r in demand_rows]
    supply_map = {
        r["skill_id"]: r["supply"]
        for r in StudentSkill.objects.filter(
            student__university=university,
            skill_id__in=skill_ids,
        )
        .values("skill_id")
        .annotate(supply=Count("student_id", distinct=True))
    }

    pending_opportunities_count = (
        Opportunity.objects.filter(approval_status=ApprovalStatus.PENDING)
        .filter(Q(target_university=university) | Q(target_university__isnull=True))
        .count()
    )
    pending_partnerships_count = UniversityCompanyPartnership.objects.filter(
        university=university, status=PartnershipStatus.PENDING
    ).count()
    pending_skills_count = StudentSkill.objects.filter(
        student__university=university, is_verified=False
    ).count()

    return {
        "university": university,
        "total_students": total_students,
        "verified_students": verified_students,
        "placed_students": placed_students,
        "accepted_students": accepted_students,
        "placement_rate": placement_rate,
        "avg_monthly_stipend": round(avg_monthly_stipend),
        "avg_annual_ctc_lpa": round(avg_annual_ctc / 100000, 1) if avg_annual_ctc else 0.0,
        "pending_opportunities_count": pending_opportunities_count,
        "pending_partnerships_count": pending_partnerships_count,
        "pending_skills_count": pending_skills_count,
        "company_labels_json": json.dumps([r["opportunity__company__company_name"] for r in top_companies_rows]),
        "company_apps_json": json.dumps([r["total_apps"] for r in top_companies_rows]),
        "company_offers_json": json.dumps([r["offers"] for r in top_companies_rows]),
        "skill_labels_json": json.dumps([r["skill__name"] for r in demand_rows]),
        "skill_demand_json": json.dumps([r["demand"] for r in demand_rows]),
        "skill_supply_json": json.dumps([supply_map.get(r["skill_id"], 0) for r in demand_rows]),
    }
