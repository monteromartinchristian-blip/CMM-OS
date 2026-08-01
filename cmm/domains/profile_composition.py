"""Phase 10.11 – Domain Profile Composition.

Pure, deterministic composition of a ``DomainProfileDraft`` from a global
profile, a primary-domain profile, supporting-domain profiles, and overlays.

The composer performs no I/O, generates no identifiers or timestamps, and
has no registry access. Every merge rule is monotonic: mandatory rules
cannot be deactivated, prohibitions prevail, permissions only narrow,
confidence thresholds never decrease, and numeric limits only tighten.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.enums import (
    DomainProfileConflictSeverity,
    DomainProfileDecisionCode,
    DomainProfileSource,
    DomainReasoningDepth,
)
from cmm.domains.profile_contracts import (
    DETAIL_LEVEL_ORDER,
    RETENTION_SCOPE_ORDER,
    DomainMemoryPolicy,
    DomainPresentationPolicy,
    DomainProductionPolicy,
    DomainProfileCompositionResult,
    DomainProfileConflict,
    DomainProfileDecision,
    DomainProfileDefinition,
    DomainProfileDraft,
    DomainProfileModification,
    DomainProfileOverlay,
    DomainProfileRejection,
    DomainQuestionPolicy,
    DomainTemporalPolicy,
)

_SOURCE_PRECEDENCE: tuple[DomainProfileSource, ...] = (
    DomainProfileSource.GLOBAL_POLICY,
    DomainProfileSource.PRIMARY_DOMAIN,
    DomainProfileSource.SUPPORTING_DOMAIN,
    DomainProfileSource.WORKFLOW,
    DomainProfileSource.OPERATION,
    DomainProfileSource.RISK,
    DomainProfileSource.ACTOR,
    DomainProfileSource.AUTONOMY,
    DomainProfileSource.EXPLICIT_REQUEST,
)

_REASONING_DEPTH_ORDER: tuple[DomainReasoningDepth, ...] = tuple(DomainReasoningDepth)
_SENSITIVITY_ORDER: tuple[SensitivityLevel, ...] = tuple(SensitivityLevel)


def _precedence_index(source: DomainProfileSource) -> int:
    return _SOURCE_PRECEDENCE.index(source)


# ═══════════════════════════════════════════════════════════════════════════════
# Pure collection merge helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _ordered_union(*sequences: tuple[str, ...]) -> tuple[str, ...]:
    """Union preserving first-appearance order across all sequences."""
    seen: set[str] = set()
    result: list[str] = []
    for seq in sequences:
        for item in seq:
            if item not in seen:
                seen.add(item)
                result.append(item)
    return tuple(result)


def _ordered_difference(
    base: tuple[str, ...], *removals: tuple[str, ...]
) -> tuple[str, ...]:
    remove_set: set[str] = set()
    for removal in removals:
        remove_set.update(removal)
    return tuple(item for item in base if item not in remove_set)


def _ordered_intersection(a: tuple[str, ...], b: tuple[str, ...]) -> tuple[str, ...]:
    b_set = set(b)
    return tuple(item for item in a if item in b_set)


def _fold_restrictive_constraint(
    current: tuple[str, ...] | None, incoming: tuple[str, ...] | None
) -> tuple[str, ...] | None:
    """Restrictive intersection fold for "allowed"/"permitted" style fields.

    ``None`` means unconstrained (a universal set) and never participates in
    the intersection. An explicit empty tuple means "permit none" and is
    absorbing: once reached, it stays empty forever.
    """
    if incoming is None:
        return current
    if current is None:
        return incoming
    return _ordered_intersection(current, incoming)


_DENY_PERMISSION_PREFIX = "deny:"


def _split_state_permissions(
    permissions: tuple[str, ...] | None,
) -> tuple[tuple[str, ...] | None, tuple[str, ...]]:
    """Split an effective permission tuple into (grants, denies).

    ``None`` means unconstrained and ``()`` means explicitly none. A tuple
    holding only ``deny:<permission>`` entries is read conservatively as
    "explicitly none plus denies": once denies were applied and no grant
    remains, the effective grant set is empty.
    """
    if permissions is None:
        return None, ()
    denies = tuple(p for p in permissions if p.startswith(_DENY_PERMISSION_PREFIX))
    grants = tuple(p for p in permissions if not p.startswith(_DENY_PERMISSION_PREFIX))
    if not grants and denies:
        return (), denies
    return grants, denies


def _split_incoming_permissions(
    permissions: tuple[str, ...],
) -> tuple[tuple[str, ...] | None, tuple[str, ...]]:
    """Split a contributed permission tuple into (grants, denies).

    A contribution holding only ``deny:<permission>`` entries does not
    constrain the grant universe; it only removes the denied permissions.
    """
    denies = tuple(p for p in permissions if p.startswith(_DENY_PERMISSION_PREFIX))
    grants = tuple(p for p in permissions if not p.startswith(_DENY_PERMISSION_PREFIX))
    if not grants and denies:
        return None, denies
    return grants, denies


def _fold_permissions(
    current: tuple[str, ...] | None, incoming: tuple[str, ...] | None
) -> tuple[str, ...] | None:
    """Restrictive permission fold where an explicit ``deny:<permission>`` prevails.

    ``None`` means unconstrained and an empty tuple means "explicitly none",
    exactly like :func:`_fold_restrictive_constraint`. Grants only narrow
    through the restrictive intersection; ``deny:<permission>`` entries
    accumulate across sources and remove the corresponding granted
    ``<permission>``: an explicit deny always wins over a grant. Deny entries
    are retained so the denial stays visible and auditable, and permissions
    can never be widened by any source.
    """
    if incoming is None:
        return current
    current_grants, current_denies = _split_state_permissions(current)
    incoming_grants, incoming_denies = _split_incoming_permissions(incoming)
    grants = _fold_restrictive_constraint(current_grants, incoming_grants)
    denies = _ordered_union(current_denies, incoming_denies)
    if grants is not None and denies:
        denied_targets = {d[len(_DENY_PERMISSION_PREFIX) :] for d in denies}
        grants = tuple(g for g in grants if g not in denied_targets)
    if grants is None:
        return denies if denies else None
    return grants + denies


def _pick_most_restrictive_high_index(
    order: tuple[str, ...], current: str | None, incoming: str | None
) -> str | None:
    """Most restrictive = highest index in ``order`` (detail level, retention scope)."""
    if incoming is None:
        return current
    if current is None:
        return incoming
    return incoming if order.index(incoming) > order.index(current) else current


def _pick_most_restrictive_low_index(
    order: tuple[Any, ...], current: Any, incoming: Any
) -> Any:
    """Most restrictive = lowest index in ``order`` (reasoning depth, sensitivity)."""
    if incoming is None:
        return current
    return incoming if order.index(incoming) < order.index(current) else current


def _and_bool(current: bool | None, incoming: bool | None) -> bool | None:
    """Capability booleans: logical AND, never silently broadened."""
    if incoming is None:
        return current
    if current is None:
        return incoming
    return current and incoming


def _or_bool(current: bool | None, incoming: bool | None) -> bool | None:
    """Safety-behavior booleans: logical OR, never silently weakened."""
    if incoming is None:
        return current
    if current is None:
        return incoming
    return current or incoming


def _min_non_null(current: float | None, incoming: float | None) -> float | None:
    if incoming is None:
        return current
    if current is None:
        return incoming
    return min(current, incoming)


def _max_non_null(current: float | None, incoming: float | None) -> float | None:
    if incoming is None:
        return current
    if current is None:
        return incoming
    return max(current, incoming)


# ═══════════════════════════════════════════════════════════════════════════════
# Typed policy merge functions
# ═══════════════════════════════════════════════════════════════════════════════

_PolicyChange = tuple[str, str, Any, Any]  # (field, operation, previous, new)


def merge_question_policy(
    current: DomainQuestionPolicy, incoming: DomainQuestionPolicy | None
) -> tuple[DomainQuestionPolicy, tuple[_PolicyChange, ...]]:
    if incoming is None:
        return current, ()
    changes: list[_PolicyChange] = []
    maximum_questions = _min_non_null(
        current.maximum_questions, incoming.maximum_questions
    )
    if maximum_questions != current.maximum_questions:
        changes.append(
            ("maximum_questions", "min", current.maximum_questions, maximum_questions)
        )
    allow_follow_up = _and_bool(current.allow_follow_up, incoming.allow_follow_up)
    if allow_follow_up != current.allow_follow_up:
        changes.append(
            ("allow_follow_up", "and", current.allow_follow_up, allow_follow_up)
        )
    require_deduplication = _or_bool(
        current.require_deduplication, incoming.require_deduplication
    )
    if require_deduplication != current.require_deduplication:
        changes.append(
            (
                "require_deduplication",
                "or",
                current.require_deduplication,
                require_deduplication,
            )
        )
    allow_clarification = _and_bool(
        current.allow_clarification, incoming.allow_clarification
    )
    if allow_clarification != current.allow_clarification:
        changes.append(
            (
                "allow_clarification",
                "and",
                current.allow_clarification,
                allow_clarification,
            )
        )
    stop_on_blocking_gap = _or_bool(
        current.stop_on_blocking_gap, incoming.stop_on_blocking_gap
    )
    if stop_on_blocking_gap != current.stop_on_blocking_gap:
        changes.append(
            (
                "stop_on_blocking_gap",
                "or",
                current.stop_on_blocking_gap,
                stop_on_blocking_gap,
            )
        )
    merged = replace(
        current,
        maximum_questions=maximum_questions,
        allow_follow_up=allow_follow_up,
        require_deduplication=require_deduplication,
        allow_clarification=allow_clarification,
        stop_on_blocking_gap=stop_on_blocking_gap,
    )
    return merged, tuple(changes)


def merge_presentation_policy(
    current: DomainPresentationPolicy, incoming: DomainPresentationPolicy | None
) -> tuple[DomainPresentationPolicy, tuple[_PolicyChange, ...]]:
    if incoming is None:
        return current, ()
    changes: list[_PolicyChange] = []
    detail_level = _pick_most_restrictive_high_index(
        DETAIL_LEVEL_ORDER, current.detail_level, incoming.detail_level
    )
    if detail_level != current.detail_level:
        changes.append(
            ("detail_level", "restrictive_order", current.detail_level, detail_level)
        )
    include_uncertainty = _or_bool(
        current.include_uncertainty, incoming.include_uncertainty
    )
    if include_uncertainty != current.include_uncertainty:
        changes.append(
            (
                "include_uncertainty",
                "or",
                current.include_uncertainty,
                include_uncertainty,
            )
        )
    include_provenance = _or_bool(
        current.include_provenance, incoming.include_provenance
    )
    if include_provenance != current.include_provenance:
        changes.append(
            ("include_provenance", "or", current.include_provenance, include_provenance)
        )
    include_alternatives = _and_bool(
        current.include_alternatives, incoming.include_alternatives
    )
    if include_alternatives != current.include_alternatives:
        changes.append(
            (
                "include_alternatives",
                "and",
                current.include_alternatives,
                include_alternatives,
            )
        )
    allow_speculation = _and_bool(current.allow_speculation, incoming.allow_speculation)
    if allow_speculation != current.allow_speculation:
        changes.append(
            ("allow_speculation", "and", current.allow_speculation, allow_speculation)
        )
    require_disclaimers = _or_bool(
        current.require_disclaimers, incoming.require_disclaimers
    )
    if require_disclaimers != current.require_disclaimers:
        changes.append(
            (
                "require_disclaimers",
                "or",
                current.require_disclaimers,
                require_disclaimers,
            )
        )
    merged = replace(
        current,
        detail_level=detail_level,
        include_uncertainty=include_uncertainty,
        include_provenance=include_provenance,
        include_alternatives=include_alternatives,
        allow_speculation=allow_speculation,
        require_disclaimers=require_disclaimers,
    )
    return merged, tuple(changes)


def merge_memory_policy(
    current: DomainMemoryPolicy, incoming: DomainMemoryPolicy | None
) -> tuple[DomainMemoryPolicy, tuple[_PolicyChange, ...]]:
    if incoming is None:
        return current, ()
    changes: list[_PolicyChange] = []
    allow_read = _and_bool(current.allow_read, incoming.allow_read)
    if allow_read != current.allow_read:
        changes.append(("allow_read", "and", current.allow_read, allow_read))
    allow_write = _and_bool(current.allow_write, incoming.allow_write)
    if allow_write != current.allow_write:
        changes.append(("allow_write", "and", current.allow_write, allow_write))
    allow_long_term = _and_bool(current.allow_long_term, incoming.allow_long_term)
    if allow_long_term != current.allow_long_term:
        changes.append(
            ("allow_long_term", "and", current.allow_long_term, allow_long_term)
        )
    allow_cross_domain = _and_bool(
        current.allow_cross_domain, incoming.allow_cross_domain
    )
    if allow_cross_domain != current.allow_cross_domain:
        changes.append(
            (
                "allow_cross_domain",
                "and",
                current.allow_cross_domain,
                allow_cross_domain,
            )
        )
    retention_scope = _pick_most_restrictive_low_index(
        RETENTION_SCOPE_ORDER, current.retention_scope, incoming.retention_scope
    )
    if retention_scope != current.retention_scope:
        changes.append(
            (
                "retention_scope",
                "restrictive_order",
                current.retention_scope,
                retention_scope,
            )
        )
    sensitivity_limit = _pick_most_restrictive_low_index(
        _SENSITIVITY_ORDER, current.sensitivity_limit, incoming.sensitivity_limit
    )
    if sensitivity_limit != current.sensitivity_limit:
        changes.append(
            (
                "sensitivity_limit",
                "restrictive_order",
                current.sensitivity_limit,
                sensitivity_limit,
            )
        )
    merged = replace(
        current,
        allow_read=allow_read,
        allow_write=allow_write,
        allow_long_term=allow_long_term,
        allow_cross_domain=allow_cross_domain,
        retention_scope=retention_scope,
        sensitivity_limit=sensitivity_limit,
    )
    return merged, tuple(changes)


def merge_temporal_policy(
    current: DomainTemporalPolicy, incoming: DomainTemporalPolicy | None
) -> tuple[DomainTemporalPolicy, tuple[_PolicyChange, ...]]:
    if incoming is None:
        return current, ()
    changes: list[_PolicyChange] = []
    require_current_information = _or_bool(
        current.require_current_information, incoming.require_current_information
    )
    if require_current_information != current.require_current_information:
        changes.append(
            (
                "require_current_information",
                "or",
                current.require_current_information,
                require_current_information,
            )
        )
    allow_historical_information = _and_bool(
        current.allow_historical_information, incoming.allow_historical_information
    )
    if allow_historical_information != current.allow_historical_information:
        changes.append(
            (
                "allow_historical_information",
                "and",
                current.allow_historical_information,
                allow_historical_information,
            )
        )
    maximum_age_seconds = _min_non_null(
        current.maximum_age_seconds, incoming.maximum_age_seconds
    )
    if maximum_age_seconds != current.maximum_age_seconds:
        changes.append(
            (
                "maximum_age_seconds",
                "min",
                current.maximum_age_seconds,
                maximum_age_seconds,
            )
        )
    require_temporal_provenance = _or_bool(
        current.require_temporal_provenance, incoming.require_temporal_provenance
    )
    if require_temporal_provenance != current.require_temporal_provenance:
        changes.append(
            (
                "require_temporal_provenance",
                "or",
                current.require_temporal_provenance,
                require_temporal_provenance,
            )
        )
    allow_future_projection = _and_bool(
        current.allow_future_projection, incoming.allow_future_projection
    )
    if allow_future_projection != current.allow_future_projection:
        changes.append(
            (
                "allow_future_projection",
                "and",
                current.allow_future_projection,
                allow_future_projection,
            )
        )
    merged = replace(
        current,
        require_current_information=require_current_information,
        allow_historical_information=allow_historical_information,
        maximum_age_seconds=maximum_age_seconds,
        require_temporal_provenance=require_temporal_provenance,
        allow_future_projection=allow_future_projection,
    )
    return merged, tuple(changes)


def merge_production_policy(
    current: DomainProductionPolicy, incoming: DomainProductionPolicy | None
) -> tuple[DomainProductionPolicy, tuple[_PolicyChange, ...]]:
    if incoming is None:
        return current, ()
    changes: list[_PolicyChange] = []
    allow_draft = _and_bool(current.allow_draft, incoming.allow_draft)
    if allow_draft != current.allow_draft:
        changes.append(("allow_draft", "and", current.allow_draft, allow_draft))
    allow_final = _and_bool(current.allow_final, incoming.allow_final)
    if allow_final != current.allow_final:
        changes.append(("allow_final", "and", current.allow_final, allow_final))
    allow_external_action = _and_bool(
        current.allow_external_action, incoming.allow_external_action
    )
    if allow_external_action != current.allow_external_action:
        changes.append(
            (
                "allow_external_action",
                "and",
                current.allow_external_action,
                allow_external_action,
            )
        )
    require_review = _or_bool(current.require_review, incoming.require_review)
    if require_review != current.require_review:
        changes.append(("require_review", "or", current.require_review, require_review))
    require_validation = _or_bool(
        current.require_validation, incoming.require_validation
    )
    if require_validation != current.require_validation:
        changes.append(
            ("require_validation", "or", current.require_validation, require_validation)
        )
    maximum_output_items = _min_non_null(
        current.maximum_output_items, incoming.maximum_output_items
    )
    if maximum_output_items != current.maximum_output_items:
        changes.append(
            (
                "maximum_output_items",
                "min",
                current.maximum_output_items,
                maximum_output_items,
            )
        )
    merged = replace(
        current,
        allow_draft=allow_draft,
        allow_final=allow_final,
        allow_external_action=allow_external_action,
        require_review=require_review,
        require_validation=require_validation,
        maximum_output_items=maximum_output_items,
    )
    return merged, tuple(changes)


# ═══════════════════════════════════════════════════════════════════════════════
# Composition state
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class _CompositionState:
    required_rules: tuple[str, ...] = ()
    optional_rules: tuple[str, ...] = ()
    prohibited_rules: tuple[str, ...] = ()
    allowed_resource_kinds: tuple[str, ...] | None = None
    priority_resource_kinds: tuple[str, ...] = ()
    prohibited_resource_kinds: tuple[str, ...] = ()
    minimum_confidence: float = 0.0
    reasoning_depth: DomainReasoningDepth = DomainReasoningDepth.EXHAUSTIVE
    allowed_inferences: tuple[str, ...] | None = None
    prohibited_inferences: tuple[str, ...] = ()
    maximum_questions: int = 16
    escalation_rules: tuple[str, ...] = ()
    prohibited_actions: tuple[str, ...] = ()
    question_policy: DomainQuestionPolicy = field(default_factory=DomainQuestionPolicy)
    presentation_policy: DomainPresentationPolicy = field(
        default_factory=DomainPresentationPolicy
    )
    memory_policy: DomainMemoryPolicy = field(default_factory=DomainMemoryPolicy)
    temporal_policy: DomainTemporalPolicy = field(default_factory=DomainTemporalPolicy)
    production_policy: DomainProductionPolicy = field(
        default_factory=DomainProductionPolicy
    )
    permissions: tuple[str, ...] | None = None


@dataclass(frozen=True)
class _Contribution:
    source: DomainProfileSource
    source_id: str | None
    profile_name: str | None
    required_rules: tuple[str, ...] | None
    optional_rules: tuple[str, ...] | None
    prohibited_rules: tuple[str, ...] | None
    allowed_resource_kinds: tuple[str, ...] | None
    priority_resource_kinds: tuple[str, ...] | None
    prohibited_resource_kinds: tuple[str, ...] | None
    minimum_confidence: float | None
    reasoning_depth: DomainReasoningDepth | None
    allowed_inferences: tuple[str, ...] | None
    prohibited_inferences: tuple[str, ...] | None
    maximum_questions: int | None
    escalation_rules: tuple[str, ...] | None
    prohibited_actions: tuple[str, ...] | None
    question_policy: DomainQuestionPolicy | None
    presentation_policy: DomainPresentationPolicy | None
    memory_policy: DomainMemoryPolicy | None
    temporal_policy: DomainTemporalPolicy | None
    production_policy: DomainProductionPolicy | None
    permissions: tuple[str, ...] | None


def _contribution_from_definition(
    definition: DomainProfileDefinition, source: DomainProfileSource
) -> _Contribution:
    return _Contribution(
        source=source,
        source_id=definition.id,
        profile_name=definition.profile_name,
        required_rules=definition.required_rules,
        optional_rules=definition.optional_rules,
        prohibited_rules=definition.prohibited_rules,
        allowed_resource_kinds=definition.allowed_resource_kinds,
        priority_resource_kinds=definition.priority_resource_kinds,
        prohibited_resource_kinds=definition.prohibited_resource_kinds,
        minimum_confidence=definition.minimum_confidence,
        reasoning_depth=definition.reasoning_depth,
        allowed_inferences=definition.allowed_inferences,
        prohibited_inferences=definition.prohibited_inferences,
        maximum_questions=definition.maximum_questions,
        escalation_rules=definition.escalation_rules,
        prohibited_actions=definition.prohibited_actions,
        question_policy=definition.question_policy,
        presentation_policy=definition.presentation_policy,
        memory_policy=definition.memory_policy,
        temporal_policy=definition.temporal_policy,
        production_policy=definition.production_policy,
        permissions=definition.permissions,
    )


def _contribution_from_overlay(overlay: DomainProfileOverlay) -> _Contribution:
    return _Contribution(
        source=overlay.source,
        source_id=overlay.source_id or overlay.id,
        profile_name=None,
        required_rules=overlay.required_rules,
        optional_rules=overlay.optional_rules,
        prohibited_rules=overlay.prohibited_rules,
        allowed_resource_kinds=overlay.allowed_resource_kinds,
        priority_resource_kinds=overlay.priority_resource_kinds,
        prohibited_resource_kinds=overlay.prohibited_resource_kinds,
        minimum_confidence=overlay.minimum_confidence,
        reasoning_depth=overlay.reasoning_depth,
        allowed_inferences=overlay.allowed_inferences,
        prohibited_inferences=overlay.prohibited_inferences,
        maximum_questions=overlay.maximum_questions,
        escalation_rules=overlay.escalation_rules,
        prohibited_actions=overlay.prohibited_actions,
        question_policy=overlay.question_policy,
        presentation_policy=overlay.presentation_policy,
        memory_policy=overlay.memory_policy,
        temporal_policy=overlay.temporal_policy,
        production_policy=overlay.production_policy,
        permissions=overlay.permissions,
    )


def _overlay_sort_key(overlay: DomainProfileOverlay) -> tuple[int, int, str, str]:
    return (
        _precedence_index(overlay.source),
        -overlay.priority,
        overlay.source_id or "",
        overlay.id,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DomainProfileComposer
# ═══════════════════════════════════════════════════════════════════════════════


@runtime_checkable
class DomainProfileComposer(Protocol):
    """Protocol for pure, deterministic Domain Profile composition."""

    def compose(
        self,
        *,
        global_profile: DomainProfileDefinition,
        primary_profile: DomainProfileDefinition,
        supporting_profiles: tuple[DomainProfileDefinition, ...],
        overlays: tuple[DomainProfileOverlay, ...],
        request_permissions: tuple[str, ...] | None,
    ) -> DomainProfileCompositionResult: ...


class DefaultDomainProfileComposer:
    """Reference ``DomainProfileComposer`` implementing the monotonic merge rules."""

    def compose(
        self,
        *,
        global_profile: DomainProfileDefinition,
        primary_profile: DomainProfileDefinition,
        supporting_profiles: tuple[DomainProfileDefinition, ...] = (),
        overlays: tuple[DomainProfileOverlay, ...] = (),
        request_permissions: tuple[str, ...] | None = None,
    ) -> DomainProfileCompositionResult:
        conflicts: list[DomainProfileConflict] = []
        rejections: list[DomainProfileRejection] = []
        decisions: list[DomainProfileDecision] = []
        modifications: list[DomainProfileModification] = []

        state = _CompositionState()
        profile_names: list[str] = []

        ordered_overlays = tuple(sorted(overlays, key=_overlay_sort_key))
        definition_contributions = [
            (global_profile, DomainProfileSource.GLOBAL_POLICY),
            (primary_profile, DomainProfileSource.PRIMARY_DOMAIN),
            *(
                (profile, DomainProfileSource.SUPPORTING_DOMAIN)
                for profile in supporting_profiles
            ),
        ]

        global_required = global_profile.required_rules

        for definition, source in definition_contributions:
            contribution = _contribution_from_definition(definition, source)
            profile_names.append(definition.profile_name)
            self._apply_contribution(
                state, contribution, modifications, decisions, conflicts
            )
            decisions.append(
                DomainProfileDecision(
                    code=DomainProfileDecisionCode.PROFILE_APPLIED,
                    field="profile",
                    source=source,
                    source_id=definition.id,
                )
            )

        for overlay in ordered_overlays:
            contribution = _contribution_from_overlay(overlay)
            self._apply_contribution(
                state, contribution, modifications, decisions, conflicts
            )
            decisions.append(
                DomainProfileDecision(
                    code=DomainProfileDecisionCode.OVERLAY_APPLIED,
                    field="overlay",
                    source=overlay.source,
                    source_id=overlay.source_id or overlay.id,
                    reason=overlay.reason,
                )
            )

        if request_permissions is not None:
            previous = state.permissions
            state.permissions = _fold_permissions(
                state.permissions, request_permissions
            )
            if state.permissions != previous:
                modifications.append(
                    DomainProfileModification(
                        field="permissions",
                        source=DomainProfileSource.EXPLICIT_REQUEST,
                        source_id=None,
                        operation="restrictive_intersection",
                        previous_value=list(previous) if previous is not None else None,
                        new_value=(
                            list(state.permissions)
                            if state.permissions is not None
                            else None
                        ),
                    )
                )
                decisions.append(
                    DomainProfileDecision(
                        code=DomainProfileDecisionCode.PERMISSION_RESTRICTED,
                        field="permissions",
                        source=DomainProfileSource.EXPLICIT_REQUEST,
                    )
                )

        for rule in global_required:
            decisions.append(
                DomainProfileDecision(
                    code=DomainProfileDecisionCode.MANDATORY_RULE_PRESERVED,
                    field="required_rules",
                    source=DomainProfileSource.GLOBAL_POLICY,
                    source_id=global_profile.id,
                    reason=rule,
                )
            )

        global_blocking = set(global_required) & set(state.prohibited_rules)
        if global_blocking:
            conflicts.append(
                DomainProfileConflict(
                    code="GLOBAL_MANDATORY_PROHIBITED",
                    field="required_rules",
                    severity=DomainProfileConflictSeverity.BLOCKING,
                    sources=(DomainProfileSource.GLOBAL_POLICY,),
                    description=(
                        "global mandatory rule(s) conflict with prohibited rule(s): "
                        f"{sorted(global_blocking)}"
                    ),
                    blocking=True,
                )
            )
            decisions.append(
                DomainProfileDecision(
                    code=DomainProfileDecisionCode.CONFLICT_RECORDED,
                    field="required_rules",
                    source=DomainProfileSource.GLOBAL_POLICY,
                    blocking=True,
                )
            )

        non_global_blocking = (
            set(state.required_rules) & set(state.prohibited_rules)
        ) - global_blocking
        if non_global_blocking:
            conflicts.append(
                DomainProfileConflict(
                    code="REQUIRED_AND_PROHIBITED_RULE",
                    field="required_rules",
                    severity=DomainProfileConflictSeverity.ERROR,
                    sources=(DomainProfileSource.PRIMARY_DOMAIN,),
                    description=(
                        "required rule(s) conflict with prohibited rule(s): "
                        f"{sorted(non_global_blocking)}"
                    ),
                    blocking=False,
                )
            )
            decisions.append(
                DomainProfileDecision(
                    code=DomainProfileDecisionCode.PROHIBITED_RULE_PREVAILED,
                    field="required_rules",
                    source=DomainProfileSource.PRIMARY_DOMAIN,
                    blocking=False,
                )
            )

        state.optional_rules = _ordered_difference(
            state.optional_rules, state.required_rules, state.prohibited_rules
        )

        if state.allowed_resource_kinds is not None:
            state.allowed_resource_kinds = _ordered_difference(
                state.allowed_resource_kinds, state.prohibited_resource_kinds
            )
        state.priority_resource_kinds = _ordered_difference(
            state.priority_resource_kinds, state.prohibited_resource_kinds
        )
        if state.allowed_resource_kinds is not None:
            state.priority_resource_kinds = _ordered_intersection(
                state.priority_resource_kinds, state.allowed_resource_kinds
            )

        inference_overlap: set[str] = set()
        if state.allowed_inferences is not None:
            inference_overlap = set(state.allowed_inferences) & set(
                state.prohibited_inferences
            )
            if inference_overlap:
                state.allowed_inferences = _ordered_difference(
                    state.allowed_inferences, state.prohibited_inferences
                )
                conflicts.append(
                    DomainProfileConflict(
                        code="ALLOWED_AND_PROHIBITED_INFERENCE",
                        field="allowed_inferences",
                        severity=DomainProfileConflictSeverity.ERROR,
                        sources=(DomainProfileSource.GLOBAL_POLICY,),
                        description=(
                            "allowed_inferences overlapped prohibited_inferences: "
                            f"{sorted(inference_overlap)}"
                        ),
                        blocking=False,
                    )
                )
                decisions.append(
                    DomainProfileDecision(
                        code=DomainProfileDecisionCode.INFERENCE_PROHIBITED,
                        field="allowed_inferences",
                        source=DomainProfileSource.GLOBAL_POLICY,
                    )
                )

        effective_maximum_questions = _min_non_null(
            state.maximum_questions, state.question_policy.maximum_questions
        )
        if effective_maximum_questions is None:
            effective_maximum_questions = state.maximum_questions
        if effective_maximum_questions != state.maximum_questions:
            modifications.append(
                DomainProfileModification(
                    field="maximum_questions",
                    source=DomainProfileSource.GLOBAL_POLICY,
                    source_id=None,
                    operation="min",
                    previous_value=state.maximum_questions,
                    new_value=effective_maximum_questions,
                    reason="question_policy.maximum_questions",
                )
            )
            decisions.append(
                DomainProfileDecision(
                    code=DomainProfileDecisionCode.LIMIT_RESTRICTED,
                    field="maximum_questions",
                    source=DomainProfileSource.GLOBAL_POLICY,
                )
            )
        state.maximum_questions = int(effective_maximum_questions)

        draft = DomainProfileDraft(
            primary_domain=primary_profile.domain_id,
            supporting_domains=tuple(p.domain_id for p in supporting_profiles),
            profile_names=tuple(profile_names),
            required_rules=state.required_rules,
            optional_rules=state.optional_rules,
            prohibited_rules=state.prohibited_rules,
            allowed_resource_kinds=state.allowed_resource_kinds,
            priority_resource_kinds=state.priority_resource_kinds,
            prohibited_resource_kinds=state.prohibited_resource_kinds,
            minimum_confidence=state.minimum_confidence,
            reasoning_depth=state.reasoning_depth,
            allowed_inferences=state.allowed_inferences,
            prohibited_inferences=state.prohibited_inferences,
            maximum_questions=state.maximum_questions,
            escalation_rules=state.escalation_rules,
            prohibited_actions=state.prohibited_actions,
            question_policy=state.question_policy,
            presentation_policy=state.presentation_policy,
            memory_policy=state.memory_policy,
            temporal_policy=state.temporal_policy,
            production_policy=state.production_policy,
            permissions=state.permissions,
            modifications=tuple(modifications),
        )

        return DomainProfileCompositionResult(
            profile=draft,
            conflicts=tuple(conflicts),
            rejections=tuple(rejections),
            decisions=tuple(decisions),
            modifications=tuple(modifications),
            metadata=MappingProxyType({}),
        )

    def _apply_contribution(
        self,
        state: _CompositionState,
        contribution: _Contribution,
        modifications: list[DomainProfileModification],
        decisions: list[DomainProfileDecision],
        conflicts: list[DomainProfileConflict],
    ) -> None:
        source = contribution.source
        source_id = contribution.source_id

        def record(field_name: str, operation: str, previous: Any, new: Any) -> None:
            if previous == new:
                return
            modifications.append(
                DomainProfileModification(
                    field=field_name,
                    source=source,
                    source_id=source_id,
                    operation=operation,
                    previous_value=previous,
                    new_value=new,
                )
            )

        if contribution.required_rules:
            new_required = _ordered_union(
                state.required_rules, contribution.required_rules
            )
            record(
                "required_rules",
                "ordered_union",
                list(state.required_rules),
                list(new_required),
            )
            state.required_rules = new_required

        if contribution.prohibited_rules:
            new_prohibited = _ordered_union(
                state.prohibited_rules, contribution.prohibited_rules
            )
            record(
                "prohibited_rules",
                "ordered_union",
                list(state.prohibited_rules),
                list(new_prohibited),
            )
            state.prohibited_rules = new_prohibited

        if contribution.optional_rules:
            new_optional = _ordered_union(
                state.optional_rules, contribution.optional_rules
            )
            record(
                "optional_rules",
                "ordered_union",
                list(state.optional_rules),
                list(new_optional),
            )
            state.optional_rules = new_optional

        if contribution.prohibited_resource_kinds:
            new_val = _ordered_union(
                state.prohibited_resource_kinds, contribution.prohibited_resource_kinds
            )
            record(
                "prohibited_resource_kinds",
                "ordered_union",
                list(state.prohibited_resource_kinds),
                list(new_val),
            )
            state.prohibited_resource_kinds = new_val

        new_allowed = _fold_restrictive_constraint(
            state.allowed_resource_kinds, contribution.allowed_resource_kinds
        )
        if new_allowed != state.allowed_resource_kinds:
            record(
                "allowed_resource_kinds",
                "restrictive_intersection",
                list(state.allowed_resource_kinds)
                if state.allowed_resource_kinds is not None
                else None,
                list(new_allowed) if new_allowed is not None else None,
            )
            decisions.append(
                DomainProfileDecision(
                    code=DomainProfileDecisionCode.RESOURCE_RESTRICTED,
                    field="allowed_resource_kinds",
                    source=source,
                    source_id=source_id,
                )
            )
            state.allowed_resource_kinds = new_allowed

        if contribution.priority_resource_kinds:
            new_val = _ordered_union(
                state.priority_resource_kinds, contribution.priority_resource_kinds
            )
            record(
                "priority_resource_kinds",
                "ordered_union",
                list(state.priority_resource_kinds),
                list(new_val),
            )
            state.priority_resource_kinds = new_val

        new_confidence = _max_non_null(
            state.minimum_confidence, contribution.minimum_confidence
        )
        if new_confidence != state.minimum_confidence:
            record(
                "minimum_confidence",
                "max",
                state.minimum_confidence,
                new_confidence,
            )
            decisions.append(
                DomainProfileDecision(
                    code=DomainProfileDecisionCode.CONFIDENCE_RAISED,
                    field="minimum_confidence",
                    source=source,
                    source_id=source_id,
                )
            )
            state.minimum_confidence = new_confidence

        new_depth = _pick_most_restrictive_low_index(
            _REASONING_DEPTH_ORDER, state.reasoning_depth, contribution.reasoning_depth
        )
        if new_depth != state.reasoning_depth:
            record(
                "reasoning_depth",
                "restrictive_order",
                state.reasoning_depth.value,
                new_depth.value,
            )
            decisions.append(
                DomainProfileDecision(
                    code=DomainProfileDecisionCode.LIMIT_RESTRICTED,
                    field="reasoning_depth",
                    source=source,
                    source_id=source_id,
                )
            )
            state.reasoning_depth = new_depth

        if contribution.prohibited_inferences:
            new_val = _ordered_union(
                state.prohibited_inferences, contribution.prohibited_inferences
            )
            record(
                "prohibited_inferences",
                "ordered_union",
                list(state.prohibited_inferences),
                list(new_val),
            )
            state.prohibited_inferences = new_val

        new_allowed_inferences = _fold_restrictive_constraint(
            state.allowed_inferences, contribution.allowed_inferences
        )
        if new_allowed_inferences != state.allowed_inferences:
            record(
                "allowed_inferences",
                "restrictive_intersection",
                list(state.allowed_inferences)
                if state.allowed_inferences is not None
                else None,
                list(new_allowed_inferences)
                if new_allowed_inferences is not None
                else None,
            )
            state.allowed_inferences = new_allowed_inferences

        if contribution.maximum_questions is not None:
            new_val = _min_non_null(
                state.maximum_questions, contribution.maximum_questions
            )
            if new_val != state.maximum_questions:
                record(
                    "maximum_questions",
                    "min",
                    state.maximum_questions,
                    new_val,
                )
                decisions.append(
                    DomainProfileDecision(
                        code=DomainProfileDecisionCode.LIMIT_RESTRICTED,
                        field="maximum_questions",
                        source=source,
                        source_id=source_id,
                    )
                )
                state.maximum_questions = int(new_val)

        if contribution.escalation_rules:
            new_val = _ordered_union(
                state.escalation_rules, contribution.escalation_rules
            )
            if new_val != state.escalation_rules:
                record(
                    "escalation_rules",
                    "ordered_union",
                    list(state.escalation_rules),
                    list(new_val),
                )
                decisions.append(
                    DomainProfileDecision(
                        code=DomainProfileDecisionCode.ESCALATION_ADDED,
                        field="escalation_rules",
                        source=source,
                        source_id=source_id,
                    )
                )
                state.escalation_rules = new_val

        if contribution.prohibited_actions:
            new_val = _ordered_union(
                state.prohibited_actions, contribution.prohibited_actions
            )
            if new_val != state.prohibited_actions:
                record(
                    "prohibited_actions",
                    "ordered_union",
                    list(state.prohibited_actions),
                    list(new_val),
                )
                decisions.append(
                    DomainProfileDecision(
                        code=DomainProfileDecisionCode.ACTION_PROHIBITED,
                        field="prohibited_actions",
                        source=source,
                        source_id=source_id,
                    )
                )
                state.prohibited_actions = new_val

        new_permissions = _fold_permissions(state.permissions, contribution.permissions)
        if new_permissions != state.permissions:
            record(
                "permissions",
                "restrictive_intersection",
                list(state.permissions) if state.permissions is not None else None,
                list(new_permissions) if new_permissions is not None else None,
            )
            decisions.append(
                DomainProfileDecision(
                    code=DomainProfileDecisionCode.PERMISSION_RESTRICTED,
                    field="permissions",
                    source=source,
                    source_id=source_id,
                )
            )
            state.permissions = new_permissions

        for policy_name, merge_fn in (
            ("question_policy", merge_question_policy),
            ("presentation_policy", merge_presentation_policy),
            ("memory_policy", merge_memory_policy),
            ("temporal_policy", merge_temporal_policy),
            ("production_policy", merge_production_policy),
        ):
            current_policy = getattr(state, policy_name)
            incoming_policy = getattr(contribution, policy_name)
            merged_policy, changes = merge_fn(current_policy, incoming_policy)
            if changes:
                setattr(state, policy_name, merged_policy)
                for sub_field, operation, previous, new in changes:
                    record(f"{policy_name}.{sub_field}", operation, previous, new)
                    decisions.append(
                        DomainProfileDecision(
                            code=DomainProfileDecisionCode.POLICY_RESTRICTED,
                            field=f"{policy_name}.{sub_field}",
                            source=source,
                            source_id=source_id,
                        )
                    )


__all__ = [
    "DefaultDomainProfileComposer",
    "DomainProfileComposer",
    "merge_memory_policy",
    "merge_presentation_policy",
    "merge_production_policy",
    "merge_question_policy",
    "merge_temporal_policy",
]
