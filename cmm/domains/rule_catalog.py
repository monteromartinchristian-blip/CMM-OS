"""Initial declarative Domain Rule catalog with conservative structural rules."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from cmm.cognitive.enums import ReasoningRuleResultStatus, ReasoningSeverity
from cmm.cognitive.reasoning_rule_contracts import (
    ReasoningEscalation,
    ReasoningFinding,
    ReasoningGap,
    ReasoningRuleContext,
    ReasoningRuleDefinition,
    ReasoningRuleResult,
    ReasoningRuleTraceEntry,
)
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition, DomainRuleResult

INITIAL_DOMAIN_REASONING_RULE_IDS: tuple[str, ...] = (
    "global.distinguish_fact_inference_hypothesis",
    "global.preserve_provenance",
    "security.respect_sensitivity",
    "security.no_unauthorized_inference",
    "health.symptom_diagnosis_hypothesis",
    "health.medication_temporal_relationship",
    "health.red_flags",
    "health.clinical_source_priority",
    "university.deadline",
    "university.workload",
    "university.exam_attempt",
    "university.academic_dependency",
    "relationships.fact_interpretation",
    "relationships.intent_uncertainty",
    "relationships.pattern_detection",
    "relationships.need_boundary",
    "project.architecture_contract",
    "project.code_documentation_consistency",
    "project.validation_required",
    "project.technical_debt",
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
    result_type = DomainRuleResult if definition.domain_id else ReasoningRuleResult
    return result_type(
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


@dataclass(frozen=True, slots=True)
class _StructuralRule:
    definition: ReasoningRuleDefinition
    behavior: str

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if self.behavior == "distinguish":
            if not context.knowledge_items:
                return _result(self.definition, context, ReasoningRuleResultStatus.NOT_APPLICABLE,
                    code="RULE_NOT_APPLICABLE", message="No knowledge items require epistemic classification.")
            return _result(self.definition, context, ReasoningRuleResultStatus.APPLIED,
                code="EPISTEMIC_KINDS_PRESERVED", message="Existing epistemic kinds were preserved.")

        if self.behavior == "provenance":
            if not context.knowledge_items:
                return _result(self.definition, context, ReasoningRuleResultStatus.NOT_APPLICABLE,
                    code="RULE_NOT_APPLICABLE", message="No knowledge items require provenance inspection.")
            missing = tuple(item for item in context.knowledge_items if not item.evidence and item.resource_id is None)
            findings = tuple(
                ReasoningFinding(
                    code="PROVENANCE_MISSING", message="A knowledge item lacks evidence provenance.",
                    severity=ReasoningSeverity.WARNING, rule_id=self.definition.id,
                    references=(item.id,),
                ) for item in missing
            )
            gaps = tuple(
                ReasoningGap(
                    code="PROVENANCE_GAP", message="Evidence provenance is required before materialization.",
                    severity=ReasoningSeverity.WARNING, rule_id=self.definition.id,
                    references=(item.id,),
                ) for item in missing
            )
            return _result(self.definition, context, ReasoningRuleResultStatus.APPLIED,
                findings=findings, gaps=gaps, code="PROVENANCE_INSPECTED",
                message="Knowledge provenance was inspected structurally.")

        if self.behavior == "sensitivity":
            if context.effective_sensitivity and "sensitivity.read" not in context.effective_permissions:
                finding = ReasoningFinding(
                    code="SENSITIVITY_PERMISSION_MISSING",
                    message="Sensitive reasoning requires an explicit evaluation permission.",
                    severity=ReasoningSeverity.ERROR, rule_id=self.definition.id,
                )
                return _result(self.definition, context, ReasoningRuleResultStatus.BLOCKED,
                    findings=(finding,), code="RULE_BLOCKED", message="Sensitivity permission is missing.")
            return _result(self.definition, context, ReasoningRuleResultStatus.APPLIED,
                code="SENSITIVITY_RESPECTED", message="No sensitivity boundary was weakened.")

        if self.behavior == "permissions":
            requested = context.metadata.get("requested_inference_permissions", ())
            if isinstance(requested, tuple):
                missing = tuple(permission for permission in requested if permission not in context.effective_permissions)
            else:
                missing = ()
            if missing:
                finding = ReasoningFinding(
                    code="UNAUTHORIZED_INFERENCE_BLOCKED",
                    message="An inference requiring unavailable permissions was blocked.",
                    severity=ReasoningSeverity.ERROR, rule_id=self.definition.id,
                    references=missing,
                )
                return _result(self.definition, context, ReasoningRuleResultStatus.BLOCKED,
                    findings=(finding,), code="RULE_BLOCKED", message="Inference permission is missing.")
            return _result(self.definition, context, ReasoningRuleResultStatus.APPLIED,
                code="INFERENCE_PERMISSIONS_RESPECTED", message="No unauthorized inference was requested.")

        if self.behavior == "health_red_flags":
            health = context.metadata.get("health")
            present = isinstance(health, Mapping) and health.get("red_flags_present") is True
            if not present:
                return _result(self.definition, context, ReasoningRuleResultStatus.NOT_APPLICABLE,
                    code="RULE_NOT_APPLICABLE", message="No structured health red-flag signal was supplied.")
            escalation = ReasoningEscalation(
                code="HEALTH_REVIEW_RECOMMENDED",
                message="Structured red-flag input warrants qualified human review.",
                severity=ReasoningSeverity.CRITICAL, rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
            return _result(self.definition, context, ReasoningRuleResultStatus.APPLIED,
                escalation=escalation, code="ESCALATION_RECOMMENDED",
                message="A conservative health escalation was recommended.")

        if self.behavior == "deadline":
            academic = context.metadata.get("university")
            if not isinstance(academic, Mapping) or "deadline" not in academic:
                gap = ReasoningGap(
                    code="DEADLINE_INFORMATION_GAP", message="No structured deadline was supplied.",
                    severity=ReasoningSeverity.WARNING, rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                )
                return _result(self.definition, context, ReasoningRuleResultStatus.APPLIED,
                    gaps=(gap,), code="GAP_RECORDED", message="A deadline information gap was recorded.")
            return _result(self.definition, context, ReasoningRuleResultStatus.APPLIED,
                code="DEADLINE_PRESENT", message="A structured deadline is present.")

        return _result(self.definition, context, ReasoningRuleResultStatus.NOT_APPLICABLE,
            code="RULE_NOT_ACTIVATED", message="The future Domain Pack semantics are not activated in Phase 10.12.")


def _global(rule_id: str, name: str, category: str, priority: int) -> ReasoningRuleDefinition:
    return ReasoningRuleDefinition(
        id=rule_id, name=name, version="1.0.0", scope="global", category=category,
        status="enabled", priority=priority, risk_level="low", deterministic=True,
        description="Conservative structural reasoning rule.", metadata={"phase": "10.12"},
    )


def _domain(
    rule_id: str,
    name: str,
    domain_id: str,
    category: str,
    priority: int,
    *,
    enabled: bool = False,
    permissions: tuple[str, ...] = (),
    risk: str = "medium",
) -> DomainReasoningRuleDefinition:
    return DomainReasoningRuleDefinition(
        id=rule_id, name=name, version="1.0.0", scope="domain", domain_id=domain_id,
        category=category, status="enabled" if enabled else "disabled", priority=priority,
        required_permissions=permissions, risk_level=risk, deterministic=True,
        description="Declarative Phase 10.12 rule; deep semantics belong to its future Domain Pack.",
        metadata={"phase": "10.12", "deep_domain_semantics": "future"},
    )


def build_initial_reasoning_rule_catalog() -> InMemoryReasoningRuleRegistry:
    registry = InMemoryReasoningRuleRegistry()
    entries = (
        (_global("global.distinguish_fact_inference_hypothesis", "DistinguishFactInferenceHypothesis", "epistemic", 1000), "distinguish"),
        (_global("global.preserve_provenance", "PreserveProvenance", "epistemic", 990), "provenance"),
        (_global("security.respect_sensitivity", "RespectSensitivity", "safety", 980), "sensitivity"),
        (_global("security.no_unauthorized_inference", "NoUnauthorizedInference", "safety", 970), "permissions"),
        (_domain("health.symptom_diagnosis_hypothesis", "SymptomDiagnosisHypothesis", "domain:health", "inference", 720), "future"),
        (_domain("health.medication_temporal_relationship", "MedicationTemporalRelationship", "domain:health", "temporality", 710), "future"),
        (_domain("health.red_flags", "HealthRedFlags", "domain:health", "safety", 900, enabled=True, permissions=("knowledge.health.read",), risk="high"), "health_red_flags"),
        (_domain("health.clinical_source_priority", "ClinicalSourcePriority", "domain:health", "epistemic", 700), "future"),
        (_domain("university.deadline", "UniversityDeadline", "domain:university", "temporality", 700, enabled=True), "deadline"),
        (_domain("university.workload", "UniversityWorkload", "domain:university", "inference", 680), "future"),
        (_domain("university.exam_attempt", "UniversityExamAttempt", "domain:university", "consistency", 670), "future"),
        (_domain("university.academic_dependency", "UniversityAcademicDependency", "domain:university", "consistency", 660), "future"),
        (_domain("relationships.fact_interpretation", "RelationshipFactInterpretation", "domain:relationship", "epistemic", 700), "future"),
        (_domain("relationships.intent_uncertainty", "RelationshipIntentUncertainty", "domain:relationship", "inference", 690, enabled=True), "future"),
        (_domain("relationships.pattern_detection", "RelationshipPatternDetection", "domain:relationship", "inference", 680), "future"),
        (_domain("relationships.need_boundary", "RelationshipNeedBoundary", "domain:relationship", "safety", 670), "future"),
        (_domain("project.architecture_contract", "ProjectArchitectureContract", "domain:project", "consistency", 700), "future"),
        (_domain("project.code_documentation_consistency", "ProjectCodeDocumentationConsistency", "domain:project", "consistency", 690), "future"),
        (_domain("project.validation_required", "ProjectValidationRequired", "domain:project", "validation", 680, enabled=True), "future"),
        (_domain("project.technical_debt", "ProjectTechnicalDebt", "domain:project", "inference", 670), "future"),
    )
    for definition, behavior in entries:
        registry.register(_StructuralRule(definition=definition, behavior=behavior))
    return registry


__all__ = ["INITIAL_DOMAIN_REASONING_RULE_IDS", "build_initial_reasoning_rule_catalog"]
