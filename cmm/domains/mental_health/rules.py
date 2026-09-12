"""Phase 10.52 — Mental Health Domain Rules and deterministic helpers.

A declarative domain plus pure deterministic emotional/therapeutic helpers.
The helpers are state-free: no IO, no model calls, no registry mutation, no
internal clock.  They receive context explicitly and return deterministic
structures.

Semantic invariants preserved here (frozen design §10, §29, §30, §32):

    emotion != fact; interpretation != fact; fear != prediction;
    intuition != evidence; possibility != probability;
    repetition != pathology; distress != emergency; concern != disorder;
    therapist statement != system fact; user statement != clinician statement;
    model interpretation != source statement; talking != authorization.

Repeated thought never becomes diagnosis.  Ordinary distress never becomes an
emergency.  A documented Health-owned clinical fact never becomes
Mental-Health-owned truth.  Sensitive inference never persists implicitly.
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
from cmm.domains.mental_health.catalog import CANONICAL_MENTAL_HEALTH_RULE_IDS
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition, DomainRuleResult

MENTAL_HEALTH_RULE_IDS: tuple[str, ...] = CANONICAL_MENTAL_HEALTH_RULE_IDS

# ── Closed epistemic categories surfaced by Mental Health ────────────────────
# These are *labels* over the canonical Cognitive Layer kinds.  Mental Health
# does not create a second persistent taxonomy (frozen design §10).

EPISTEMIC_FACT = "fact"
EPISTEMIC_OBSERVATION = "observation"
EPISTEMIC_INTERPRETATION = "interpretation"
EPISTEMIC_HYPOTHESIS = "hypothesis"
EPISTEMIC_FEAR = "fear"
EPISTEMIC_INTUITION = "intuition"
EPISTEMIC_PREFERENCE = "preference"
EPISTEMIC_DECISION = "decision"
EPISTEMIC_UNCERTAINTY = "uncertainty"
EPISTEMIC_UNKNOWN = "unknown"

# ── Speaker attribution classes for therapy material (spec §30) ───────────────

SPEAKER_THERAPIST = "therapist"
SPEAKER_USER = "user"
SPEAKER_MODEL = "model"
SPEAKER_UNKNOWN = "unknown"

_KNOWN_SPEAKERS = frozenset({SPEAKER_THERAPIST, SPEAKER_USER, SPEAKER_MODEL})

# Content kinds that must never be silently persisted by Mental Health.
_RESTRICTED_CONTENT_KINDS = frozenset(
    {
        "fear",
        "intuition",
        "inferred_emotional_pattern",
        "emotional_pattern",
        "emotional_loop",
        "loop_hypothesis",
        "psychological_interpretation",
        "psychiatric_interpretation",
        "disorder_attribution",
        "third_party_motive",
        "trauma_inference",
    }
)

# Emotional-context vocabulary used for relevance detection only.  This is not
# a diagnosis vocabulary and never produces a clinical label.
_EMOTIONAL_MARKERS = (
    "feel",
    "feeling",
    "felt",
    "emotion",
    "emotional",
    "lonely",
    "loneliness",
    "sad",
    "sadness",
    "anxious",
    "anxiety",
    "worry",
    "worried",
    "frustrat",
    "angry",
    "anger",
    "grief",
    "distress",
    "overwhelm",
    "therapy",
    "therapist",
    "psychologist",
    "session",
    "mood",
    "cope",
    "coping",
    "rumination",
    "loop",
    "self-esteem",
    "burnout",
)


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
        domain_id="domain:mental-health",
        category=category,
        status=ReasoningRuleStatus.ENABLED,
        priority=priority,
        risk_level=risk_level,
        deterministic=True,
        description=(
            "Conservative, non-pathologizing emotional rule for " + rule_id + "."
        ),
        metadata={"phase": "10.52"},
    )


def _result(
    definition: ReasoningRuleDefinition,
    context: ReasoningRuleContext,
    status: ReasoningRuleResultStatus,
    *,
    findings: tuple[ReasoningFinding, ...] = (),
    gaps: tuple[ReasoningGap, ...] = (),
    escalation: ReasoningEscalation | None = None,
    metadata: Mapping | None = None,
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
        metadata=dict(metadata or {}),
        started_at=context.timestamp,
        completed_at=context.timestamp,
    )


def _mapping(metadata: Mapping, key: str) -> Mapping | None:
    value = metadata.get(key)
    return value if isinstance(value, Mapping) else None


def _seq(metadata: Mapping, key: str) -> tuple | None:
    value = metadata.get(key)
    return value if isinstance(value, (list, tuple)) else None


def _finding(
    definition: ReasoningRuleDefinition,
    code: str,
    message: str,
    *,
    severity: ReasoningSeverity = ReasoningSeverity.INFO,
    references: tuple[str, ...] = (),
    metadata: Mapping | None = None,
) -> ReasoningFinding:
    return ReasoningFinding(
        code=code,
        message=message,
        severity=severity,
        rule_id=definition.id,
        domain_id=definition.domain_id,
        references=references,
        metadata=dict(metadata or {}),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Pure deterministic helpers
# ═══════════════════════════════════════════════════════════════════════════════


def is_emotionally_relevant(text: Any) -> bool:
    """Deterministic, non-clinical relevance detection for an objective.

    Matching emotional language is a *routing/relevance* signal only.  It never
    produces a diagnosis, a severity score, or a clinical label.
    """
    if not isinstance(text, str):
        return False
    lowered = text.casefold()
    return any(marker in lowered for marker in _EMOTIONAL_MARKERS)


def classify_emotional_statement(statement: Mapping) -> str:
    """Classify a statement into one closed epistemic label.

    Precedence is deliberately conservative: uncertainty and non-factual
    classes win over ``fact`` so an ambiguous statement can never be promoted
    to fact.  ``fact`` requires an explicit non-inferential fact flag.
    """
    if bool(statement.get("uncertainty")):
        return EPISTEMIC_UNCERTAINTY
    if bool(statement.get("fear")) or bool(statement.get("fear_as_prediction")):
        return EPISTEMIC_FEAR
    if bool(statement.get("intuition")):
        return EPISTEMIC_INTUITION
    if bool(statement.get("interpretation")):
        return EPISTEMIC_INTERPRETATION
    if bool(statement.get("hypothesis")):
        return EPISTEMIC_HYPOTHESIS
    if bool(statement.get("preference")):
        return EPISTEMIC_PREFERENCE
    if bool(statement.get("decision")):
        return EPISTEMIC_DECISION
    if bool(statement.get("observation")):
        return EPISTEMIC_OBSERVATION
    if bool(statement.get("fact")) and not (
        statement.get("interpretation")
        or statement.get("fear")
        or statement.get("intuition")
    ):
        return EPISTEMIC_FACT
    return EPISTEMIC_UNKNOWN


def classify_speaker(turn: Mapping) -> str:
    """Return the closed speaker attribution class for a transcript turn."""
    if bool(turn.get("model_interpretation")):
        return SPEAKER_MODEL
    speaker = turn.get("speaker")
    if isinstance(speaker, str):
        normalized = speaker.strip().casefold()
        if normalized in _KNOWN_SPEAKERS:
            return normalized
        if normalized in {"assistant", "system"}:
            return SPEAKER_MODEL
    return SPEAKER_UNKNOWN


def is_persistence_restricted_content(content_kind: Any) -> bool:
    """True when ``content_kind`` must never be silently persisted."""
    if not isinstance(content_kind, str):
        return True
    return content_kind.strip().casefold() in _RESTRICTED_CONTENT_KINDS


def persistence_is_authorized(authorization: Any) -> bool:
    """Strict authorization: only an explicit approval chain authorizes.

    Raw booleans, numerics, strings, ``None`` and arbitrary mappings never
    authorize.  Repetition, intensity or emotional certainty are not
    authorization either.
    """
    if not isinstance(authorization, Mapping):
        return False
    if authorization.get("approved") is not True:
        return False
    # A canonical approval chain requires a referenced proposal and binding.
    return bool(authorization.get("proposal_id")) and bool(
        authorization.get("binding_id")
    )


def detect_health_owned_clinical_claim(claim: Mapping) -> dict:
    """Deterministically decide whether a claim is Health-owned clinical truth.

    Any documented diagnosis, treatment, medication or medical-safety claim is
    Health-owned.  Mental Health may support it but may never override it.
    """
    clinical_keys = (
        "documented_diagnosis",
        "diagnosis_status",
        "treatment_plan",
        "medication",
        "documented_medication_change",
        "medical_safety",
        "clinical_record",
    )
    is_clinical = any(bool(claim.get(key)) for key in clinical_keys)
    override_requested = isinstance(claim.get("requested"), str) and claim.get(
        "requested"
    ) in {
        "adjust_medication",
        "change_medication",
        "stop_medication",
        "start_medication",
        "set_diagnosis",
        "confirm_diagnosis",
        "change_treatment",
    }
    return {
        "primary_authority": "domain:health" if is_clinical else "domain:mental-health",
        "is_health_owned": is_clinical,
        "override_requested": override_requested,
        "mental_health_may_override": False,
        "mental_health_supporting_allowed": is_clinical,
    }


def evaluate_safety_proportionality(safety: Mapping) -> dict:
    """Ordinary distress is never an emergency.

    Escalation requires material, credible immediate risk.  Emotional language,
    intensity, repetition or unverified claims never trigger escalation.
    """
    material_risk = bool(safety.get("material_risk"))
    credible = bool(safety.get("credible", True))
    specialized = safety.get("specialized_domain_result") is not None
    escalate = material_risk and credible
    return {
        "escalate": escalate,
        "routed_to_specialized_contract": specialized,
        "emotion_triggered_escalation": False,
        "ordinary_distress_is_not_emergency": True,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 1. EmotionalContextRelevanceRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class EmotionalContextRelevanceRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        objective = context.metadata.get("objective")
        relevant = is_emotionally_relevant(objective)
        if not isinstance(objective, str) or not objective.strip():
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No objective supplied.",
            )
        finding = _finding(
            self.definition,
            "EMOTIONAL_CONTEXT_RELEVANCE",
            (
                "The objective carries emotional/thereapeutic meaning; route to "
                "emotional specialization without clinical framing."
                if relevant
                else "No emotional meaning detected; no clinical framing is added."
            ),
            metadata={
                "emotionally_relevant": relevant,
                "clinical_framing_added": False,
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            metadata={"emotionally_relevant": relevant},
            code="EMOTIONAL_CONTEXT_EVALUATED",
            message="Emotional relevance evaluated without pathologizing.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. EmotionalEpistemicSeparationRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class EmotionalEpistemicSeparationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        statements = _seq(context.metadata, "statements")
        if not statements:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No statements supplied.",
            )
        findings: list[ReasoningFinding] = []
        for statement in statements:
            if not isinstance(statement, Mapping):
                continue
            statement_id = str(statement.get("id", "unknown"))
            category = classify_emotional_statement(statement)
            findings.append(
                _finding(
                    self.definition,
                    "EPISTEMIC_CATEGORY",
                    (
                        f"Statement {statement_id} kept as {category}; facts, "
                        "observations, interpretations, hypotheses, fears and "
                        "intuitions stay distinct and are never promoted."
                    ),
                    references=(statement_id,),
                    metadata={"epistemic_category": category},
                )
            )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            metadata={"promotion_performed": False},
            code="EPISTEMIC_SEPARATION_APPLIED",
            message="Fact/interpretation/fear/intuition kept distinct.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. NonPathologizingDefaultRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class NonPathologizingDefaultRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        mode = context.metadata.get("mode", "ordinary")
        finding = _finding(
            self.definition,
            "NON_PATHOLOGIZING_DEFAULT",
            "Ordinary emotional conversation is treated as human, not clinical.",
            metadata={
                "mode": str(mode),
                "clinical_presentation_default": False,
                "diagnostic_language_used": False,
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            metadata={"clinical_presentation_default": False},
            code="NON_PATHOLOGIZING_DEFAULT_APPLIED",
            message="No default medicalization.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. MaterialGapQuestioningRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class MaterialGapQuestioningRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        gaps = _seq(context.metadata, "gaps")
        if not gaps:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No gap inputs supplied.",
            )
        findings: list[ReasoningFinding] = []
        out_gaps: list[ReasoningGap] = []
        for gap in gaps:
            if not isinstance(gap, Mapping):
                continue
            if not bool(gap.get("affects_reasoning")):
                continue
            topic = str(gap.get("topic", "unknown"))
            findings.append(
                _finding(
                    self.definition,
                    "MATERIAL_GAP",
                    f"Material gap '{topic}' affects reasoning; ask before concluding.",
                    severity=ReasoningSeverity.INFO,
                    references=(topic,),
                    metadata={"topic": topic},
                )
            )
            out_gaps.append(
                ReasoningGap(
                    code="MATERIAL_GAP",
                    message=f"Missing material information: {topic}.",
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
            gaps=tuple(out_gaps),
            code="MATERIAL_GAPS_IDENTIFIED",
            message="Only materially relevant questions were raised.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. AuthorizedLongitudinalContinuityRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AuthorizedLongitudinalContinuityRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        longitudinal = _mapping(context.metadata, "longitudinal")
        if longitudinal is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No longitudinal inputs supplied.",
            )
        references = longitudinal.get("references") or ()
        if not isinstance(references, (list, tuple)):
            references = ()
        unauthorized = tuple(
            str(ref.get("id", "unknown"))
            for ref in references
            if isinstance(ref, Mapping) and not bool(ref.get("authorized"))
        )
        if unauthorized:
            finding = _finding(
                self.definition,
                "UNAUTHORIZED_LONGITUDINAL_REFERENCE",
                "Longitudinal use requires current authorization; unauthorized "
                "references are blocked.",
                severity=ReasoningSeverity.WARNING,
                references=unauthorized,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(finding,),
                metadata={
                    "unauthorized_references": unauthorized,
                    "authorization_revalidated": True,
                },
                code="LONGITUDINAL_ACCESS_BLOCKED",
                message="Longitudinal access failed closed.",
            )
        findings = tuple(
            _finding(
                self.definition,
                "AUTHORIZED_LONGITUDINAL_REFERENCE",
                "Authorized longitudinal reference used with provenance and date.",
                references=(str(ref.get("id", "unknown")),),
                metadata={"date": ref.get("date")},
            )
            for ref in references
            if isinstance(ref, Mapping)
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=findings,
            metadata={"authorization_revalidated": True},
            code="LONGITUDINAL_CONTINUITY_APPLIED",
            message="Longitudinal context used only through authorized references.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 6. TherapySpeakerProvenanceRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class TherapySpeakerProvenanceRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        turns = _seq(context.metadata, "transcript_turns")
        if not turns:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No transcript turns supplied.",
            )
        findings: list[ReasoningFinding] = []
        unknown_claim: list[str] = []
        for turn in turns:
            if not isinstance(turn, Mapping):
                continue
            turn_id = str(turn.get("id", "unknown"))
            speaker = classify_speaker(turn)
            findings.append(
                _finding(
                    self.definition,
                    "SPEAKER_ATTRIBUTION",
                    f"Turn {turn_id} attributed to {speaker}.",
                    references=(turn_id,),
                    metadata={"speaker": speaker, "source_identity_preserved": True},
                )
            )
            if speaker is SPEAKER_UNKNOWN and bool(turn.get("clinical_claim")):
                unknown_claim.append(turn_id)
        if unknown_claim:
            finding = _finding(
                self.definition,
                "SPEAKER_PROVENANCE_INSUFFICIENT",
                "An unattributed clinical claim cannot support a high-confidence "
                "conclusion.",
                severity=ReasoningSeverity.WARNING,
                references=tuple(unknown_claim),
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(*findings, finding),
                metadata={"unattributed_clinical_claims": tuple(unknown_claim)},
                code="SPEAKER_PROVENANCE_BLOCKED",
                message="High-confidence output blocked: provenance insufficient.",
            )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            metadata={
                "speaker_classes": sorted({f.metadata["speaker"] for f in findings})
            },
            code="SPEAKER_PROVENANCE_PRESERVED",
            message="Speaker and source identity preserved.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 7. TherapyStatementSeparationRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class TherapyStatementSeparationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        turns = _seq(context.metadata, "transcript_turns")
        if not turns:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No transcript turns supplied.",
            )
        fabricated = tuple(
            str(turn.get("id", "unknown"))
            for turn in turns
            if isinstance(turn, Mapping)
            and bool(turn.get("attributed_to_therapist"))
            and classify_speaker(turn) is not SPEAKER_THERAPIST
        )
        findings = tuple(
            _finding(
                self.definition,
                "STATEMENT_SOURCE_SEPARATED",
                f"Turn {turn.get('id', 'unknown')} kept as "
                f"{classify_speaker(turn)} statement.",
                references=(str(turn.get("id", "unknown")),),
                metadata={
                    "statement_source": classify_speaker(turn),
                    "model_interpretation_distinct": (
                        classify_speaker(turn) is SPEAKER_MODEL
                    ),
                },
            )
            for turn in turns
            if isinstance(turn, Mapping)
        )
        if fabricated:
            finding = _finding(
                self.definition,
                "FABRICATED_THERAPIST_STATEMENT",
                "A non-therapist statement must never be presented as therapist "
                "guidance.",
                severity=ReasoningSeverity.WARNING,
                references=fabricated,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(*findings, finding),
                metadata={"fabricated_therapist_statement": True},
                code="THERAPIST_STATEMENT_BLOCKED",
                message="Fabricated therapist statement blocked.",
            )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=findings,
            metadata={"fabricated_therapist_statement": False},
            code="STATEMENT_SOURCES_SEPARATED",
            message="Therapist/user/model statements kept separate.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 8. UncertaintyPreservationRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class UncertaintyPreservationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        conclusions = _seq(context.metadata, "conclusions")
        if not conclusions:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No conclusions supplied.",
            )
        findings: list[ReasoningFinding] = []
        gaps: list[ReasoningGap] = []
        for conclusion in conclusions:
            if not isinstance(conclusion, Mapping):
                continue
            conclusion_id = str(conclusion.get("id", "unknown"))
            certainty = str(conclusion.get("certainty", "unknown")).casefold()
            evidence = str(conclusion.get("evidence", "unknown")).casefold()
            thin = evidence in {"thin", "none", "", "weak"}
            if thin and certainty in {"high", "certain", "definitive"}:
                findings.append(
                    _finding(
                        self.definition,
                        "UNCERTAINTY_PRESERVED",
                        f"Conclusion {conclusion_id} keeps explicit uncertainty: "
                        "stated certainty exceeds evidence.",
                        severity=ReasoningSeverity.WARNING,
                        references=(conclusion_id,),
                        metadata={"certainty_withheld": True},
                    )
                )
                gaps.append(
                    ReasoningGap(
                        code="EVIDENCE_THIN",
                        message=(
                            f"Conclusion {conclusion_id} lacks supporting evidence."
                        ),
                        severity=ReasoningSeverity.WARNING,
                        rule_id=self.definition.id,
                        domain_id=self.definition.domain_id,
                    )
                )
            else:
                findings.append(
                    _finding(
                        self.definition,
                        "UNCERTAINTY_PRESERVED",
                        f"Conclusion {conclusion_id} retains its uncertainty level.",
                        references=(conclusion_id,),
                        metadata={"certainty_withheld": False},
                    )
                )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            gaps=tuple(gaps),
            metadata={"evidence_presence_grants_certainty": False},
            code="UNCERTAINTY_PRESERVED",
            message="Emotional certainty never became evidential certainty.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 9. RepetitionWithoutPathologyRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class RepetitionWithoutPathologyRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        recurrence = _mapping(context.metadata, "recurrence")
        if recurrence is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No recurrence inputs supplied.",
            )
        topic = str(recurrence.get("topic", "unknown"))
        finding = _finding(
            self.definition,
            "REPETITION_REVIEWED_WITHOUT_PATHOLOGY",
            (
                "Repeating an emotional topic is not a disorder; no diagnosis, "
                "label or severity score is inferred from repetition."
            ),
            references=(topic,),
            metadata={
                "topic": topic,
                "pathology_inferred": False,
                "disorder_attributed": False,
                "severity_score_invented": False,
                "psychiatric_label": None,
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            escalation=None,
            metadata={
                "pathology_inferred": False,
                "disorder_attributed": False,
            },
            code="REPETITION_EVALUATED",
            message="Repeated loop reviewed non-pathologizingly.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 10. HealthAuthorityRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class HealthAuthorityRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        claim = _mapping(context.metadata, "clinical_claim")
        if claim is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No clinical claim supplied.",
            )
        verdict = detect_health_owned_clinical_claim(claim)
        if verdict["is_health_owned"] and verdict["override_requested"]:
            finding = _finding(
                self.definition,
                "HEALTH_AUTHORITY_BOUNDARY",
                "Documented diagnosis, treatment or medication truth belongs to "
                "Health; Mental Health may support but never overrides it.",
                severity=ReasoningSeverity.WARNING,
                metadata={
                    "primary_authority": verdict["primary_authority"],
                    "mental_health_may_override": False,
                    "mental_health_supporting_allowed": True,
                },
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(finding,),
                metadata={
                    "primary_authority": verdict["primary_authority"],
                    "mental_health_may_override": False,
                    "mental_health_supporting_allowed": True,
                },
                code="CLINICAL_OVERRIDE_BLOCKED",
                message="Clinical override blocked; Health authority preserved.",
            )
        finding = _finding(
            self.definition,
            "HEALTH_AUTHORITY_BOUNDARY",
            "No clinical override requested; Health ownership unchanged.",
            metadata={
                "primary_authority": verdict["primary_authority"],
                "mental_health_may_override": False,
                "mental_health_supporting_allowed": verdict[
                    "mental_health_supporting_allowed"
                ],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            metadata={
                "primary_authority": verdict["primary_authority"],
                "mental_health_may_override": False,
                "mental_health_supporting_allowed": verdict[
                    "mental_health_supporting_allowed"
                ],
            },
            code="HEALTH_AUTHORITY_PRESERVED",
            message="Health clinical authority preserved.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 11. PurposeMinimizedCrossDomainRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class PurposeMinimizedCrossDomainRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        projection = _mapping(context.metadata, "projection")
        if projection is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No cross-domain projection supplied.",
            )
        fields = projection.get("fields")
        if not isinstance(fields, Mapping):
            fields = {}
        included = tuple(
            name
            for name, spec in fields.items()
            if isinstance(spec, Mapping) and bool(spec.get("relevant"))
        )
        excluded = tuple(name for name in fields if name not in included)
        finding = _finding(
            self.definition,
            "PURPOSE_MINIMIZED_PROJECTION",
            (
                "Only fields material to the current purpose were projected; "
                "irrelevant sensitive fields were excluded."
            ),
            metadata={
                "purpose": str(projection.get("purpose", "unknown")),
                "source_domain": str(projection.get("source_domain", "unknown")),
                "included_fields": list(included),
                "excluded_fields": list(excluded),
                "provenance_preserved": True,
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            metadata={
                "included_fields": included,
                "excluded_fields": excluded,
                "provenance_preserved": True,
            },
            code="CROSS_DOMAIN_MINIMIZED",
            message="Cross-domain import minimized to the authorized purpose.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 12. SensitivePersistenceControlRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class SensitivePersistenceControlRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        request = _mapping(context.metadata, "persistence_request")
        if request is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No persistence request supplied.",
            )
        content_kind = request.get("content_kind")
        restricted = is_persistence_restricted_content(content_kind)
        authorized = persistence_is_authorized(request.get("authorization"))
        blocked = restricted or not authorized
        finding = _finding(
            self.definition,
            "SENSITIVE_PERSISTENCE_CONTROL",
            (
                "Sensitive inference is not persisted: discussion is not "
                "authorization and no approval chain was presented."
                if blocked
                else "Persistence proceeds only through the canonical proposal path."
            ),
            severity=ReasoningSeverity.WARNING if blocked else ReasoningSeverity.INFO,
            metadata={
                "content_kind": content_kind if isinstance(content_kind, str) else None,
                "content_restricted": restricted,
                "authorization_accepted": authorized,
                "direct_write_performed": False,
                "proposal_required": True,
            },
        )
        return _result(
            self.definition,
            context,
            (
                ReasoningRuleResultStatus.BLOCKED
                if blocked
                else ReasoningRuleResultStatus.APPLIED
            ),
            findings=(finding,),
            metadata={
                "direct_write_performed": False,
                "proposal_required": True,
                "content_restricted": restricted,
            },
            code=(
                "SENSITIVE_PERSISTENCE_BLOCKED"
                if blocked
                else "SENSITIVE_PERSISTENCE_PROPOSAL_ALLOWED"
            ),
            message=(
                "Implicit persistence blocked; proposal path required."
                if blocked
                else "Persistence goes through the canonical proposal path only."
            ),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 13. ProportionateSafetyEscalationRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ProportionateSafetyEscalationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        safety = _mapping(context.metadata, "safety")
        if safety is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No safety inputs supplied.",
            )
        record = evaluate_safety_proportionality(safety)
        if not record["escalate"]:
            finding = _finding(
                self.definition,
                "NO_ESCALATION",
                "Ordinary distress, intensity or repetition is not an emergency; "
                "no escalation is triggered without material risk.",
                metadata={
                    "escalate": False,
                    "emotion_triggered_escalation": False,
                },
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
                escalation=None,
                metadata={"escalate": False, "emotion_triggered_escalation": False},
                code="NO_ESCALATION_REQUIRED",
                message="Escalation proportionate: none required.",
            )
        finding = _finding(
            self.definition,
            "PROPORTIONATE_ESCALATION",
            "Material credible immediate risk routed through the existing "
            "canonical escalation mechanism; no own crisis engine was created.",
            severity=ReasoningSeverity.WARNING,
            metadata={
                "escalate": True,
                "emotion_triggered_escalation": False,
                "own_crisis_engine_created": False,
            },
        )
        escalation = ReasoningEscalation(
            code="PROPORTIONATE_SAFETY_REVIEW",
            message=(
                "Material immediate risk requires the existing canonical "
                "escalation path, not an invented crisis decision engine."
            ),
            severity=ReasoningSeverity.WARNING,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.BLOCKED,
            findings=(finding,),
            escalation=escalation,
            metadata={
                "escalate": True,
                "emotion_triggered_escalation": False,
                "own_crisis_engine_created": False,
            },
            code="PROPORTIONATE_ESCALATION_ROUTED",
            message="Escalation routed proportionately.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════════════


def build_mental_health_rules() -> tuple[Any, ...]:
    """Build the thirteen Mental Health rules deterministically in catalog order."""
    by_id = {
        "mental_health.authorized_longitudinal_continuity": (
            AuthorizedLongitudinalContinuityRule(
                definition=_definition(
                    "mental_health.authorized_longitudinal_continuity",
                    "AuthorizedLongitudinalContinuityRule",
                    ReasoningRuleCategory.TEMPORALITY.value,
                    750,
                    risk_level=ReasoningRiskLevel.MEDIUM,
                )
            )
        ),
        "mental_health.emotional_context_relevance": EmotionalContextRelevanceRule(
            definition=_definition(
                "mental_health.emotional_context_relevance",
                "EmotionalContextRelevanceRule",
                ReasoningRuleCategory.INFERENCE.value,
                700,
            )
        ),
        "mental_health.emotional_epistemic_separation": (
            EmotionalEpistemicSeparationRule(
                definition=_definition(
                    "mental_health.emotional_epistemic_separation",
                    "EmotionalEpistemicSeparationRule",
                    ReasoningRuleCategory.EPISTEMIC.value,
                    760,
                )
            )
        ),
        "mental_health.health_authority": HealthAuthorityRule(
            definition=_definition(
                "mental_health.health_authority",
                "HealthAuthorityRule",
                ReasoningRuleCategory.SAFETY.value,
                830,
                risk_level=ReasoningRiskLevel.HIGH,
            )
        ),
        "mental_health.material_gap_questioning": MaterialGapQuestioningRule(
            definition=_definition(
                "mental_health.material_gap_questioning",
                "MaterialGapQuestioningRule",
                ReasoningRuleCategory.INFERENCE.value,
                720,
            )
        ),
        "mental_health.non_pathologizing_default": NonPathologizingDefaultRule(
            definition=_definition(
                "mental_health.non_pathologizing_default",
                "NonPathologizingDefaultRule",
                ReasoningRuleCategory.EPISTEMIC.value,
                740,
            )
        ),
        "mental_health.proportionate_safety_escalation": (
            ProportionateSafetyEscalationRule(
                definition=_definition(
                    "mental_health.proportionate_safety_escalation",
                    "ProportionateSafetyEscalationRule",
                    ReasoningRuleCategory.SAFETY.value,
                    840,
                    risk_level=ReasoningRiskLevel.HIGH,
                )
            )
        ),
        "mental_health.purpose_minimized_cross_domain": (
            PurposeMinimizedCrossDomainRule(
                definition=_definition(
                    "mental_health.purpose_minimized_cross_domain",
                    "PurposeMinimizedCrossDomainRule",
                    ReasoningRuleCategory.CONSISTENCY.value,
                    730,
                    risk_level=ReasoningRiskLevel.MEDIUM,
                )
            )
        ),
        "mental_health.repetition_without_pathology": (
            RepetitionWithoutPathologyRule(
                definition=_definition(
                    "mental_health.repetition_without_pathology",
                    "RepetitionWithoutPathologyRule",
                    ReasoningRuleCategory.EPISTEMIC.value,
                    710,
                )
            )
        ),
        "mental_health.sensitive_persistence_control": (
            SensitivePersistenceControlRule(
                definition=_definition(
                    "mental_health.sensitive_persistence_control",
                    "SensitivePersistenceControlRule",
                    ReasoningRuleCategory.SAFETY.value,
                    820,
                    risk_level=ReasoningRiskLevel.HIGH,
                )
            )
        ),
        "mental_health.therapy_speaker_provenance": TherapySpeakerProvenanceRule(
            definition=_definition(
                "mental_health.therapy_speaker_provenance",
                "TherapySpeakerProvenanceRule",
                ReasoningRuleCategory.EPISTEMIC.value,
                780,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "mental_health.therapy_statement_separation": (
            TherapyStatementSeparationRule(
                definition=_definition(
                    "mental_health.therapy_statement_separation",
                    "TherapyStatementSeparationRule",
                    ReasoningRuleCategory.EPISTEMIC.value,
                    770,
                    risk_level=ReasoningRiskLevel.MEDIUM,
                )
            )
        ),
        "mental_health.uncertainty_preservation": UncertaintyPreservationRule(
            definition=_definition(
                "mental_health.uncertainty_preservation",
                "UncertaintyPreservationRule",
                ReasoningRuleCategory.EPISTEMIC.value,
                790,
            )
        ),
    }
    return tuple(by_id[rule_id] for rule_id in MENTAL_HEALTH_RULE_IDS)


__all__ = [
    "EPISTEMIC_DECISION",
    "EPISTEMIC_FACT",
    "EPISTEMIC_FEAR",
    "EPISTEMIC_HYPOTHESIS",
    "EPISTEMIC_INTERPRETATION",
    "EPISTEMIC_INTUITION",
    "EPISTEMIC_OBSERVATION",
    "EPISTEMIC_PREFERENCE",
    "EPISTEMIC_UNCERTAINTY",
    "EPISTEMIC_UNKNOWN",
    "MENTAL_HEALTH_RULE_IDS",
    "SPEAKER_MODEL",
    "SPEAKER_THERAPIST",
    "SPEAKER_UNKNOWN",
    "SPEAKER_USER",
    "AuthorizedLongitudinalContinuityRule",
    "EmotionalContextRelevanceRule",
    "EmotionalEpistemicSeparationRule",
    "HealthAuthorityRule",
    "MaterialGapQuestioningRule",
    "NonPathologizingDefaultRule",
    "ProportionateSafetyEscalationRule",
    "PurposeMinimizedCrossDomainRule",
    "RepetitionWithoutPathologyRule",
    "SensitivePersistenceControlRule",
    "TherapySpeakerProvenanceRule",
    "TherapyStatementSeparationRule",
    "UncertaintyPreservationRule",
    "build_mental_health_rules",
    "classify_emotional_statement",
    "classify_speaker",
    "detect_health_owned_clinical_claim",
    "evaluate_safety_proportionality",
    "is_emotionally_relevant",
    "is_persistence_restricted_content",
    "persistence_is_authorized",
]
