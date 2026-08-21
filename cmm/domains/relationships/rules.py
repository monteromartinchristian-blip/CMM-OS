"""Phase 10.21 — Relationships Domain Rules and deterministic helpers.

A declarative domain + pure deterministic relationship helpers.  The helper
functions are state-free: no IO, no model calls, no registry mutation, no
internal clock.  They receive context explicitly and return deterministic
structures.

The eight reasoning rules are ``@dataclass(frozen=True, slots=True)``
definitions exposing ``definition`` and ``evaluate(context)``, exactly like the
General and Health Domain rules, so they compose with the existing cognitive
layer.

Epistemic-safety core (spec §6–§8): provenance is NOT epistemic truth.  The
classification layer never promotes a user interpretation, a system
hypothesis, a possible function, or a possible origin into an observed fact.
The system never attributes intention as fact without direct evidence, never
diagnoses a third party, preserves ambivalence, and reviews boundaries without
acting on them.
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
from cmm.domains.relationships.catalog import CANONICAL_RELATIONSHIPS_RULE_IDS
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition, DomainRuleResult

RELATIONSHIPS_RULE_IDS: tuple[str, ...] = CANONICAL_RELATIONSHIPS_RULE_IDS

# ── Closed epistemic categories (spec §6) ─────────────────────────────────────

EPISTEMIC_CATEGORY_OBSERVED_FACT = "observed_fact"
EPISTEMIC_CATEGORY_DIRECT_STATEMENT = "direct_statement"
EPISTEMIC_CATEGORY_USER_INTERPRETATION = "user_interpretation"
EPISTEMIC_CATEGORY_SYSTEM_HYPOTHESIS = "system_hypothesis"
EPISTEMIC_CATEGORY_POSSIBLE_FUNCTION = "possible_function"
EPISTEMIC_CATEGORY_POSSIBLE_ORIGIN = "possible_origin"
EPISTEMIC_CATEGORY_UNKNOWN = "unknown"

# ── Closed relational pattern kinds (spec §14) ────────────────────────────────

PATTERN_APPROACH_DISTANCE_CYCLE = "approach_distance_cycle"
PATTERN_CONFLICT_REPAIR_CYCLE = "conflict_repair_cycle"
PATTERN_REPEATED_CANCELLATION = "repeated_cancellation"
PATTERN_SUPPORT_ASYMMETRY = "support_asymmetry"
PATTERN_FREQUENCY_CHANGE = "frequency_change"
PATTERN_BOUNDARY_CONFLICT = "boundary_conflict"
PATTERN_COMMITMENT_NON_FULFILMENT = "commitment_non_fulfilment"

# Closed pattern taxonomy derived from the canonical constants above.  This is
# the single canonical tuple/set used by both the rule layer and the operation
# schema; arbitrary psychological/personality labels are structurally rejected.
CANONICAL_RELATIONSHIPS_PATTERN_KINDS: tuple[str, ...] = (
    PATTERN_APPROACH_DISTANCE_CYCLE,
    PATTERN_CONFLICT_REPAIR_CYCLE,
    PATTERN_REPEATED_CANCELLATION,
    PATTERN_SUPPORT_ASYMMETRY,
    PATTERN_FREQUENCY_CHANGE,
    PATTERN_BOUNDARY_CONFLICT,
    PATTERN_COMMITMENT_NON_FULFILMENT,
)
CANONICAL_RELATIONSHIPS_PATTERN_KIND_SET: frozenset[str] = frozenset(
    CANONICAL_RELATIONSHIPS_PATTERN_KINDS
)

# ── Closed boundary consistency states (spec §13) ─────────────────────────────

BOUNDARY_EXPRESSED = "expressed"
BOUNDARY_ACKNOWLEDGED = "acknowledged"
BOUNDARY_APPLIED = "applied"
BOUNDARY_VIOLATED = "violated"
BOUNDARY_CHANGED = "changed"
BOUNDARY_CONTRADICTORY = "contradictory"
BOUNDARY_UNRESOLVED = "unresolved"

# ── Closed self/other perspective categories (spec §11) ───────────────────────

PERSPECTIVE_SELF_EXPERIENCE = "self_experience"
PERSPECTIVE_OTHER_OBSERVABLE = "other_observable_behavior"
PERSPECTIVE_OTHER_POSSIBLE = "possible_other_perspective"
PERSPECTIVE_UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════════════════════
# Pure deterministic relationship helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _usable_reference(value: Any) -> str | None:
    """Return a usable reference identifier from a raw value, or ``None``.

    A reference is usable only when it is a non-empty string.  Lists/tuples
    yield the first usable reference.  This deliberately never fabricates a
    placeholder (e.g. ``"unknown"``): an absent or blank reference is
    ``None``, never a fake evidence ID.
    """
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    if isinstance(value, (list, tuple)):
        for item in value:
            usable = _usable_reference(item)
            if usable is not None:
                return usable
    return None


def _reference_from(
    mapping: Mapping,
    *keys: str,
) -> str | None:
    """Extract the first usable reference from ``mapping`` under any of ``keys``."""
    for key in keys:
        value = mapping.get(key)
        usable = _usable_reference(value)
        if usable is not None:
            return usable
    return None


def _normalize_references(values: Any) -> tuple[str, ...]:
    """Normalize a collection of reference IDs into a deterministic,
    order-preserving, de-duplicated tuple of usable references.

    Blank/placeholder IDs are dropped and never count as evidence.  This never
    fabricates a placeholder (e.g. ``"unknown"``) for a missing identifier.
    """
    if isinstance(values, str):
        values = (values,)
    if not isinstance(values, (list, tuple)):
        return ()
    seen: list[str] = []
    seen_set: set[str] = set()
    for value in values:
        usable = _usable_reference(value)
        if usable is not None and usable not in seen_set:
            seen_set.add(usable)
            seen.append(usable)
    return tuple(seen)


def classify_relationship_statement(
    *,
    provenance: str | None = None,
    is_observed: bool = False,
    is_direct_statement: bool = False,
    is_user_interpretation: bool = False,
    is_system_hypothesis: bool = False,
    is_possible_function: bool = False,
    is_possible_origin: bool = False,
    evidence_reference_ids: tuple[str, ...] = (),
) -> str:
    """Classify a relationship statement into a closed epistemic category.

    Deterministic precedence: observed -> direct statement -> interpretation ->
    hypothesis -> possible function -> possible origin -> unknown.

    ``provenance`` records the *origin* of a statement (source origin) and is
    deliberately NOT treated as epistemic evidence.  The mere presence of
    provenance never promotes a user interpretation, system hypothesis, possible
    function, or possible origin into an ``observed_fact``.

    Grounding is fail-closed: an ``observed_fact`` may only be emitted when
    BOTH an explicit ``is_observed`` flag AND at least one usable grounded
    evidence reference (``evidence_reference_ids``) are present.  A bare
    ``is_observed=True`` boolean with no grounded evidence reference never
    bypasses grounding.  When the observed flag is ungrounded, the safe
    epistemic component (interpretation, hypothesis, possible function/origin)
    wins — the factual proposition is only promoted where it is separately
    grounded.

    A ``possible_function`` or ``possible_origin`` is a sub-kind of hypothesis
    and is never promoted to fact or intention.
    """
    if is_observed and _usable_reference(evidence_reference_ids) is not None:
        return EPISTEMIC_CATEGORY_OBSERVED_FACT
    if is_direct_statement:
        return EPISTEMIC_CATEGORY_DIRECT_STATEMENT
    if is_possible_origin:
        return EPISTEMIC_CATEGORY_POSSIBLE_ORIGIN
    if is_possible_function:
        return EPISTEMIC_CATEGORY_POSSIBLE_FUNCTION
    if is_user_interpretation:
        return EPISTEMIC_CATEGORY_USER_INTERPRETATION
    if is_system_hypothesis:
        return EPISTEMIC_CATEGORY_SYSTEM_HYPOTHESIS
    return EPISTEMIC_CATEGORY_UNKNOWN


def classify_relationship_perspective(
    *,
    is_self_experience: bool = False,
    is_other_observable: bool = False,
    is_other_possible: bool = False,
    evidence_reference_ids: tuple[str, ...] = (),
) -> str:
    """Classify a claim into a closed self/other perspective category.

    ``other_observable_behavior`` requires directly observed/documented
    behavior: an ``is_other_observable`` boolean alone never establishes it
    without a grounded evidence reference.  Possible other perspectives are
    never facts: without direct observable evidence the claim is
    ``possible_other_perspective``, and without any information it is
    ``unknown``.
    """
    if is_self_experience:
        return PERSPECTIVE_SELF_EXPERIENCE
    if is_other_observable and _usable_reference(evidence_reference_ids) is not None:
        return PERSPECTIVE_OTHER_OBSERVABLE
    if is_other_possible:
        return PERSPECTIVE_OTHER_POSSIBLE
    return PERSPECTIVE_UNKNOWN


def detect_relationship_pattern(
    *,
    pattern_kind: str,
    support_count: int = 0,
    counterexample_count: int = 0,
    references: tuple[str, ...] = (),
    counterexample_references: tuple[str, ...] = (),
    period_start: str | None = None,
    period_end: str | None = None,
) -> dict:
    """Build a deterministic relationship-pattern hypothesis record.

    A pattern is always a **hypothesis**, never an established fact or cause.
    The record preserves supporting references and counterexamples; a
    counterexample is never silently discarded.  Repetition may strengthen
    confidence in an observational pattern but never establishes motive,
    personality, or psychological cause.

    Pattern kinds are structurally closed: only the canonical seven Phase 10.21
    kinds are accepted.  An unrecognized kind (including any arbitrary
    psychological/personality diagnostic label) is rejected with ``ValueError``
    and can never become a hypothesis.

    Grounding is the source of truth: ``support_count`` and
    ``counterexample_count`` are DERIVED from the usable supporting /
    counterexample reference IDs, never from caller-supplied integers.  A
    caller integer alone cannot generate confidence; with no grounded support
    references the pattern remains an ungrounded hypothesis with high
    uncertainty.
    """
    if pattern_kind not in CANONICAL_RELATIONSHIPS_PATTERN_KIND_SET:
        raise ValueError(
            f"Unknown relationship pattern kind: {pattern_kind!r}. "
            "Only canonical Phase 10.21 pattern kinds are allowed."
        )
    support = _normalize_references(references)
    counter = _normalize_references(counterexample_references)
    support_n = len(support)
    counter_n = len(counter)
    # Simple deterministic uncertainty that accounts for BOTH grounded support
    # and counterevidence: substantial grounded counterexamples temper
    # confidence even when support is high, so certainty is never misleadingly
    # low while real counterevidence exists.
    if support_n < 2 or counter_n >= 2:
        uncertainty = "high"
    elif support_n < 4 or counter_n >= 1:
        uncertainty = "medium"
    else:
        uncertainty = "low"
    return {
        "pattern_kind": pattern_kind,
        "hypothesis": True,
        "support_count": support_n,
        "counterexample_count": counter_n,
        "references": support,
        "counterexample_references": counter,
        "period_start": period_start,
        "period_end": period_end,
        "temporal_range": (period_start, period_end),
        "uncertainty": uncertainty,
        "psychological_cause": None,
    }


def evaluate_boundary_consistency(
    *,
    expressed: bool = False,
    acknowledged: bool = False,
    applied: bool = False,
    violated: bool = False,
    changed: bool = False,
) -> str:
    """Classify a boundary consistency state deterministically.

    Returns one of: ``expressed``, ``acknowledged``, ``applied``, ``violated``,
    ``changed``, ``contradictory``, ``unresolved``.

    A contradiction is identified when a boundary is both applied and violated
    (stated vs applied divergence).  Detecting a contradiction never authorizes
    imposing, communicating, withdrawing, or modifying a boundary.
    """
    if expressed and applied and violated:
        return BOUNDARY_CONTRADICTORY
    if violated:
        return BOUNDARY_VIOLATED
    if applied:
        return BOUNDARY_APPLIED
    if changed:
        return BOUNDARY_CHANGED
    if acknowledged:
        return BOUNDARY_ACKNOWLEDGED
    if expressed:
        return BOUNDARY_EXPRESSED
    return BOUNDARY_UNRESOLVED


def separate_emotion_need_expectation(
    *,
    statements: tuple = (),
) -> dict:
    """Separate user statements into emotion, need, desire, expectation,
    interpretation, and behavior buckets.

    Brute deterministic separation: each statement may carry flags for each
    bucket.  A statement can be classified into multiple buckets; no bucket is
    inferred from another (an emotion is not a need, a need is not an
    expectation).
    """
    result = {
        "emotions": [],
        "needs": [],
        "desires": [],
        "expectations": [],
        "interpretations": [],
        "behaviors": [],
    }
    for statement in statements:
        if not isinstance(statement, Mapping):
            continue
        # Only a real, usable statement id may represent the item in a bucket.
        # A missing/blank id is never replaced with a fabricated placeholder
        # ("unknown") that could later leak into reference collections.
        statement_id = _usable_reference(statement.get("id"))
        if statement_id is None:
            continue
        if statement.get("emotion"):
            result["emotions"].append(statement_id)
        if statement.get("need"):
            result["needs"].append(statement_id)
        if statement.get("desire"):
            result["desires"].append(statement_id)
        if statement.get("expectation"):
            result["expectations"].append(statement_id)
        if statement.get("interpretation"):
            result["interpretations"].append(statement_id)
        if statement.get("behavior"):
            result["behaviors"].append(statement_id)
    return result


def preserve_relationship_ambivalence(
    *,
    wants_closeness: bool = False,
    wants_distance: bool = False,
    misses_person: bool = False,
    relief_without_contact: bool = False,
) -> dict:
    """Preserve simultaneous contradictory feelings as structured information.

    Ambivalence is first-class information, not an inconsistency to resolve.
    The system never collapses these into a single relational objective and
    never decides leave / reconcile / distance / resume on the user's behalf.
    """
    coexisting = []
    if wants_closeness:
        coexisting.append("wants_closeness")
    if wants_distance:
        coexisting.append("wants_distance")
    if misses_person:
        coexisting.append("misses_person")
    if relief_without_contact:
        coexisting.append("relief_without_contact")
    # Both approved ambivalence pairs are first-class: the pull toward closeness
    # while wanting distance, and the simultaneous miss + relief at no contact.
    contradictory = (wants_closeness and wants_distance) or (
        misses_person and relief_without_contact
    )
    return {
        "feelings": tuple(coexisting),
        "ambivalent": contradictory,
        "preserved": True,
        "forced_objective": None,
        "requires_confirmation_for_decision": True,
    }


def compare_relationship_options(
    *,
    options: tuple = (),
    criteria: tuple = (),
) -> dict:
    """Compare candidate options against the user's EXPLICIT criteria.

    Decision Support Mode A (spec §26): the helper may enumerate options, use
    explicit user criteria, compare options, and identify which option best
    matches the user's explicit criteria.  It never adopts an option as a
    decision, never persists it as decided, and never converts a recommendation
    into a commitment.  A relational decision becomes explicit only after user
    confirmation.
    """
    criteria_list = tuple(criteria)
    scored: list[dict] = []
    for option in options:
        if not isinstance(option, Mapping):
            continue
        option_id = option.get("id", "unknown")
        option_criteria = option.get("criteria", ())
        if not isinstance(option_criteria, (list, tuple)):
            option_criteria = ()
        matches = tuple(
            criterion for criterion in criteria_list if criterion in option_criteria
        )
        scored.append(
            {
                "option_id": option_id,
                "matches": matches,
                "match_count": len(matches),
                "total_criteria": len(criteria_list),
            }
        )
    best = None
    tied: tuple[str, ...] = ()
    if scored and criteria_list:
        max_count = max((s["match_count"] for s in scored), default=0)
        if max_count > 0:
            top = [s for s in scored if s["match_count"] == max_count]
            tied = tuple(s["option_id"] for s in top)
            if len(top) == 1:
                best = dict(top[0])
                best["statement"] = (
                    f"Option {best['option_id']} currently matches "
                    f"{best['match_count']}/{best['total_criteria']} criteria "
                    "you explicitly prioritized."
                )
    return {
        "options": tuple(scored),
        "criteria": criteria_list,
        "best_match": best,
        "tied_best_matches": tied,
        "adopted_decision": False,
        "requires_user_confirmation": True,
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
        domain_id="domain:relationships",
        category=category,
        status=ReasoningRuleStatus.ENABLED,
        priority=priority,
        risk_level=risk_level,
        deterministic=True,
        description=f"Conservative relationship rule for {rule_id}.",
        metadata={"phase": "10.21"},
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
# SeparateRelationshipFactInterpretationRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class SeparateRelationshipFactInterpretationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        statements = _seq(context.metadata, "relationship_statements")
        if not statements:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No relationship statements supplied.",
            )
        findings: list[ReasoningFinding] = []
        for statement in statements:
            if not isinstance(statement, Mapping):
                continue
            statement_id = _usable_reference(statement.get("id"))
            category = classify_relationship_statement(
                provenance=statement.get("provenance"),
                is_observed=bool(statement.get("observed")),
                is_direct_statement=bool(statement.get("direct_statement")),
                is_user_interpretation=bool(statement.get("user_interpretation")),
                is_system_hypothesis=bool(statement.get("system_hypothesis")),
                is_possible_function=bool(statement.get("possible_function")),
                is_possible_origin=bool(statement.get("possible_origin")),
                evidence_reference_ids=tuple(
                    statement.get("evidence_references", ()) or ()
                ),
            )
            # A missing/blank id is never replaced with a fabricated
            # placeholder reference; the finding simply carries no reference.
            references = (statement_id,) if statement_id is not None else ()
            findings.append(
                ReasoningFinding(
                    code="EPISTEMIC_CATEGORY",
                    message=f"Statement {statement_id} classified as {category}.",
                    severity=ReasoningSeverity.INFO,
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                    references=references,
                )
            )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="EPISTEMIC_CATEGORIES_ASSIGNED",
            message="Epistemic categories assigned without promotion.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# DoNotInferIntentRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class DoNotInferIntentRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        intent = _mapping(context.metadata, "intent_claim")
        if intent is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No intent claim metadata supplied.",
            )
        has_direct_evidence = bool(intent.get("direct_evidence"))
        is_sourced_statement = bool(intent.get("sourced_statement"))
        # Grounding is fail-closed: a bare boolean never bypasses grounding and
        # no placeholder reference is ever fabricated.  Direct evidence requires
        # an evidence/source reference; a sourced statement requires a real
        # source reference.
        direct_reference = _reference_from(
            intent,
            "evidence_reference",
            "source_reference",
            "references",
            "evidence_references",
        )
        source_reference = _reference_from(
            intent, "source_reference", "source", "references"
        )
        if has_direct_evidence and direct_reference is not None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                code="INTENT_DIRECTLY_EVIDENCED",
                message="Intent is directly evidenced/attributed by an authorized source.",
            )
        if is_sourced_statement and source_reference is not None:
            finding = ReasoningFinding(
                code="INTENT_SOURCED_NOT_FACT",
                message="A source states this intention; it is represented with provenance, not as system fact.",
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                references=(source_reference,),
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
                code="INTENT_SOURCED_STATEMENT",
                message="Intention represented as a sourced statement, not as fact.",
            )
        finding = ReasoningFinding(
            code="INTENT_NOT_ESTABLISHED",
            message="Intention cannot be established without grounded evidence or a sourced reference.",
            severity=ReasoningSeverity.WARNING,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
        )

        # A tentative interpretation with no claimed grounding may remain a
        # hypothesis.  But once the caller explicitly claims direct evidence
        # or a sourced statement, the corresponding reference is mandatory:
        # missing provenance is an invalid grounding claim, not uncertainty.
        grounding_claim_invalid = (
            (has_direct_evidence and direct_reference is None)
            or (is_sourced_statement and source_reference is None)
        )
        if grounding_claim_invalid:
            escalation = ReasoningEscalation(
                code="INTENT_BLOCKED",
                message=(
                    "Claimed grounding is incomplete; unsupported intention "
                    "attribution must not be presented as evidenced fact."
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
                code="INTENT_BLOCKED",
                message="Claimed intent grounding is incomplete; blocked.",
            )

        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="INTENT_HYPOTHESIS_RETAINED",
            message=(
                "Intention is not established as fact; "
                "it may remain a qualified hypothesis."
            ),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# RelationshipTimelineRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class RelationshipTimelineRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        timeline = _seq(context.metadata, "timeline")
        if not timeline:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No timeline items supplied.",
            )
        findings: list[ReasoningFinding] = []
        for item in timeline:
            if not isinstance(item, Mapping):
                continue
            item_id = _usable_reference(item.get("id"))
            kind = item.get("kind", "unknown")
            references = (item_id,) if item_id is not None else ()
            findings.append(
                ReasoningFinding(
                    code="TIMELINE_ITEM",
                    message=f"Timeline item {item_id} of kind {kind}.",
                    severity=ReasoningSeverity.INFO,
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                    references=references,
                )
            )
        # Temporal proximity is not causation: a change following an event is
        # recorded as an ordering, never as a reason derived from timing alone.
        gaps = (
            ReasoningGap(
                code="TEMPORAL_PROXIMITY_NOT_CAUSE",
                message=(
                    "Temporal ordering is recorded; proximity does not imply "
                    "causation or motive."
                ),
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            ),
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            gaps=gaps,
            code="TIMELINE_ORDERED",
            message="Timeline ordered without inferring motive from timing.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# PatternWithoutCertaintyRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class PatternWithoutCertaintyRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        pattern = _mapping(context.metadata, "pattern")
        if pattern is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No pattern metadata supplied.",
            )
        kind = str(pattern.get("pattern_kind", "unknown"))
        # The pattern taxonomy is structurally closed: an arbitrary
        # psychological/personality label is blocked and never becomes a
        # PATTERN_HYPOTHESIS.
        if kind not in CANONICAL_RELATIONSHIPS_PATTERN_KIND_SET:
            finding = ReasoningFinding(
                code="PATTERN_KIND_REJECTED",
                message=(
                    f"Pattern kind {kind!r} is not a canonical Phase 10.21 "
                    "relationship pattern kind and is blocked."
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
                code="PATTERN_KIND_REJECTED",
                message="Unsupported pattern kind blocked.",
            )
        record = detect_relationship_pattern(
            pattern_kind=kind,
            support_count=int(pattern.get("support_count", 0)),
            counterexample_count=int(pattern.get("counterexample_count", 0)),
            references=tuple(pattern.get("references", ()) or ()),
            counterexample_references=tuple(
                pattern.get("counterexample_references", ()) or ()
            ),
            period_start=pattern.get("period_start"),
            period_end=pattern.get("period_end"),
        )
        finding = ReasoningFinding(
            code="PATTERN_HYPOTHESIS",
            message=(
                f"Pattern {record['pattern_kind']} is a hypothesis with "
                f"support {record['support_count']} and counterexamples "
                f"{record['counterexample_count']}; it does not establish "
                "motive, personality, or psychological cause."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            references=record["references"],
            metadata={
                "counterexample_references": record["counterexample_references"],
                "counterexample_count": record["counterexample_count"],
                "uncertainty": record["uncertainty"],
            },
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="PATTERN_HYPOTHESIS_RECORDED",
            message="Pattern recorded as a hypothesis with preserved evidence and uncertainty.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# EmotionNeedDistinctionRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class EmotionNeedDistinctionRule:
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
        separated = separate_emotion_need_expectation(statements=tuple(statements))
        findings: list[ReasoningFinding] = []
        for bucket, items in separated.items():
            if items:
                findings.append(
                    ReasoningFinding(
                        code="DISTINCT_CATEGORY",
                        message=f"{bucket}: {', '.join(items)}.",
                        severity=ReasoningSeverity.INFO,
                        rule_id=self.definition.id,
                        domain_id=self.definition.domain_id,
                        references=tuple(items),
                    )
                )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="CATEGORIES_SEPARATED",
            message="Emotions, needs, desires, expectations, and behaviors kept distinct.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# BoundaryConsistencyRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class BoundaryConsistencyRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        boundary = _mapping(context.metadata, "boundary")
        if boundary is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No boundary metadata supplied.",
            )
        state = evaluate_boundary_consistency(
            expressed=bool(boundary.get("expressed")),
            acknowledged=bool(boundary.get("acknowledged")),
            applied=bool(boundary.get("applied")),
            violated=bool(boundary.get("violated")),
            changed=bool(boundary.get("changed")),
        )
        boundary_id = _usable_reference(boundary.get("id"))
        references = (boundary_id,) if boundary_id is not None else ()
        finding = ReasoningFinding(
            code="BOUNDARY_STATE",
            message=f"Boundary consistency state: {state}.",
            severity=ReasoningSeverity.WARNING
            if state in (BOUNDARY_CONTRADICTORY, BOUNDARY_VIOLATED)
            else ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            references=references,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="BOUNDARY_CONSISTENCY_EVALUATED",
            message="Boundary consistency evaluated; no autonomous boundary action.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AmbivalencePreservationRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AmbivalencePreservationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        # Decision Support Mode A path: the rule that owns preservation of
        # decision ambiguity also carries the option/criteria comparison.  It
        # retains the comparison and never adopts a decision or drops the
        # confirmation requirement.
        decision_support = _mapping(context.metadata, "decision_support")
        if decision_support is not None:
            comparison = compare_relationship_options(
                options=tuple(decision_support.get("options", ()) or ()),
                criteria=tuple(decision_support.get("criteria", ()) or ()),
            )
            finding = ReasoningFinding(
                code="DECISION_SUPPORT_COMPARISON",
                message=(
                    "Candidate options compared against explicit criteria; no "
                    "relational decision is adopted."
                ),
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                metadata={"comparison": comparison},
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
                code="DECISION_SUPPORT_COMPARISON",
                message="Options compared; decision ambiguity preserved.",
            )
        ambivalence = _mapping(context.metadata, "ambivalence")
        if ambivalence is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No ambivalence metadata supplied.",
            )
        record = preserve_relationship_ambivalence(
            wants_closeness=bool(ambivalence.get("wants_closeness")),
            wants_distance=bool(ambivalence.get("wants_distance")),
            misses_person=bool(ambivalence.get("misses_person")),
            relief_without_contact=bool(ambivalence.get("relief_without_contact")),
        )
        finding = ReasoningFinding(
            code="AMBIVALENCE_PRESERVED",
            message=f"Coexisting feelings preserved: {', '.join(record['feelings'])}.",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="AMBIVALENCE_PRESERVED",
            message="Ambivalence preserved; no forced relational objective.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SelfOtherPerspectiveRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class SelfOtherPerspectiveRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        # Third-party diagnosis policy: the domain never diagnoses a third party
        # on its own.  A structured claim is blocked unless an authorized source
        # explicitly states the diagnosis, in which case it is represented as a
        # *sourced statement* with provenance — never adopted as a system
        # diagnosis.  The rule enforces this on the structured claim semantics,
        # not on the label text (no medical keyword detector).
        diagnosis_claim = _mapping(context.metadata, "third_party_diagnosis_claim")
        if diagnosis_claim is not None:
            label = str(diagnosis_claim.get("label", "unspecified"))
            source_statement = bool(diagnosis_claim.get("source_statement"))
            source_reference = _reference_from(
                diagnosis_claim, "source_reference", "source", "references"
            )
            if not source_statement or source_reference is None:
                finding = ReasoningFinding(
                    code="THIRD_PARTY_DIAGNOSIS_UNSUPPORTED",
                    message=(
                        f"Unsupported or ungrounded third-party diagnosis claim "
                        f"({label}) is blocked; it is not a system diagnosis."
                    ),
                    severity=ReasoningSeverity.WARNING,
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                    metadata={"adopted_as_system_diagnosis": False},
                )
                escalation = ReasoningEscalation(
                    code="THIRD_PARTY_DIAGNOSIS_BLOCKED",
                    message="Third-party diagnosis is blocked; it must not be presented as fact.",
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
                    code="THIRD_PARTY_DIAGNOSIS_BLOCKED",
                    message="Unsupported third-party diagnosis blocked.",
                )
            # Authorized source states the diagnosis with a real source reference:
            # represent with provenance, never adopt as a system diagnosis.
            finding = ReasoningFinding(
                code="THIRD_PARTY_DIAGNOSIS_SOURCED",
                message=(
                    f"A source states '{label}' for a third party; it is "
                    "represented with provenance, not adopted as a system "
                    "diagnosis."
                ),
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                references=(source_reference,),
                metadata={"adopted_as_system_diagnosis": False},
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
                code="THIRD_PARTY_DIAGNOSIS_SOURCED",
                message="Third-party diagnosis represented as a sourced statement only.",
            )
        claims = _seq(context.metadata, "perspective_claims")
        if not claims:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No perspective claims supplied.",
            )
        findings: list[ReasoningFinding] = []
        gaps: list[ReasoningGap] = []
        for claim in claims:
            if not isinstance(claim, Mapping):
                continue
            claim_id = _usable_reference(claim.get("id"))
            claim_references = (claim_id,) if claim_id is not None else ()
            perspective = classify_relationship_perspective(
                is_self_experience=bool(claim.get("self_experience")),
                is_other_observable=bool(claim.get("other_observable")),
                is_other_possible=bool(claim.get("other_possible")),
                evidence_reference_ids=tuple(
                    claim.get("evidence_references", ()) or ()
                ),
            )
            if perspective == PERSPECTIVE_UNKNOWN:
                gaps.append(
                    ReasoningGap(
                        code="OTHER_PERSPECTIVE_UNKNOWN",
                        message="I cannot establish why they did this.",
                        severity=ReasoningSeverity.WARNING,
                        rule_id=self.definition.id,
                        domain_id=self.definition.domain_id,
                        references=claim_references,
                    )
                )
            else:
                findings.append(
                    ReasoningFinding(
                        code="PERSPECTIVE_CATEGORY",
                        message=f"Claim {claim_id} classified as {perspective}.",
                        severity=ReasoningSeverity.INFO,
                        rule_id=self.definition.id,
                        domain_id=self.definition.domain_id,
                        references=claim_references,
                    )
                )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            gaps=tuple(gaps),
            code="PERSPECTIVES_SEPARATED",
            message="Self experience, other observable behavior, possible other perspective, and unknown kept distinct.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════════════


def build_relationships_rules() -> tuple[Any, ...]:
    """Build the eight Relationships Domain rules deterministically in canonical order."""
    by_id = {
        "relationships.ambivalence_preservation": AmbivalencePreservationRule(
            definition=_definition(
                "relationships.ambivalence_preservation",
                "AmbivalencePreservationRule",
                ReasoningRuleCategory.INFERENCE.value,
                770,
            )
        ),
        "relationships.boundary_consistency": BoundaryConsistencyRule(
            definition=_definition(
                "relationships.boundary_consistency",
                "BoundaryConsistencyRule",
                ReasoningRuleCategory.CONSISTENCY.value,
                750,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "relationships.do_not_infer_intent": DoNotInferIntentRule(
            definition=_definition(
                "relationships.do_not_infer_intent",
                "DoNotInferIntentRule",
                ReasoningRuleCategory.SAFETY.value,
                810,
                risk_level=ReasoningRiskLevel.HIGH,
            )
        ),
        "relationships.emotion_need_distinction": EmotionNeedDistinctionRule(
            definition=_definition(
                "relationships.emotion_need_distinction",
                "EmotionNeedDistinctionRule",
                ReasoningRuleCategory.INFERENCE.value,
                760,
            )
        ),
        "relationships.pattern_without_certainty": PatternWithoutCertaintyRule(
            definition=_definition(
                "relationships.pattern_without_certainty",
                "PatternWithoutCertaintyRule",
                ReasoningRuleCategory.EPISTEMIC.value,
                730,
            )
        ),
        "relationships.relationship_timeline": RelationshipTimelineRule(
            definition=_definition(
                "relationships.relationship_timeline",
                "RelationshipTimelineRule",
                ReasoningRuleCategory.TEMPORALITY.value,
                740,
            )
        ),
        "relationships.separate_facts_interpretations": SeparateRelationshipFactInterpretationRule(
            definition=_definition(
                "relationships.separate_facts_interpretations",
                "SeparateRelationshipFactInterpretationRule",
                ReasoningRuleCategory.EPISTEMIC.value,
                720,
            )
        ),
        "relationships.self_other_perspective": SelfOtherPerspectiveRule(
            definition=_definition(
                "relationships.self_other_perspective",
                "SelfOtherPerspectiveRule",
                ReasoningRuleCategory.SAFETY.value,
                800,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
    }
    return tuple(by_id[rule_id] for rule_id in RELATIONSHIPS_RULE_IDS)


__all__ = [
    "BOUNDARY_ACKNOWLEDGED",
    "BOUNDARY_APPLIED",
    "BOUNDARY_CHANGED",
    "BOUNDARY_CONTRADICTORY",
    "BOUNDARY_EXPRESSED",
    "BOUNDARY_UNRESOLVED",
    "BOUNDARY_VIOLATED",
    "CANONICAL_RELATIONSHIPS_PATTERN_KINDS",
    "CANONICAL_RELATIONSHIPS_PATTERN_KIND_SET",
    "EPISTEMIC_CATEGORY_DIRECT_STATEMENT",
    "EPISTEMIC_CATEGORY_OBSERVED_FACT",
    "EPISTEMIC_CATEGORY_POSSIBLE_FUNCTION",
    "EPISTEMIC_CATEGORY_POSSIBLE_ORIGIN",
    "EPISTEMIC_CATEGORY_SYSTEM_HYPOTHESIS",
    "EPISTEMIC_CATEGORY_UNKNOWN",
    "EPISTEMIC_CATEGORY_USER_INTERPRETATION",
    "PATTERN_APPROACH_DISTANCE_CYCLE",
    "PATTERN_BOUNDARY_CONFLICT",
    "PATTERN_COMMITMENT_NON_FULFILMENT",
    "PATTERN_CONFLICT_REPAIR_CYCLE",
    "PATTERN_FREQUENCY_CHANGE",
    "PATTERN_REPEATED_CANCELLATION",
    "PATTERN_SUPPORT_ASYMMETRY",
    "PERSPECTIVE_OTHER_OBSERVABLE",
    "PERSPECTIVE_OTHER_POSSIBLE",
    "PERSPECTIVE_SELF_EXPERIENCE",
    "PERSPECTIVE_UNKNOWN",
    "RELATIONSHIPS_RULE_IDS",
    "AmbivalencePreservationRule",
    "BoundaryConsistencyRule",
    "DoNotInferIntentRule",
    "EmotionNeedDistinctionRule",
    "PatternWithoutCertaintyRule",
    "RelationshipTimelineRule",
    "SelfOtherPerspectiveRule",
    "SeparateRelationshipFactInterpretationRule",
    "build_relationships_rules",
    "classify_relationship_perspective",
    "classify_relationship_statement",
    "compare_relationship_options",
    "detect_relationship_pattern",
    "evaluate_boundary_consistency",
    "preserve_relationship_ambivalence",
    "separate_emotion_need_expectation",
]
