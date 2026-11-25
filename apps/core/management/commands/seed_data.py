"""Idempotent management command to populate realistic demo data for the portal."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import University, UniversityAdminProfile, User, UserRole
from apps.applications.models import Application, ApplicationStatus, ApplicationStatusLog
from apps.notifications.models import Notification, NotificationCategory
from apps.opportunities.models import (
    ApprovalStatus,
    CompensationUnit,
    Opportunity,
    OpportunitySkill,
    OpportunityStatus,
    OpportunityType,
    RequirementType,
    WorkMode,
)
from apps.opportunities.services.recommendation import default_recommendation_engine
from apps.profiles.models import (
    AcademicStanding,
    CompanyProfile,
    CompanySize,
    PartnershipStatus,
    ProjectShowcase,
    StudentProfile,
    UniversityCompanyPartnership,
)
from apps.profiles.services.completion import compute_student_profile_strength
from apps.skills.models import ProficiencyLevel, Skill, SkillCategory, StudentSkill


class Command(BaseCommand):
    help = "Seed realistic universities, companies, students, skills, opportunities, and ATS applications."

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        self.stdout.write("Seeding Academia-Industry Collaboration Portal...")

        # 1. Universities & Admins
        nitk, _ = University.objects.get_or_create(
            code="NITK",
            defaults={
                "name": "National Institute of Technology Karnataka",
                "domain": "nitk.edu.in",
                "city": "Surathkal",
                "country": "India",
                "website": "https://nitk.ac.in",
                "is_verified": True,
            },
        )
        mitb, _ = University.objects.get_or_create(
            code="MITB",
            defaults={
                "name": "Metropolitan Institute of Technology",
                "domain": "mitb.edu",
                "city": "Bengaluru",
                "country": "India",
                "website": "https://mitb.edu",
                "is_verified": True,
            },
        )

        admin_nitk = self._ensure_user("admin@nitk.edu", "Dr. Kavita Rao", UserRole.UNIVERSITY_ADMIN)
        UniversityAdminProfile.objects.get_or_create(
            user=admin_nitk,
            defaults={"university": nitk, "designation": "Head of Career Services", "department": "Placement Cell"},
        )
        admin_mitb = self._ensure_user("admin@mitb.edu", "Prof. Vikram Menon", UserRole.UNIVERSITY_ADMIN)
        UniversityAdminProfile.objects.get_or_create(
            user=admin_mitb,
            defaults={"university": mitb, "designation": "Placement Director", "department": "Industry Relations"},
        )

        # 2. Standardized Skills
        skill_specs = [
            ("Python", SkillCategory.BACKEND),
            ("Django", SkillCategory.BACKEND),
            ("FastAPI", SkillCategory.BACKEND),
            ("PostgreSQL", SkillCategory.BACKEND),
            ("Redis", SkillCategory.BACKEND),
            ("React", SkillCategory.FRONTEND),
            ("TypeScript", SkillCategory.FRONTEND),
            ("Tailwind CSS", SkillCategory.FRONTEND),
            ("Next.js", SkillCategory.FRONTEND),
            ("PyTorch", SkillCategory.AI_ML),
            ("Scikit-Learn", SkillCategory.AI_ML),
            ("LLMs & RAG", SkillCategory.AI_ML),
            ("Docker", SkillCategory.CLOUD_DEVOPS),
            ("Kubernetes", SkillCategory.CLOUD_DEVOPS),
            ("AWS", SkillCategory.CLOUD_DEVOPS),
            ("CI/CD", SkillCategory.CLOUD_DEVOPS),
            ("SQL & Analytics", SkillCategory.DATA),
            ("Apache Spark", SkillCategory.DATA),
            ("Power BI", SkillCategory.DATA),
            ("Embedded C", SkillCategory.CORE_ENG),
            ("ROS2 Robotics", SkillCategory.CORE_ENG),
            ("Product Strategy", SkillCategory.MANAGEMENT),
            ("Agile Delivery", SkillCategory.MANAGEMENT),
            ("Figma", SkillCategory.DESIGN),
        ]
        skills: dict[str, Skill] = {}
        for name, cat in skill_specs:
            obj, _ = Skill.objects.get_or_create(name=name, defaults={"category": cat})
            skills[name] = obj

        # 3. Companies & Partnerships
        company_specs = [
            ("hr@cloudscale.io", "Elena Vance", "CloudScale Systems", "Cloud Infrastructure", CompanySize.GROWTH, "Bengaluru, India", "High-throughput distributed cloud control planes.", True),
            ("talent@quantai.io", "Rohan Kapoor", "QuantAI Labs", "Applied AI & ML", CompanySize.STARTUP, "Hyderabad, India", "Enterprise document intelligence and agentic workflows.", True),
            ("careers@finpulse.io", "Sneha Iyer", "FinPulse Technologies", "FinTech", CompanySize.MID_MARKET, "Mumbai, India", "Real-time payment settlement rails and risk scoring.", True),
            ("robotics@kinetix.io", "Aravind Deshmukh", "Kinetix Robotics", "Autonomous Systems", CompanySize.STARTUP, "Pune, India", "Warehouse AMRs and embedded perception stacks.", False),
        ]
        companies: dict[str, CompanyProfile] = {}
        for email, owner, cname, ind, size, hq, desc, verified in company_specs:
            u = self._ensure_user(email, owner, UserRole.COMPANY)
            cp, _ = CompanyProfile.objects.get_or_create(
                user=u,
                defaults={
                    "company_name": cname,
                    "industry": ind,
                    "company_size": size,
                    "headquarters": hq,
                    "website": f"https://{cname.lower().replace(' ', '')}.example.com",
                    "description": desc,
                    "is_verified": verified,
                },
            )
            companies[cname] = cp

        UniversityCompanyPartnership.objects.get_or_create(
            university=nitk, company=companies["CloudScale Systems"],
            defaults={"status": PartnershipStatus.APPROVED, "reviewed_by": admin_nitk, "reviewed_at": timezone.now()},
        )
        UniversityCompanyPartnership.objects.get_or_create(
            university=nitk, company=companies["QuantAI Labs"],
            defaults={"status": PartnershipStatus.APPROVED, "reviewed_by": admin_nitk, "reviewed_at": timezone.now()},
        )
        UniversityCompanyPartnership.objects.get_or_create(
            university=nitk, company=companies["FinPulse Technologies"],
            defaults={"status": PartnershipStatus.APPROVED, "reviewed_by": admin_nitk, "reviewed_at": timezone.now()},
        )
        UniversityCompanyPartnership.objects.get_or_create(
            university=nitk, company=companies["Kinetix Robotics"],
            defaults={"status": PartnershipStatus.PENDING},
        )
        UniversityCompanyPartnership.objects.get_or_create(
            university=mitb, company=companies["CloudScale Systems"],
            defaults={"status": PartnershipStatus.APPROVED, "reviewed_by": admin_mitb, "reviewed_at": timezone.now()},
        )

        # 4. Students, Skills & Projects
        student_specs = [
            ("student@nitk.edu", "Aarav Mehta", nitk, "22CS101", "Computer Science & Engineering", 2026, "9.12", AcademicStanding.DEANS_LIST, True,
             [("Python", 3, True), ("Django", 3, True), ("PostgreSQL", 2, True), ("Docker", 2, False), ("React", 2, False)],
             "Distributed Systems Telemetry", "Built an OpenTelemetry log aggregator handling 20k events/sec.", "Python, Django, PostgreSQL, Docker"),
            ("ananya@nitk.edu", "Ananya Nair", nitk, "22AI104", "Artificial Intelligence", 2026, "9.35", AcademicStanding.HONORS, True,
             [("Python", 3, True), ("PyTorch", 3, True), ("LLMs & RAG", 3, True), ("FastAPI", 2, False), ("Docker", 2, True)],
             "Campus Research Copilot", "RAG assistant indexing 4,500 university thesis papers.", "Python, PyTorch, LLMs & RAG, FastAPI"),
            ("karthik@nitk.edu", "Karthik Hegde", nitk, "22IT118", "Information Technology", 2026, "8.45", AcademicStanding.GOOD_STANDING, True,
             [("React", 3, True), ("TypeScript", 3, True), ("Tailwind CSS", 3, False), ("Next.js", 2, False), ("Figma", 2, False)],
             "Design System Kit", "Accessible UI component library used by 4 student clubs.", "React, TypeScript, Tailwind CSS"),
            ("diya@nitk.edu", "Diya Kulkarni", nitk, "22EC205", "Electronics & Communication", 2027, "8.75", AcademicStanding.GOOD_STANDING, False,
             [("Python", 2, False), ("Embedded C", 3, True), ("ROS2 Robotics", 2, False), ("Docker", 1, False)],
             "Autonomous Rover SLAM", "ROS2 navigation stack for indoor mapping.", "Embedded C, ROS2 Robotics, Python"),
            ("siddharth@nitk.edu", "Siddharth Joshi", nitk, "22CS142", "Computer Science & Engineering", 2026, "7.90", AcademicStanding.GOOD_STANDING, True,
             [("Python", 2, True), ("SQL & Analytics", 3, True), ("Apache Spark", 2, False), ("Power BI", 2, False)],
             "Placement Analytics Warehouse", "ETL pipeline analyzing historical campus offer trends.", "Python, SQL & Analytics, Power BI"),
            ("ishaan@nitk.edu", "Ishaan Verma", nitk, "23CS109", "Computer Science & Engineering", 2027, "8.20", AcademicStanding.GOOD_STANDING, False,
             [("Python", 2, False), ("Django", 2, False), ("AWS", 2, False), ("CI/CD", 2, False)],
             "CI Runner Dashboard", "Automated GitHub Actions build monitor.", "Python, Django, AWS"),
            ("neha@mitb.edu", "Neha Bansal", mitb, "22CS012", "Computer Science", 2026, "8.95", AcademicStanding.DEANS_LIST, True,
             [("Python", 3, True), ("FastAPI", 3, True), ("PostgreSQL", 3, True), ("Kubernetes", 2, False), ("Docker", 3, True)],
             "Multi-Tenant Billing Engine", "Idempotent Stripe-like usage metering service.", "Python, FastAPI, PostgreSQL, Kubernetes"),
            ("rahul@mitb.edu", "Rahul Sinha", mitb, "22DS027", "Data Science", 2026, "8.60", AcademicStanding.GOOD_STANDING, True,
             [("Python", 3, True), ("Scikit-Learn", 3, True), ("SQL & Analytics", 3, True), ("PyTorch", 2, False)],
             "Credit Default Predictor", "Explainable SHAP scoring pipeline on imbalanced transactions.", "Python, Scikit-Learn, SQL & Analytics"),
        ]

        students: dict[str, StudentProfile] = {}
        for email, fname, uni, roll, dept, grad, cgpa, standing, verified, skill_list, proj_t, proj_s, proj_tech in student_specs:
            u = self._ensure_user(email, fname, UserRole.STUDENT)
            sp, _ = StudentProfile.objects.get_or_create(
                user=u,
                defaults={
                    "university": uni,
                    "roll_number": roll,
                    "department": dept,
                    "graduation_year": grad,
                    "cgpa": Decimal(cgpa),
                    "academic_standing": standing,
                    "bio": f"Final-year {dept} student passionate about building production software.",
                    "github_url": f"https://github.com/{email.split('@')[0]}",
                    "linkedin_url": f"https://linkedin.com/in/{email.split('@')[0]}",
                    "is_verified_by_university": verified,
                    "verified_by": admin_nitk if (verified and uni == nitk) else (admin_mitb if verified else None),
                    "verified_at": timezone.now() if verified else None,
                },
            )
            for sname, prof, sver in skill_list:
                StudentSkill.objects.get_or_create(
                    student=sp,
                    skill=skills[sname],
                    defaults={
                        "proficiency_level": prof,
                        "is_verified": sver,
                        "verified_by": admin_nitk if (sver and uni == nitk) else (admin_mitb if sver else None),
                        "verified_at": timezone.now() if sver else None,
                    },
                )
            ProjectShowcase.objects.get_or_create(
                student=sp,
                title=proj_t,
                defaults={"summary": proj_s, "tech_stack": proj_tech, "repo_url": sp.github_url},
            )
            compute_student_profile_strength(sp, persist=True)
            students[email] = sp

        # 5. Opportunities
        today = timezone.localdate()
        opp_specs = [
            ("CloudScale Systems", "Backend Platform Intern", OpportunityType.INTERNSHIP, WorkMode.HYBRID, "Bengaluru, India", None,
             45000, 60000, CompensationUnit.MONTHLY, "7.50", [2026, 2027], 25, OpportunityStatus.ACTIVE, ApprovalStatus.APPROVED, True,
             ["Python", "Django", "PostgreSQL", "Docker"], ["Redis", "AWS"]),
            ("CloudScale Systems", "Site Reliability Engineer (Full-Time)", OpportunityType.FULL_TIME, WorkMode.ONSITE, "Bengaluru, India", nitk,
             1400000, 1800000, CompensationUnit.ANNUAL, "8.00", [2026], 30, OpportunityStatus.ACTIVE, ApprovalStatus.APPROVED, True,
             ["Python", "Docker", "Kubernetes", "AWS"], ["CI/CD"]),
            ("QuantAI Labs", "Applied ML & LLM Intern", OpportunityType.INTERNSHIP, WorkMode.REMOTE, "Remote", None,
             50000, 75000, CompensationUnit.MONTHLY, "8.00", [2026, 2027], 20, OpportunityStatus.ACTIVE, ApprovalStatus.APPROVED, True,
             ["Python", "PyTorch", "LLMs & RAG", "FastAPI"], ["Docker"]),
            ("QuantAI Labs", "Agentic Workflows Capstone", OpportunityType.CAPSTONE, WorkMode.REMOTE, "Remote", nitk,
             25000, 30000, CompensationUnit.MONTHLY, "7.50", [2026, 2027], 40, OpportunityStatus.ACTIVE, ApprovalStatus.APPROVED, False,
             ["Python", "LLMs & RAG"], ["FastAPI", "React"]),
            ("FinPulse Technologies", "Full-Stack Product Engineer", OpportunityType.FULL_TIME, WorkMode.HYBRID, "Mumbai, India", None,
             1200000, 1600000, CompensationUnit.ANNUAL, "7.50", [2026], 22, OpportunityStatus.ACTIVE, ApprovalStatus.APPROVED, False,
             ["React", "TypeScript", "Python", "PostgreSQL"], ["Tailwind CSS", "Docker"]),
            ("FinPulse Technologies", "Data Analytics Intern", OpportunityType.INTERNSHIP, WorkMode.HYBRID, "Mumbai, India", None,
             35000, 45000, CompensationUnit.MONTHLY, "7.00", [2026, 2027], 18, OpportunityStatus.ACTIVE, ApprovalStatus.APPROVED, False,
             ["Python", "SQL & Analytics", "Power BI"], ["Apache Spark"]),
            ("Kinetix Robotics", "Embedded Perception Intern", OpportunityType.INTERNSHIP, WorkMode.ONSITE, "Pune, India", nitk,
             40000, 50000, CompensationUnit.MONTHLY, "7.50", [2026, 2027], 28, OpportunityStatus.ACTIVE, ApprovalStatus.PENDING, False,
             ["Embedded C", "ROS2 Robotics", "Python"], ["Docker"]),
            ("CloudScale Systems", "Frontend Systems Intern", OpportunityType.INTERNSHIP, WorkMode.REMOTE, "Remote", None,
             40000, 50000, CompensationUnit.MONTHLY, "7.00", [2026, 2027], 14, OpportunityStatus.PAUSED, ApprovalStatus.APPROVED, False,
             ["React", "TypeScript", "Tailwind CSS"], ["Next.js", "Figma"]),
        ]

        opps: dict[str, Opportunity] = {}
        for cname, title, otype, wmode, loc, target_uni, smin, smax, unit, cgpa, grad_yrs, days, st, appr, feat, reqs, bons in opp_specs:
            opp, created = Opportunity.objects.get_or_create(
                company=companies[cname],
                title=title,
                defaults={
                    "target_university": target_uni,
                    "opportunity_type": otype,
                    "work_mode": wmode,
                    "location": loc,
                    "description": f"Join {cname} as a {title} working closely with senior mentors on high-impact production systems.",
                    "eligibility_notes": f"Minimum {cgpa} CGPA required.",
                    "stipend_min": smin,
                    "stipend_max": smax,
                    "compensation_unit": unit,
                    "min_cgpa": Decimal(cgpa),
                    "eligible_grad_years": grad_yrs,
                    "deadline": today + timedelta(days=days),
                    "status": st,
                    "approval_status": appr,
                    "is_featured": feat,
                    "approved_by": admin_nitk if appr == ApprovalStatus.APPROVED else None,
                    "approved_at": timezone.now() if appr == ApprovalStatus.APPROVED else None,
                },
            )
            if created:
                for r in reqs:
                    OpportunitySkill.objects.get_or_create(
                        opportunity=opp, skill=skills[r],
                        defaults={"requirement_type": RequirementType.REQUIRED, "min_proficiency": ProficiencyLevel.INTERMEDIATE},
                    )
                for b in bons:
                    OpportunitySkill.objects.get_or_create(
                        opportunity=opp, skill=skills[b],
                        defaults={"requirement_type": RequirementType.BONUS, "min_proficiency": ProficiencyLevel.BEGINNER},
                    )
            opps[title] = opp

        # 6. Applications across ATS stages
        app_specs = [
            ("student@nitk.edu", "Backend Platform Intern", ApplicationStatus.INTERVIEW_SCHEDULED, "Built distributed OpenTelemetry ingestion in Django."),
            ("student@nitk.edu", "Site Reliability Engineer (Full-Time)", ApplicationStatus.SHORTLISTED, "Strong systems and Docker foundation."),
            ("student@nitk.edu", "Full-Stack Product Engineer", ApplicationStatus.OFFERED, "Comfortable across React and Django APIs."),
            ("ananya@nitk.edu", "Applied ML & LLM Intern", ApplicationStatus.ACCEPTED, "Published campus RAG system with PyTorch."),
            ("ananya@nitk.edu", "Agentic Workflows Capstone", ApplicationStatus.OFFERED, "Interested in agentic evaluation benchmarks."),
            ("karthik@nitk.edu", "Full-Stack Product Engineer", ApplicationStatus.UNDER_REVIEW, "Maintainer of our campus React design kit."),
            ("siddharth@nitk.edu", "Data Analytics Intern", ApplicationStatus.SHORTLISTED, "Built campus placement ETL warehouse."),
            ("ishaan@nitk.edu", "Backend Platform Intern", ApplicationStatus.APPLIED, "Eager to contribute to cloud infrastructure."),
            ("neha@mitb.edu", "Backend Platform Intern", ApplicationStatus.OFFERED, "Built multi-tenant FastAPI metering engine."),
            ("neha@mitb.edu", "Applied ML & LLM Intern", ApplicationStatus.REJECTED, "Applying from systems background."),
            ("rahul@mitb.edu", "Data Analytics Intern", ApplicationStatus.ACCEPTED, "Experienced in Scikit-Learn and SQL analytics."),
        ]

        for semail, otitle, final_status, note in app_specs:
            sp = students[semail]
            opp = opps[otitle]
            if Application.objects.filter(student=sp, opportunity=opp).exists():
                continue
            match = default_recommendation_engine.score_pair(sp, opp)
            app = Application.objects.create(
                student=sp,
                opportunity=opp,
                status=final_status,
                cover_note=note,
                match_score_snapshot=match.score,
                match_breakdown_snapshot=match.to_snapshot_dict(),
            )
            ApplicationStatusLog.objects.create(
                application=app,
                from_status="",
                to_status=ApplicationStatus.APPLIED,
                changed_by=sp.user,
                note="Application submitted",
            )
            if final_status != ApplicationStatus.APPLIED:
                ApplicationStatusLog.objects.create(
                    application=app,
                    from_status=ApplicationStatus.APPLIED,
                    to_status=final_status,
                    changed_by=opp.company.user,
                    note=f"Pipeline progressed to {app.get_status_display()}",
                )

        # Sample notifications if empty
        if not Notification.objects.exists():
            Notification.objects.create(
                recipient=students["student@nitk.edu"].user,
                actor=companies["FinPulse Technologies"].user,
                category=NotificationCategory.STATUS_UPDATE,
                title="Offer Received: Full-Stack Product Engineer",
                message="FinPulse Technologies extended an offer! Review and respond in your Application Tracker.",
                target_url="/applications/my/",
            )
            Notification.objects.create(
                recipient=companies["CloudScale Systems"].user,
                actor=students["student@nitk.edu"].user,
                category=NotificationCategory.APPLICATION,
                title="Top Match Candidate: Aarav Mehta",
                message="Aarav Mehta (NITK) matched 92% on Backend Platform Intern.",
                target_url=f"/applications/opportunity/{opps['Backend Platform Intern'].pk}/pipeline/",
            )

        self.stdout.write(self.style.SUCCESS("Seed data populated successfully!"))
        self.stdout.write("\nDemo Credentials (password for all accounts: DemoPass123!):")
        self.stdout.write("  Student          : student@nitk.edu")
        self.stdout.write("  Company          : hr@cloudscale.io")
        self.stdout.write("  University Admin : admin@nitk.edu\n")

    def _ensure_user(self, email: str, full_name: str, role: str) -> User:
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "full_name": full_name,
                "role": role,
                "onboarding_completed": True,
            },
        )
        if created:
            user.set_password("DemoPass123!")
            user.save(update_fields=["password"])
        return user
