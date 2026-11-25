"""Pluggable, SOLID skill-based recommendation scoring engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable, Protocol, Sequence

from apps.opportunities.models import Opportunity, OpportunitySkill, RequirementType
from apps.profiles.models import StudentProfile
from apps.skills.models import StudentSkill


@dataclass(frozen=True)
class StrategyEvaluation:
    """Output produced by an individual ScoringStrategy."""

    name: str
    weight: float
    ratio: float  # 0.0 to 1.0
    active: bool = True
    details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MatchResult:
    """Transparent match score and skill-gap breakdown for a student-opportunity pair."""

    score: int
    is_eligible: bool
    matched_required: list[str]
    partial_required: list[str]
    missing_required: list[str]
    matched_bonus: list[str]
    eligibility_notes: list[str]
    summary_text: str

    def to_snapshot_dict(self) -> dict:
        """Return JSON-serializable breakdown stored on Application snapshots."""
        return {
            "score": self.score,
            "is_eligible": self.is_eligible,
            "matched_required": self.matched_required,
            "partial_required": self.partial_required,
            "missing_required": self.missing_required,
            "matched_bonus": self.matched_bonus,
            "eligibility_notes": self.eligibility_notes,
            "summary_text": self.summary_text,
        }


class ScoringStrategy(Protocol):
    """Protocol for pluggable recommendation scoring strategies (Open/Closed Principle)."""

    weight: float

    def evaluate(
        self,
        *,
        student: StudentProfile,
        opportunity: Opportunity,
        student_skills_map: dict[int, StudentSkill],
        opp_skills: Sequence[OpportunitySkill],
    ) -> StrategyEvaluation:
        ...


class RequiredSkillStrategy:
    """Score overlap and proficiency fit against REQUIRED opportunity skills."""

    def __init__(self, weight: float = 0.60) -> None:
        self.weight = weight

    def evaluate(
        self,
        *,
        student: StudentProfile,
        opportunity: Opportunity,
        student_skills_map: dict[int, StudentSkill],
        opp_skills: Sequence[OpportunitySkill],
    ) -> StrategyEvaluation:
        required = [s for s in opp_skills if s.requirement_type == RequirementType.REQUIRED]
        matched: list[str] = []
        partial: list[str] = []
        missing: list[str] = []

        if not required:
            return StrategyEvaluation(
                name="required_skills",
                weight=self.weight,
                ratio=1.0,
                active=True,
                details={"matched": matched, "partial": partial, "missing": missing},
            )

        earned = 0.0
        verified_hits = 0
        for req in required:
            entry = student_skills_map.get(req.skill_id)
            if entry is None:
                missing.append(req.skill.name)
            elif entry.proficiency_level >= req.min_proficiency:
                earned += 1.0
                matched.append(req.skill.name)
                if entry.is_verified:
                    verified_hits += 1
            else:
                earned += 0.6
                partial.append(f"{req.skill.name} ({entry.get_proficiency_level_display()})")

        base_ratio = earned / len(required)
        verification_boost = 0.05 * (verified_hits / len(required))
        ratio = min(1.0, base_ratio + verification_boost)

        return StrategyEvaluation(
            name="required_skills",
            weight=self.weight,
            ratio=ratio,
            active=True,
            details={"matched": matched, "partial": partial, "missing": missing},
        )


class BonusSkillStrategy:
    """Score overlap against optional BONUS opportunity skills."""

    def __init__(self, weight: float = 0.20) -> None:
        self.weight = weight

    def evaluate(
        self,
        *,
        student: StudentProfile,
        opportunity: Opportunity,
        student_skills_map: dict[int, StudentSkill],
        opp_skills: Sequence[OpportunitySkill],
    ) -> StrategyEvaluation:
        bonus = [s for s in opp_skills if s.requirement_type == RequirementType.BONUS]
        if not bonus:
            # Inactive when opportunity defines no bonus skills so candidates are not penalized
            return StrategyEvaluation(
                name="bonus_skills",
                weight=self.weight,
                ratio=0.0,
                active=False,
                details={"matched": []},
            )

        matched: list[str] = []
        earned = 0.0
        for item in bonus:
            entry = student_skills_map.get(item.skill_id)
            if entry is not None:
                matched.append(item.skill.name)
                earned += 1.0 if entry.proficiency_level >= item.min_proficiency else 0.7

        return StrategyEvaluation(
            name="bonus_skills",
            weight=self.weight,
            ratio=min(1.0, earned / len(bonus)),
            active=True,
            details={"matched": matched},
        )


class EligibilityFitStrategy:
    """Score CGPA cutoff compliance and graduation year eligibility."""

    def __init__(self, weight: float = 0.20) -> None:
        self.weight = weight

    def evaluate(
        self,
        *,
        student: StudentProfile,
        opportunity: Opportunity,
        student_skills_map: dict[int, StudentSkill],
        opp_skills: Sequence[OpportunitySkill],
    ) -> StrategyEvaluation:
        notes: list[str] = []
        is_eligible = True
        cgpa_score = 0.7

        min_cgpa = opportunity.min_cgpa or Decimal("0.00")
        if student.cgpa < min_cgpa:
            is_eligible = False
            notes.append(f"CGPA {student.cgpa} below minimum {min_cgpa}")
            diff = float(min_cgpa - student.cgpa)
            cgpa_score = 0.35 if diff <= 0.5 else 0.0
        elif min_cgpa > 0:
            notes.append(f"Meets CGPA cutoff ({min_cgpa}+)")

        grad_score = 0.3
        eligible_years = opportunity.eligible_grad_years or []
        if eligible_years and student.graduation_year not in eligible_years:
            is_eligible = False
            grad_score = 0.0
            notes.append(f"Class of {student.graduation_year} outside target batch {eligible_years}")

        return StrategyEvaluation(
            name="eligibility_fit",
            weight=self.weight,
            ratio=min(1.0, cgpa_score + grad_score),
            active=True,
            details={"is_eligible": is_eligible, "notes": notes},
        )


class RecommendationEngine:
    """Compute transparent 0-100% match scores by aggregating pluggable strategies."""

    def __init__(self, strategies: Sequence[ScoringStrategy] | None = None) -> None:
        self.strategies: Sequence[ScoringStrategy] = strategies or (
            RequiredSkillStrategy(weight=0.60),
            BonusSkillStrategy(weight=0.20),
            EligibilityFitStrategy(weight=0.20),
        )

    @staticmethod
    def _build_student_skill_map(student: StudentProfile) -> dict[int, StudentSkill]:
        return {entry.skill_id: entry for entry in student.student_skills.all()}

    @staticmethod
    def _build_summary(
        *,
        total_required: int,
        matched_count: int,
        partial_count: int,
        missing_required: list[str],
        is_eligible: bool,
    ) -> str:
        if total_required == 0:
            base = "No mandatory skill prerequisites"
        else:
            covered = matched_count + partial_count
            base = f"Matches {covered}/{total_required} required skills"
        if missing_required:
            missing_preview = ", ".join(missing_required[:3])
            if len(missing_required) > 3:
                missing_preview += f" +{len(missing_required) - 3}"
            base = f"{base} • Missing: {missing_preview}"
        if not is_eligible:
            base = f"{base} • Eligibility gap"
        return base

    def score_pair(
        self,
        student: StudentProfile,
        opportunity: Opportunity,
        *,
        student_skills_map: dict[int, StudentSkill] | None = None,
    ) -> MatchResult:
        """Compute MatchResult for a single student and opportunity."""
        skill_map = (
            student_skills_map
            if student_skills_map is not None
            else self._build_student_skill_map(student)
        )
        opp_skills = list(opportunity.opportunity_skills.all())

        evaluations = [
            strategy.evaluate(
                student=student,
                opportunity=opportunity,
                student_skills_map=skill_map,
                opp_skills=opp_skills,
            )
            for strategy in self.strategies
        ]

        active_evals = [e for e in evaluations if e.active]
        total_weight = sum(e.weight for e in active_evals) or 1.0
        weighted_ratio = sum(e.ratio * e.weight for e in active_evals) / total_weight
        score = max(0, min(100, round(weighted_ratio * 100)))

        req_details = next((e.details for e in evaluations if e.name == "required_skills"), {})
        bonus_details = next((e.details for e in evaluations if e.name == "bonus_skills"), {})
        elig_details = next((e.details for e in evaluations if e.name == "eligibility_fit"), {})

        matched_req = req_details.get("matched", [])
        partial_req = req_details.get("partial", [])
        missing_req = req_details.get("missing", [])
        matched_bonus = bonus_details.get("matched", [])
        is_eligible = elig_details.get("is_eligible", True)
        eligibility_notes = elig_details.get("notes", [])

        total_required = len(matched_req) + len(partial_req) + len(missing_req)
        summary_text = self._build_summary(
            total_required=total_required,
            matched_count=len(matched_req),
            partial_count=len(partial_req),
            missing_required=missing_req,
            is_eligible=is_eligible,
        )

        return MatchResult(
            score=score,
            is_eligible=is_eligible,
            matched_required=matched_req,
            partial_required=partial_req,
            missing_required=missing_req,
            matched_bonus=matched_bonus,
            eligibility_notes=eligibility_notes,
            summary_text=summary_text,
        )

    def rank_opportunities_for_student(
        self,
        student: StudentProfile,
        opportunities: Iterable[Opportunity],
    ) -> list[tuple[Opportunity, MatchResult]]:
        """Score and rank opportunities descending by Match Score."""
        skill_map = self._build_student_skill_map(student)
        ranked = [
            (opp, self.score_pair(student, opp, student_skills_map=skill_map))
            for opp in opportunities
        ]
        ranked.sort(key=lambda pair: (pair[1].is_eligible, pair[1].score, pair[0].is_featured), reverse=True)
        return ranked

    def rank_students_for_opportunity(
        self,
        students: Iterable[StudentProfile],
        opportunity: Opportunity,
    ) -> list[tuple[StudentProfile, MatchResult]]:
        """Score and rank candidate students descending by Match Score."""
        ranked = [(student, self.score_pair(student, opportunity)) for student in students]
        ranked.sort(key=lambda pair: (pair[1].is_eligible, pair[1].score), reverse=True)
        return ranked


default_recommendation_engine = RecommendationEngine()
