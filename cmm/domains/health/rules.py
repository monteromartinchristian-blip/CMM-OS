"""Phase 10.20 — Health Domain Rules and deterministic clinical helpers.

A declarative domain + pure deterministic clinical helpers.  The helper
functions are state-free: no IO, no model calls, no registry mutation, no
internal clock.  They receive dates/context explicitly and return
deterministic structures.

The eight reasoning rules are ``@dataclass(frozen=True, slots=True)``
definitions exposing ``definition`` and ``evaluate(context)``, exactly like
the General Domain rules, so they compose with the existing cognitive layer.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
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
from cmm.domains.health.catalog import CANONICAL_HEALTH_RULE_IDS
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition, DomainRuleResult

HEALTH_RULE_IDS: tuple[str, ...] = CANONICAL_HEALTH_RULE_IDS

# ── Closed epistemic categories (spec §6) ─────────────────────────────────────

EPISTEMIC_CATEGORY_DOCUMENTED = "documented_information"
EPISTEMIC_CATEGORY_OBSERVATION = "clinical_observation"
EPISTEMIC_CATEGORY_REPORTED_SYMPTOM = "reported_symptom"
EPISTEMIC_CATEGORY_DOCUMENTED_DIAGNOSIS = "documented_diagnosis"
EPISTEMIC_CATEGORY_PROVISIONAL = "provisional_diagnosis"
EPISTEMIC_CATEGORY_HYPOTHESIS = "system_hypothesis"
EPISTEMIC_CATEGORY_POSSIBILITY = "user_possibility"
EPISTEMIC_CATEGORY_CONTRADICTION = "contradiction"
EPISTEMIC_CATEGORY_MISSING = "missing_information"
EPISTEMIC_CATEGORY_RED_FLAG = "red_flag"
EPISTEMIC_CATEGORY_ESCALATION = "escalation"

# ── Closed medication temporal relationship kinds (spec §8.2) ────────────────

MEDICATION_RELATION_START = "start"
MEDICATION_RELATION_DOSE_CHANGE = "dose_change"
MEDICATION_RELATION_SYMPTOM_ONSET = "symptom_onset"
MEDICATION_RELATION_WITHDRAWAL = "withdrawal"
MEDICATION_RELATION_REEXPOSURE = "reexposure"
MEDICATION_RELATION_EVOLUTION = "evolution"

# ── Escalation levels (spec §8.3) ────────────────────────────────────────────

ESCALATION_MONITORING = "monitoring"
ESCALATION_PROFESSIONAL_REVIEW = "professional_review"
ESCALATION_PRIORITY_REVIEW = "priority_review"
ESCALATION_URGENT_ATTENTION = "urgent_attention"

# ── Clinical source priority (spec §8.4) ─────────────────────────────────────

_CLINICAL_SOURCE_RANK: dict[str, int] = {
    "medical_report": 1,
    "test_result": 2,
    "prescription": 3,
    "identified_professional": 4,
    "primary_medical_source": 5,
    "user_statement": 6,
    "inference": 7,
}


# ═══════════════════════════════════════════════════════════════════════════════
# Pure deterministic clinical helpers
# ═══════════════════════════════════════════════════════════════════════════════


def classify_clinical_statement(
    *,
    provenance: str | None = None,
    is_documented: bool = False,
    is_clinical_observation: bool = False,
    is_user_reported: bool = False,
    is_diagnosis: bool = False,
    is_provisional: bool = False,
    is_system_hypothesis: bool = False,
    is_user_possibility: bool = False,
) -> str:
    """Classify a clinical statement into a closed epistemic category.

    Deterministic precedence, documented before inference:
    documented -> observation -> diagnosis -> provisional -> hypothesis ->
    user possibility.  A system-flagged ``is_diagnosis`` with a provisional
    flag stays provisional; it is never promoted to ``documented_diagnosis``.
    """
    if is_user_possibility and not (is_documented or is_clinical_observation):
        return EPISTEMIC_CATEGORY_POSSIBILITY
    if is_system_hypothesis and not (is_documented or is_clinical_observation):
        return EPISTEMIC_CATEGORY_HYPOTHESIS
    if is_documentary := (bool(provenance) or is_documented):
        if is_diagnosis:
            if is_provisional:
                return EPISTEMIC_CATEGORY_PROVISIONAL
            return EPISTEMIC_CATEGORY_DOCUMENTED_DIAGNOSIS
        return EPISTEMIC_CATEGORY_DOCUMENTED
    if is_clinical_observation:
        return EPISTEMIC_CATEGORY_OBSERVATION
    if is_diagnosis and is_provisional:
        return EPISTEMIC_CATEGORY_PROVISIONAL
    if is_user_reported:
        return EPISTEMIC_CATEGORY_REPORTED_SYMPTOM
    _ = is_documentary
    return EPISTEMIC_CATEGORY_HYPOTHESIS


def build_medication_temporal_relation(
    *,
    medication: str,
    event_kind: str,
    dose_before: str | None = None,
    dose_after: str | None = None,
    symptom: str | None = None,
    onset_date: str | None = None,
    withdrawal_date: str | None = None,
    reexposure_date: str | None = None,
) -> dict:
    """Build a deterministic medication temporal relation record.

    Hard invariant: the record always labels the observation as a
    ``temporal_association`` and never asserts causation.
    """
    return {
        "medication": medication,
        "event_kind": event_kind,
        "temporal_association": True,
        "causation": False,
        "dose_before": dose_before,
        "dose_after": dose_after,
        "symptom": symptom,
        "onset_date": onset_date,
        "withdrawal_date": withdrawal_date,
        "reexposure_date": reexposure_date,
    }


def classify_escalation_level(*, symptom_severity: int = 0, is_red_flag: bool = False) -> str:
    """Classify an escalation level from deterministic inputs (0-10 severity)."""
    if is_red_flag or symptom_severity >= 9:
        return ESCALATION_URGENT_ATTENTION
    if symptom_severity >= 7:
        return ESCALATION_PRIORITY_REVIEW
    if symptom_severity >= 4:
        return ESCALATION_PROFESSIONAL_REVIEW
    return ESCALATION_MONITORING


def clinical_source_rank(source_type: str) -> int:
    """Return the conceptual priority rank for a clinical source type.

    Lower is more authoritative.  Unknown source types rank last (least
    authoritative) so unreliable sources can never outrank documented ones.
    """
    return _CLINICAL_SOURCE_RANK.get(source_type, 8)


def evaluate_clinical_temporality(
    *,
    state: str,
    active: bool = False,
    withdrawn: bool = False,
    superseded: bool = False,
) -> str:
    """Evaluate a closed temporal validity classification for clinical data.

    Returns one of: ``current``, ``historical``, ``pending``, ``expired``,
    ``superseded``, ``future``, ``unknown``.
    """
    if state == "unknown":
        return "unknown"
    if state == "pending":
        return "pending"
    if state == "future":
        return "future"
    if superseded:
        return "superseded"
    if withdrawn:
        return "historical"
    if active:
        return "current"
    if state == "expired":
        return "expired"
    return "historical"


@dataclass(frozen=True, slots=True)
class MedicationConflict:
    """A deterministic medication-conflict record; never a resolution decision."""

    code: str
    message: str
    medication_ids: tuple[str, ...]


def detect_medication_conflicts(records: list | tuple) -> tuple[MedicationConflict, ...]:
    """Detect structured medication inconsistencies without deciding correctness.

    Detecting a conflict is not equivalent to determining which record is
    correct (spec §8.6).
    """
    conflicts: list[MedicationConflict] = []
    by_medication: dict[str, list] = {}
    for record in records:
        if not isinstance(record, Mapping):
            continue
        med = record.get("medication_id")
        if med:
            by_medication.setdefault(med, []).append(record)

    for med, entries in by_medication.items():
        active = [r for r in entries if r.get("active")]
        withdrawn = [r for r in entries if r.get("withdrawn")]
        if active and withdrawn:
            conflicts.append(
                MedicationConflict(
                    code="MEDICATION_SIMULTANEOUS_ACTIVE_WITHDRAWN",
                    message="Medication is simultaneously active and withdrawn.",
                    medication_ids=(med,),
                )
            )
        if len({r.get("dose") for r in entries}) > 1:
            conflicts.append(
                MedicationConflict(
                    code="INCOMPATIBLE_DOSE_RECORDS",
                    message="Multiple distinct doses recorded for the medication.",
                    medication_ids=(med,),
                )
            )
        if len(entries) > 1 and any(r.get("duplicate") for r in entries):
            conflicts.append(
                MedicationConflict(
                    code="DUPLICATE_MEDICATION",
                    message="Duplicate medication record detected.",
                    medication_ids=(med,),
                )
            )
    return tuple(conflicts)


def validate_diagnostic_claim(
    *,
    evidence: bool = False,
    documented: bool = False,
    confirmed: bool = False,
    provisional: bool = False,
) -> dict:
    """Validate whether a diagnostic claim may be considered definitive.

    Hard invariant: being documented (present in a source) or evidenced
    (supported by material) does NOT confirm a diagnosis.  A claim is
    definitive only when an explicit ``confirmed`` status is present and the
    claim is not provisional.  Confirmation is never derived from evidence
    presence, source existence, or documentary provenance.  Anything less
    must remain provisional/hypothesis and never be presented as definitive.
    """
    is_definitive = bool(confirmed) and not provisional
    supported_category = classify_clinical_statement(
        provenance="documented" if documented else None,
        is_documented=documented,
        is_diagnosis=True,
        is_provisional=provisional or not confirmed,
        is_system_hypothesis=(not documented and not confirmed),
    )
    return {
        "is_definitive": is_definitive,
        "may_present_as_definitive": is_definitive,
        "supported_category": supported_category,
        "reason": (
            "Explicit confirmation establishes a definitive diagnostic claim."
            if is_definitive
            else (
                "Diagnostic claim lacks explicit confirmation; "
                "keep provisional."
            )
        ),
    }


def evaluate_professional_escalation(
    *,
    risk: bool = False,
    significant_deterioration: bool = False,
    insufficient_exploration: bool = False,
    missing_important_tests: bool = False,
    unresolved_contradiction: bool = False,
    request_clinical_decision: bool = False,
    unresolvable_uncertainty: bool = False,
) -> dict:
    """Deterministically decide whether professional escalation is required."""
    should_escalate = any(
        (
            risk,
            significant_deterioration,
            insufficient_exploration,
            missing_important_tests,
            unresolved_contradiction,
            request_clinical_decision,
            unresolvable_uncertainty,
        )
    )
    return {
        "escalate": should_escalate,
        "reason": "Professional escalation required."
        if should_escalate
        else "No escalation required on the supplied factors.",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Reasoning rule scaffolding
# ═══════════════════════════════════════════════════════════════════════════════


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
        domain_id="domain:health",
        category=category,
        status=ReasoningRuleStatus.ENABLED,
        priority=priority,
        risk_level=risk_level,
        deterministic=True,
        description=f"Conservative clinical rule for {rule_id}.",
        metadata={"phase": "10.20"},
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


def _mapping(metadata: Mapping, key: str) -> Mapping | None:
    value = metadata.get(key)
    return value if isinstance(value, Mapping) else None


def _seq(metadata: Mapping, key: str) -> tuple | None:
    value = metadata.get(key)
    return value if isinstance(value, (list, tuple)) else None


# ═══════════════════════════════════════════════════════════════════════════════
# DistinguishSymptomDiagnosisHypothesis
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class HealthSymptomDiagnosisHypothesisRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        statements = _seq(context.metadata, "clinical_statements")
        if not statements:
            return _result(
                self.definition, context, ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No clinical statements supplied.",
            )
        findings: list[ReasoningFinding] = []
        for statement in statements:
            if not isinstance(statement, Mapping):
                continue
            statement_id = statement.get("id", "unknown")
            category = classify_clinical_statement(
                provenance=statement.get("provenance"),
                is_documented=bool(statement.get("documented")),
                is_clinical_observation=bool(statement.get("clinical_observation")),
                is_user_reported=bool(statement.get("user_reported")),
                is_diagnosis=bool(statement.get("diagnosis")),
                is_provisional=bool(statement.get("provisional")),
                is_system_hypothesis=bool(statement.get("system_hypothesis")),
                is_user_possibility=bool(statement.get("user_possibility")),
            )
            findings.append(
                ReasoningFinding(
                    code="EPISTEMIC_CATEGORY",
                    message=f"Statement {statement_id} classified as {category}.",
                    severity=ReasoningSeverity.INFO,
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                    references=(statement_id,),
                )
            )
        return _result(
            self.definition, context, ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings), code="EPISTEMIC_CATEGORIES_ASSIGNED",
            message="Epistemic categories assigned without promotion.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MedicationTemporalRelationshipRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class HealthMedicationTemporalRelationshipRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        relation = _mapping(context.metadata, "medication_relation")
        if relation is None:
            return _result(
                self.definition, context, ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No medication relation metadata supplied.",
            )
        finding = ReasoningFinding(
            code="TEMPORAL_ASSOCIATION_NOT_CAUSATION",
            message="A temporal association does not prove causation.",
            severity=ReasoningSeverity.WARNING,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            references=(
                str(relation.get("medication", "unknown")),
                str(relation.get("symptom", "unknown")),
            ),
        )
        return _result(
            self.definition, context, ReasoningRuleResultStatus.APPLIED,
            findings=(finding,), code="TEMPORAL_ASSOCIATION_RECORDED",
            message="Temporal association recorded without causation.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MedicalRedFlagRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class HealthMedicalRedFlagRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        red_flag = context.metadata.get("red_flag")
        if not isinstance(red_flag, Mapping):
            return _result(
                self.definition, context, ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No red flag metadata supplied.",
            )
        severity = int(red_flag.get("symptom_severity", 0))
        is_flag = bool(red_flag.get("is_red_flag"))
        level = classify_escalation_level(
            symptom_severity=severity, is_red_flag=is_flag
        )
        finding = ReasoningFinding(
            code="RED_FLAG_ESCALATION_LEVEL",
            message=f"Escalation level: {level}.",
            severity=ReasoningSeverity.WARNING,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            references=(str(red_flag.get("id", "unknown")),),
        )
        escalation = ReasoningEscalation(
            code="PROFESSIONAL_REVIEW_REQUIRED",
            message="A red flag requires professional review, not a diagnosis.",
            severity=ReasoningSeverity.WARNING,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
        )
        return _result(
            self.definition, context, ReasoningRuleResultStatus.APPLIED,
            findings=(finding,), escalation=escalation,
            code="RED_FLAG_CLASSIFIED",
            message="Red flag classified; cause not diagnosed.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ClinicalSourcePriorityRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class HealthClinicalSourcePriorityRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        sources = _seq(context.metadata, "sources")
        if not sources:
            return _result(
                self.definition, context, ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No source metadata supplied.",
            )
        findings: list[ReasoningFinding] = []
        for source in sources:
            if not isinstance(source, Mapping):
                continue
            source_id = source.get("id", "unknown")
            rank = clinical_source_rank(str(source.get("type", "unknown")))
            findings.append(
                ReasoningFinding(
                    code="SOURCE_PRIORITY_RANK",
                    message=f"Source {source_id} priority rank {rank}.",
                    severity=ReasoningSeverity.INFO,
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                    references=(source_id,),
                )
            )
        return _result(
            self.definition, context, ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings), code="SOURCE_PRIORITY_RANKED",
            message="Source priority ranked; provenance preserved.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MedicalTemporalValidityRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class HealthMedicalTemporalValidityRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        temporal = _mapping(context.metadata, "temporal")
        if temporal is None:
            return _result(
                self.definition, context, ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No temporal metadata supplied.",
            )
        state = evaluate_clinical_temporality(
            state=str(temporal.get("state", "unknown")),
            active=bool(temporal.get("active")),
            withdrawn=bool(temporal.get("withdrawn")),
            superseded=bool(temporal.get("superseded")),
        )
        if state == "unknown":
            gap = ReasoningGap(
                code="TEMPORAL_UNKNOWN",
                message="Temporal status is unknown; not treated as current.",
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
            return _result(
                self.definition, context, ReasoningRuleResultStatus.APPLIED,
                gaps=(gap,), code="TEMPORAL_UNKNOWN_RECORDED",
                message="Unknown temporality recorded as gap.",
            )
        if state == "expired":
            finding = ReasoningFinding(
                code="TEMPORAL_EXPIRED",
                message="Clinical data is expired; not treated as current.",
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
            return _result(
                self.definition, context, ReasoningRuleResultStatus.APPLIED,
                findings=(finding,), code="TEMPORAL_EXPIRED_RECORDED",
                message="Expired temporality recorded.",
            )
        return _result(
            self.definition, context, ReasoningRuleResultStatus.APPLIED,
            code="TEMPORAL_STATE_CLASSIFIED",
            message=f"Temporal state classified as {state}.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MedicationConsistencyRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class HealthMedicationConsistencyRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        records = _seq(context.metadata, "medication_records")
        if not records:
            return _result(
                self.definition, context, ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No medication records supplied.",
            )
        conflicts = detect_medication_conflicts(records)
        findings = tuple(
            ReasoningFinding(
                code=conflict.code,
                message=conflict.message,
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                references=conflict.medication_ids,
            )
            for conflict in conflicts
        )
        return _result(
            self.definition, context, ReasoningRuleResultStatus.APPLIED,
            findings=findings, code="MEDICATION_CONSISTENCY_EVALUATED",
            message="Medication consistency evaluated without deciding correctness.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# NoDefinitiveDiagnosisRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class HealthNoDefinitiveDiagnosisRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        claim = _mapping(context.metadata, "diagnostic_claim")
        if claim is None:
            return _result(
                self.definition, context, ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No diagnostic claim metadata supplied.",
            )
        verdict = validate_diagnostic_claim(
            evidence=bool(claim.get("evidence")),
            documented=bool(claim.get("documented")),
            confirmed=bool(claim.get("confirmed")),
            provisional=bool(claim.get("provisional")),
        )
        if verdict["is_definitive"]:
            return _result(
                self.definition, context, ReasoningRuleResultStatus.APPLIED,
                code="DEFINITIVE_CLAIM_DOCUMENTED",
                message="Definitive diagnostic claim is documented.",
            )
        finding = ReasoningFinding(
            code="NO_DEFINITIVE_DIAGNOSIS",
            message=verdict["reason"],
            severity=ReasoningSeverity.WARNING,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
        )
        escalation = ReasoningEscalation(
            code="PROFESSIONAL_CONFIRMATION_REQUIRED",
            message="Diagnosis must not be presented as definitive without confirmation.",
            severity=ReasoningSeverity.WARNING,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
        )
        return _result(
            self.definition, context, ReasoningRuleResultStatus.BLOCKED,
            findings=(finding,), escalation=escalation,
            code="DEFINITIVE_DIAGNOSIS_BLOCKED",
            message=verdict["reason"],
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ProfessionalEscalationRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class HealthProfessionalEscalationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        factors = _mapping(context.metadata, "escalation_factors")
        if factors is None:
            return _result(
                self.definition, context, ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No escalation factor metadata supplied.",
            )
        verdict = evaluate_professional_escalation(
            risk=bool(factors.get("risk")),
            significant_deterioration=bool(factors.get("significant_deterioration")),
            insufficient_exploration=bool(factors.get("insufficient_exploration")),
            missing_important_tests=bool(factors.get("missing_important_tests")),
            unresolved_contradiction=bool(factors.get("unresolved_contradiction")),
            request_clinical_decision=bool(factors.get("request_clinical_decision")),
            unresolvable_uncertainty=bool(factors.get("unresolvable_uncertainty")),
        )
        if not verdict["escalate"]:
            return _result(
                self.definition, context, ReasoningRuleResultStatus.APPLIED,
                code="NO_ESCALATION_REQUIRED",
                message=verdict["reason"],
            )
        escalation = ReasoningEscalation(
            code="PROFESSIONAL_ESCALATION_REQUIRED",
            message=verdict["reason"],
            severity=ReasoningSeverity.WARNING,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
        )
        finding = ReasoningFinding(
            code="ESCALATION_REQUIRED",
            message=verdict["reason"],
            severity=ReasoningSeverity.WARNING,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
        )
        return _result(
            self.definition, context, ReasoningRuleResultStatus.BLOCKED,
            findings=(finding,), escalation=escalation,
            code="PROFESSIONAL_ESCALATION_RECOMMENDED",
            message=verdict["reason"],
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════════════


def build_health_rules() -> tuple[Any, ...]:
    """Build the eight Health Domain rules deterministically in canonical order."""
    by_id = {
        "health.clinical_source_priority": HealthClinicalSourcePriorityRule(
            definition=_definition(
                "health.clinical_source_priority", "HealthClinicalSourcePriorityRule",
                ReasoningRuleCategory.EPISTEMIC.value, 730,
            )
        ),
        "health.medical_red_flag": HealthMedicalRedFlagRule(
            definition=_definition(
                "health.medical_red_flag", "HealthMedicalRedFlagRule",
                ReasoningRuleCategory.SAFETY.value, 790,
                risk_level=ReasoningRiskLevel.HIGH,
            )
        ),
        "health.medical_temporal_validity": HealthMedicalTemporalValidityRule(
            definition=_definition(
                "health.medical_temporal_validity", "HealthMedicalTemporalValidityRule",
                ReasoningRuleCategory.TEMPORALITY.value, 760,
            )
        ),
        "health.medication_consistency": HealthMedicationConsistencyRule(
            definition=_definition(
                "health.medication_consistency", "HealthMedicationConsistencyRule",
                ReasoningRuleCategory.CONSISTENCY.value, 750,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "health.medication_temporal_relationship": HealthMedicationTemporalRelationshipRule(
            definition=_definition(
                "health.medication_temporal_relationship",
                "HealthMedicationTemporalRelationshipRule",
                ReasoningRuleCategory.TEMPORALITY.value, 740,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "health.no_definitive_diagnosis": HealthNoDefinitiveDiagnosisRule(
            definition=_definition(
                "health.no_definitive_diagnosis", "HealthNoDefinitiveDiagnosisRule",
                ReasoningRuleCategory.SAFETY.value, 810,
                risk_level=ReasoningRiskLevel.HIGH,
            )
        ),
        "health.professional_escalation": HealthProfessionalEscalationRule(
            definition=_definition(
                "health.professional_escalation", "HealthProfessionalEscalationRule",
                ReasoningRuleCategory.SAFETY.value, 800,
                risk_level=ReasoningRiskLevel.HIGH,
            )
        ),
        "health.symptom_diagnosis_hypothesis": HealthSymptomDiagnosisHypothesisRule(
            definition=_definition(
                "health.symptom_diagnosis_hypothesis",
                "HealthSymptomDiagnosisHypothesisRule",
                ReasoningRuleCategory.EPISTEMIC.value, 720,
            )
        ),
    }
    return tuple(by_id[rule_id] for rule_id in HEALTH_RULE_IDS)


__all__ = [
    "EPISTEMIC_CATEGORY_DOCUMENTED",
    "EPISTEMIC_CATEGORY_DOCUMENTED_DIAGNOSIS",
    "EPISTEMIC_CATEGORY_ESCALATION",
    "EPISTEMIC_CATEGORY_HYPOTHESIS",
    "EPISTEMIC_CATEGORY_MISSING",
    "EPISTEMIC_CATEGORY_OBSERVATION",
    "EPISTEMIC_CATEGORY_POSSIBILITY",
    "EPISTEMIC_CATEGORY_PROVISIONAL",
    "EPISTEMIC_CATEGORY_RED_FLAG",
    "EPISTEMIC_CATEGORY_REPORTED_SYMPTOM",
    "ESCALATION_MONITORING",
    "ESCALATION_PRIORITY_REVIEW",
    "ESCALATION_PROFESSIONAL_REVIEW",
    "ESCALATION_URGENT_ATTENTION",
    "HEALTH_RULE_IDS",
    "MEDICATION_RELATION_DOSE_CHANGE",
    "MEDICATION_RELATION_EVOLUTION",
    "MEDICATION_RELATION_REEXPOSURE",
    "MEDICATION_RELATION_START",
    "MEDICATION_RELATION_SYMPTOM_ONSET",
    "MEDICATION_RELATION_WITHDRAWAL",
    "HealthClinicalSourcePriorityRule",
    "HealthMedicalRedFlagRule",
    "HealthMedicalTemporalValidityRule",
    "HealthMedicationConsistencyRule",
    "HealthMedicationTemporalRelationshipRule",
    "HealthNoDefinitiveDiagnosisRule",
    "HealthProfessionalEscalationRule",
    "HealthSymptomDiagnosisHypothesisRule",
    "MedicationConflict",
    "build_health_rules",
    "build_medication_temporal_relation",
    "classify_clinical_statement",
    "classify_escalation_level",
    "clinical_source_rank",
    "detect_medication_conflicts",
    "evaluate_clinical_temporality",
    "evaluate_professional_escalation",
    "validate_diagnostic_claim",
]

# Re-export closed epistemic constants used across the module surface
_EPISTEMIC_EXPORTS = (
    "EPISTEMIC_CATEGORY_CONTRADICTION",
    "EPISTEMIC_CATEGORY_DOCUMENTED",
    "EPISTEMIC_CATEGORY_DOCUMENTED_DIAGNOSIS",
    "EPISTEMIC_CATEGORY_ESCALATION",
    "EPISTEMIC_CATEGORY_HYPOTHESIS",
    "EPISTEMIC_CATEGORY_MISSING",
    "EPISTEMIC_CATEGORY_OBSERVATION",
    "EPISTEMIC_CATEGORY_POSSIBILITY",
    "EPISTEMIC_CATEGORY_PROVISIONAL",
    "EPISTEMIC_CATEGORY_RED_FLAG",
    "EPISTEMIC_CATEGORY_REPORTED_SYMPTOM",
)
assert all(name in globals() for name in _EPISTEMIC_EXPORTS)
