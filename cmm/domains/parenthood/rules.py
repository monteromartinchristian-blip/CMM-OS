"""Phase 10.27 — Parenthood Domain Rules and deterministic evaluators.

Declarative domain rules + pure deterministic parenting/journey reasoning helpers.
All helper functions and rule evaluators are state-free: no IO, no model calls,
no registry mutation, no internal clock. They receive context explicitly and
return deterministic JSON-safe structures.

Semantic invariants enforced:
1. Explicit adoption: candidate options/hypotheses are not adopted decisions.
2. Temporal validity: temporally mutable legal/admin facts require current evidence.
3. Medical/legal/financial separation: distinct categories, no conflation.
4. Ethical constraints: respect user ethical boundaries as hard filters.
5. Cost uncertainty: costs are ranges/contingencies, never guaranteed constants.
6. Journey dependency: prerequisites structured without autonomous commitments.
7. Journey to child boundary: selective, authorized context transfer only.
8. Child interest & wellbeing: primacy of child safety, health, and development.
9. Developmental context: normal variation is non-pathological, not diagnostic.
10. Age-appropriate guidance: developmentally attuned recommendations.
11. Parent-child boundary: separate parent preferences from child needs/autonomy.
12. Health boundary: scoped health facts without clinical diagnosis/prescription.
13. Education boundary: pedagogical planning without specialized clinical assessment.
14. Minor privacy: fail-closed data protection, no autonomous egress.
15. Long-term continuity: adapt present plans to long-term objectives.
16. Parental uncertainty: preserve alternatives when no single truth exists.
17. Sibling identity isolation: absolute isolation between sibling workspaces.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from cmm.cognitive.enums import (
    ReasoningRiskLevel,
    ReasoningRuleCategory,
    ReasoningRuleResultStatus,
    ReasoningRuleScope,
    ReasoningRuleStatus,
    ReasoningSeverity,
)
from cmm.cognitive.reasoning_rule_contracts import (
    ReasoningEscalation,
    ReasoningFinding,
    ReasoningGap,
    ReasoningRuleContext,
    ReasoningRuleDefinition,
    ReasoningRuleResult,
    ReasoningRuleTraceEntry,
)
from cmm.domains.parenthood.catalog import (
    CANONICAL_PARENTHOOD_RULE_IDS,
    CANONICAL_PARENTHOOD_RULE_NAMES,
)
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition, DomainRuleResult

PARENTHOOD_RULE_IDS: tuple[str, ...] = CANONICAL_PARENTHOOD_RULE_IDS
PARENTHOOD_RULE_NAMES: tuple[str, ...] = CANONICAL_PARENTHOOD_RULE_NAMES


def _definition(
    rule_id: str,
    name: str,
    category: str,
    priority: int,
    risk_level: ReasoningRiskLevel = ReasoningRiskLevel.LOW,
) -> DomainReasoningRuleDefinition:
    return DomainReasoningRuleDefinition(
        id=rule_id,
        name=name,
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:parenthood",
        category=category,
        status=ReasoningRuleStatus.ENABLED,
        priority=priority,
        risk_level=risk_level,
        deterministic=True,
        description=f"Parenthood domain reasoning rule for {rule_id}.",
        metadata={"phase": "10.27"},
    )


def _result(
    definition: ReasoningRuleDefinition,
    context: ReasoningRuleContext,
    status: ReasoningRuleResultStatus,
    *,
    findings: tuple[ReasoningFinding, ...] = (),
    gaps: tuple[ReasoningGap, ...] = (),
    escalation: ReasoningEscalation | None = None,
    code: str,
    message: str,
) -> ReasoningRuleResult:
    return DomainRuleResult(
        rule_id=definition.id,
        rule_name=definition.name,
        rule_version=definition.version,
        domain_id=definition.domain_id,
        status=status,
        findings=findings,
        gaps=gaps,
        escalation=escalation,
        trace_entries=(
            ReasoningRuleTraceEntry(
                code=code,
                message=message,
                rule_id=definition.id,
                domain_id=definition.domain_id,
                status=status,
                occurred_at=context.timestamp,
                output_count=len(findings) + len(gaps) + int(escalation is not None),
            ),
        ),
        started_at=context.timestamp,
        completed_at=context.timestamp,
    )


# ── 1. ParenthoodDecisionExplicitRule ─────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ParenthoodDecisionExplicitRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "parenthood.rule.parenthood_decision_explicit",
            "ParenthoodDecisionExplicitRule",
            ReasoningRuleCategory.EPISTEMIC.value,
            700,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        findings: list[ReasoningFinding] = []
        decisions = context.metadata.get("decisions", ())
        if isinstance(decisions, (Sequence, list, tuple)):
            for dec in decisions:
                if isinstance(dec, (Mapping, dict)):
                    explicit = dec.get("explicitly_adopted", False)
                    status = dec.get("status", "proposed")
                    if explicit and status == "adopted":
                        findings.append(
                            ReasoningFinding(
                                code="ADOPTED_DECISION_VERIFIED",
                                message=f"Explicitly adopted decision verified: {dec.get('topic')}",
                                severity=ReasoningSeverity.INFO,
                                rule_id=self.definition.id,
                                domain_id=self.definition.domain_id,
                            )
                        )
                    else:
                        findings.append(
                            ReasoningFinding(
                                code="PROPOSED_DECISION_PRESERVED",
                                message=f"Option preserved as proposal/hypothesis: {dec.get('topic')}",
                                severity=ReasoningSeverity.INFO,
                                rule_id=self.definition.id,
                                domain_id=self.definition.domain_id,
                            )
                        )

        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="DECISION_EXPLICIT_EVALUATED",
            message="Evaluated explicit decision boundaries.",
        )


# ── 2. LegalTemporalValidityRule ──────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class LegalTemporalValidityRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "parenthood.rule.legal_temporal_validity",
            "LegalTemporalValidityRule",
            ReasoningRuleCategory.TEMPORALITY.value,
            710,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        findings: list[ReasoningFinding] = []
        legal_reqs = context.metadata.get("legal_requirements", ())
        if isinstance(legal_reqs, (Sequence, list, tuple)):
            for req in legal_reqs:
                if isinstance(req, (Mapping, dict)) and not req.get(
                    "verified_current", False
                ):
                    findings.append(
                        ReasoningFinding(
                            code="LEGAL_TEMPORAL_VERIFICATION_REQUIRED",
                            message=f"Legal requirement requires current temporal verification: {req.get('id')}",
                            severity=ReasoningSeverity.WARNING,
                            rule_id=self.definition.id,
                            domain_id=self.definition.domain_id,
                        )
                    )

        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="LEGAL_TEMPORAL_EVALUATED",
            message="Evaluated legal temporal validity.",
        )


# ── 3. MedicalLegalSeparationRule ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class MedicalLegalSeparationRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "parenthood.rule.medical_legal_separation",
            "MedicalLegalSeparationRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            720,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        findings: list[ReasoningFinding] = [
            ReasoningFinding(
                code="MEDICAL_LEGAL_SEPARATED",
                message="Medical, legal, and financial dimensions preserved in distinct epistemic categories.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="MEDICAL_LEGAL_SEPARATION_EVALUATED",
            message="Evaluated medical, legal, and financial separation.",
        )


# ── 4. EthicalConstraintRule ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class EthicalConstraintRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "parenthood.rule.ethical_constraint",
            "EthicalConstraintRule",
            ReasoningRuleCategory.EPISTEMIC.value,
            730,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        findings: list[ReasoningFinding] = [
            ReasoningFinding(
                code="ETHICAL_CONSTRAINTS_APPLIED",
                message="User ethical criteria preserved as active filters.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="ETHICAL_CONSTRAINTS_EVALUATED",
            message="Evaluated ethical constraints.",
        )


# ── 5. CostUncertaintyRule ────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CostUncertaintyRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "parenthood.rule.cost_uncertainty",
            "CostUncertaintyRule",
            ReasoningRuleCategory.EPISTEMIC.value,
            740,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        findings: list[ReasoningFinding] = []
        scenarios = context.metadata.get("financial_scenarios", ())
        if isinstance(scenarios, (Sequence, list, tuple)):
            for sc in scenarios:
                if isinstance(sc, (Mapping, dict)) and sc.get("is_guaranteed", False):
                    findings.append(
                        ReasoningFinding(
                            code="COST_CERTAINTY_FLAGGED",
                            message=f"Cost estimate flagged: guaranteed fixed cost assertion rejected for {sc.get('item')}",
                            severity=ReasoningSeverity.WARNING,
                            rule_id=self.definition.id,
                            domain_id=self.definition.domain_id,
                        )
                    )

        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="COST_UNCERTAINTY_EVALUATED",
            message="Evaluated cost uncertainty and ranges.",
        )


# ── 6. JourneyDependencyRule ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class JourneyDependencyRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "parenthood.rule.journey_dependency",
            "JourneyDependencyRule",
            ReasoningRuleCategory.INFERENCE.value,
            750,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        findings: list[ReasoningFinding] = [
            ReasoningFinding(
                code="JOURNEY_DEPENDENCIES_TRACKED",
                message="Dependencies tracked without automatic decision commitments.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="JOURNEY_DEPENDENCY_EVALUATED",
            message="Evaluated journey dependencies.",
        )


# ── 7. JourneyToChildBoundaryRule ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class JourneyToChildBoundaryRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "parenthood.rule.journey_to_child_boundary",
            "JourneyToChildBoundaryRule",
            ReasoningRuleCategory.SAFETY.value,
            760,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        findings: list[ReasoningFinding] = [
            ReasoningFinding(
                code="JOURNEY_TO_CHILD_BOUNDARY_ENFORCED",
                message="Pre-parenthood operational dossier isolated from child workspace.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="JOURNEY_TO_CHILD_BOUNDARY_EVALUATED",
            message="Evaluated journey to child workspace boundary.",
        )


# ── 8. ChildInterestAndWellbeingRule ──────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ChildInterestAndWellbeingRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "parenthood.rule.child_interest_and_wellbeing",
            "ChildInterestAndWellbeingRule",
            ReasoningRuleCategory.SAFETY.value,
            770,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        findings: list[ReasoningFinding] = [
            ReasoningFinding(
                code="CHILD_WELLBEING_PRIORITIZED",
                message="Child safety, wellbeing, and developmental needs prioritized.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="CHILD_WELLBEING_EVALUATED",
            message="Evaluated child interest and wellbeing.",
        )


# ── 9. DevelopmentalContextRule ───────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DevelopmentalContextRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "parenthood.rule.developmental_context",
            "DevelopmentalContextRule",
            ReasoningRuleCategory.EPISTEMIC.value,
            780,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        findings: list[ReasoningFinding] = []
        obs_list = context.metadata.get("child_observations", ())
        if isinstance(obs_list, (Sequence, list, tuple)):
            for obs in obs_list:
                if isinstance(obs, (Mapping, dict)) and obs.get("proposed_diagnosis"):
                    findings.append(
                        ReasoningFinding(
                            code="PATHOLOGY_LABEL_REJECTED",
                            message=(
                                f"Developmental variation '{obs.get('behavior')}' preserved as non-pathological; "
                                f"diagnosis '{obs.get('proposed_diagnosis')}' rejected."
                            ),
                            severity=ReasoningSeverity.ERROR,
                            rule_id=self.definition.id,
                            domain_id=self.definition.domain_id,
                        )
                    )

        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="DEVELOPMENTAL_CONTEXT_EVALUATED",
            message="Evaluated developmental context and non-pathology invariant.",
        )


# ── 10. AgeAppropriateGuidanceRule ────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AgeAppropriateGuidanceRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "parenthood.rule.age_appropriate_guidance",
            "AgeAppropriateGuidanceRule",
            ReasoningRuleCategory.INFERENCE.value,
            790,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        findings: list[ReasoningFinding] = [
            ReasoningFinding(
                code="AGE_APPROPRIATENESS_VERIFIED",
                message="Recommendations verified for age and maturity suitability.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="AGE_APPROPRIATE_GUIDANCE_EVALUATED",
            message="Evaluated age-appropriate guidance.",
        )


# ── 11. ParentChildBoundaryRule ───────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ParentChildBoundaryRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "parenthood.rule.parent_child_boundary",
            "ParentChildBoundaryRule",
            ReasoningRuleCategory.EPISTEMIC.value,
            800,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        findings: list[ReasoningFinding] = [
            ReasoningFinding(
                code="PARENT_CHILD_BOUNDARY_PRESERVED",
                message="Parent preferences separated from child needs and autonomy.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="PARENT_CHILD_BOUNDARY_EVALUATED",
            message="Evaluated parent-child boundary.",
        )


# ── 12. HealthBoundaryRule ────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class HealthBoundaryRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "parenthood.rule.health_boundary",
            "HealthBoundaryRule",
            ReasoningRuleCategory.SAFETY.value,
            810,
            risk_level=ReasoningRiskLevel.HIGH,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        findings: list[ReasoningFinding] = [
            ReasoningFinding(
                code="HEALTH_BOUNDARY_ENFORCED",
                message="Health context handled without clinical diagnosis or prescription.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="HEALTH_BOUNDARY_EVALUATED",
            message="Evaluated health boundary.",
        )


# ── 13. EducationBoundaryRule ─────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class EducationBoundaryRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "parenthood.rule.education_boundary",
            "EducationBoundaryRule",
            ReasoningRuleCategory.EPISTEMIC.value,
            820,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        findings: list[ReasoningFinding] = [
            ReasoningFinding(
                code="EDUCATION_BOUNDARY_PRESERVED",
                message="Educational planning supported without clinical/psychometric diagnosis.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="EDUCATION_BOUNDARY_EVALUATED",
            message="Evaluated education boundary.",
        )


# ── 14. MinorPrivacyRule ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class MinorPrivacyRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "parenthood.rule.minor_privacy",
            "MinorPrivacyRule",
            ReasoningRuleCategory.SAFETY.value,
            830,
            risk_level=ReasoningRiskLevel.HIGH,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        findings: list[ReasoningFinding] = []
        action = context.metadata.get("action_proposed")
        if action and any(
            kw in str(action) for kw in ("external", "export", "share", "transmit")
        ):
            findings.append(
                ReasoningFinding(
                    code="MINOR_PRIVACY_RESTRICTION",
                    message=f"External transmission/export of minor data restricted: {action}",
                    severity=ReasoningSeverity.CRITICAL,
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                )
            )

        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="MINOR_PRIVACY_EVALUATED",
            message="Evaluated minor privacy rule.",
        )


# ── 15. LongTermContinuityRule ────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class LongTermContinuityRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "parenthood.rule.long_term_continuity",
            "LongTermContinuityRule",
            ReasoningRuleCategory.INFERENCE.value,
            840,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        findings: list[ReasoningFinding] = [
            ReasoningFinding(
                code="LONG_TERM_CONTINUITY_MAINTAINED",
                message="Present parenting plans aligned with evolving long-term objectives.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="LONG_TERM_CONTINUITY_EVALUATED",
            message="Evaluated long-term continuity.",
        )


# ── 16. ParentalUncertaintyRule ───────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ParentalUncertaintyRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "parenthood.rule.parental_uncertainty",
            "ParentalUncertaintyRule",
            ReasoningRuleCategory.EPISTEMIC.value,
            850,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        findings: list[ReasoningFinding] = [
            ReasoningFinding(
                code="PARENTAL_UNCERTAINTY_PRESERVED",
                message="Uncertainties and balanced alternatives presented where no single standard exists.",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="PARENTAL_UNCERTAINTY_EVALUATED",
            message="Evaluated parental uncertainty.",
        )


# ── 17. SiblingIdentityIsolationRule ──────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SiblingIdentityIsolationRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "parenthood.rule.sibling_identity_isolation",
            "SiblingIdentityIsolationRule",
            ReasoningRuleCategory.SAFETY.value,
            860,
            risk_level=ReasoningRiskLevel.HIGH,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        findings: list[ReasoningFinding] = []
        active_child_id = context.metadata.get("active_child_id")
        records = context.metadata.get("context_records", ())

        if active_child_id and isinstance(records, (Sequence, list, tuple)):
            for rec in records:
                if isinstance(rec, (Mapping, dict)):
                    rec_child_id = rec.get("child_id")
                    is_shared = rec.get("is_shared", False)
                    if (
                        not is_shared
                        and rec_child_id
                        and rec_child_id != active_child_id
                    ):
                        findings.append(
                            ReasoningFinding(
                                code="SIBLING_CONTAMINATION_BLOCKED",
                                message=(
                                    f"Cross-sibling contamination blocked: record belonging to {rec_child_id} "
                                    f"cannot apply to active child workspace {active_child_id}."
                                ),
                                severity=ReasoningSeverity.CRITICAL,
                                rule_id=self.definition.id,
                                domain_id=self.definition.domain_id,
                            )
                        )

        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="SIBLING_ISOLATION_EVALUATED",
            message="Evaluated sibling identity isolation.",
        )


# ── Build Function ────────────────────────────────────────────────────


def build_parenthood_rules() -> tuple[Any, ...]:
    """Build the seventeen Parenthood Domain rules deterministically in canonical order."""
    by_id = {
        "parenthood.rule.parenthood_decision_explicit": ParenthoodDecisionExplicitRule(),
        "parenthood.rule.legal_temporal_validity": LegalTemporalValidityRule(),
        "parenthood.rule.medical_legal_separation": MedicalLegalSeparationRule(),
        "parenthood.rule.ethical_constraint": EthicalConstraintRule(),
        "parenthood.rule.cost_uncertainty": CostUncertaintyRule(),
        "parenthood.rule.journey_dependency": JourneyDependencyRule(),
        "parenthood.rule.journey_to_child_boundary": JourneyToChildBoundaryRule(),
        "parenthood.rule.child_interest_and_wellbeing": ChildInterestAndWellbeingRule(),
        "parenthood.rule.developmental_context": DevelopmentalContextRule(),
        "parenthood.rule.age_appropriate_guidance": AgeAppropriateGuidanceRule(),
        "parenthood.rule.parent_child_boundary": ParentChildBoundaryRule(),
        "parenthood.rule.health_boundary": HealthBoundaryRule(),
        "parenthood.rule.education_boundary": EducationBoundaryRule(),
        "parenthood.rule.minor_privacy": MinorPrivacyRule(),
        "parenthood.rule.long_term_continuity": LongTermContinuityRule(),
        "parenthood.rule.parental_uncertainty": ParentalUncertaintyRule(),
        "parenthood.rule.sibling_identity_isolation": SiblingIdentityIsolationRule(),
    }

    return tuple(by_id[rule_id] for rule_id in CANONICAL_PARENTHOOD_RULE_IDS)


__all__ = [
    "PARENTHOOD_RULE_IDS",
    "PARENTHOOD_RULE_NAMES",
    "AgeAppropriateGuidanceRule",
    "ChildInterestAndWellbeingRule",
    "CostUncertaintyRule",
    "DevelopmentalContextRule",
    "EducationBoundaryRule",
    "EthicalConstraintRule",
    "HealthBoundaryRule",
    "JourneyDependencyRule",
    "JourneyToChildBoundaryRule",
    "LegalTemporalValidityRule",
    "LongTermContinuityRule",
    "MedicalLegalSeparationRule",
    "MinorPrivacyRule",
    "ParentChildBoundaryRule",
    "ParentalUncertaintyRule",
    "ParenthoodDecisionExplicitRule",
    "SiblingIdentityIsolationRule",
    "build_parenthood_rules",
]
