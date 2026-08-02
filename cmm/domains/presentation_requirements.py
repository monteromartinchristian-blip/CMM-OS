"""Phase 10.16 – pure effective requirements shared by planner and validator."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from cmm.domains.composition_contracts import PresentationComposition
from cmm.domains.errors import DomainPresentationPolicyError
from cmm.domains.presentation_contracts import (
    DomainOutputIntent,
    DomainOutputIntentType,
    DomainPresentationEpistemicKind,
    DomainPresentationItemRef,
    DomainPresentationItemType,
    DomainPresentationRequest,
)
from cmm.domains.profile_contracts import DomainPresentationPolicy

_UNCERTAIN_EPISTEMIC_KINDS = frozenset(
    {
        DomainPresentationEpistemicKind.HYPOTHESIS,
        DomainPresentationEpistemicKind.INFERENCE,
        DomainPresentationEpistemicKind.UNKNOWN,
    }
)
_ALWAYS_VISIBLE_TYPES = frozenset(
    {
        DomainPresentationItemType.WARNING,
        DomainPresentationItemType.CONTRADICTION,
        DomainPresentationItemType.ESCALATION,
    }
)
_CONDITIONAL_VISIBLE_TYPES = frozenset(
    {
        DomainPresentationItemType.QUESTION,
        DomainPresentationItemType.WORKFLOW,
        DomainPresentationItemType.MEMORY_PROPOSAL,
    }
)


def _ordered_union(*sequences: tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    for sequence in sequences:
        for value in sequence:
            if value not in result:
                result.append(value)
    return tuple(result)


def composition_identifiers(
    presentation: PresentationComposition, key: str
) -> tuple[str, ...]:
    """Read one declared, identifier-only composition field deterministically."""
    values = presentation.values
    if not isinstance(values, Mapping):  # defensive; the contract already enforces it
        raise DomainPresentationPolicyError(
            "presentation values must be a mapping", field="presentation"
        )
    raw = values.get(key, ())
    if raw is None:
        return ()
    if isinstance(raw, str) or not isinstance(raw, Sequence):
        raise DomainPresentationPolicyError(
            f"presentation composition {key!r} must be a sequence of identifiers",
            field=key,
        )
    result: list[str] = []
    for value in raw:
        if not isinstance(value, str) or not value or value in result:
            raise DomainPresentationPolicyError(
                f"presentation composition {key!r} must contain unique identifiers",
                field=key,
            )
        result.append(value)
    return tuple(result)


def effective_required_sections(
    policy: DomainPresentationPolicy, presentation: PresentationComposition
) -> tuple[str, ...]:
    """The one canonical required-section union for planning and validation."""
    return _ordered_union(
        policy.required_sections,
        composition_identifiers(presentation, "required_sections"),
    )


def effective_suppressed_sections(
    policy: DomainPresentationPolicy, presentation: PresentationComposition
) -> tuple[str, ...]:
    """Declared suppressions; callers reject overlap with required sections."""
    return _ordered_union(
        policy.suppressible_sections,
        composition_identifiers(presentation, "suppressible_sections"),
    )


def required_visibility_refs(request: DomainPresentationRequest) -> tuple[str, ...]:
    """Return only references that must remain visible after presentation."""
    return tuple(
        item.ref_id
        for item in sorted(request.items, key=lambda item: (item.source_order, item.ref_id))
        if _requires_visibility(item, request.policy)
    )


def _requires_visibility(
    item: DomainPresentationItemRef, policy: DomainPresentationPolicy
) -> bool:
    if item.item_type in _ALWAYS_VISIBLE_TYPES:
        return True
    if item.item_type is DomainPresentationItemType.APPROVAL and item.pending:
        return True
    if policy.include_provenance is True and item.requires_provenance:
        return True
    if (
        policy.include_uncertainty is True
        and item.epistemic_kind in _UNCERTAIN_EPISTEMIC_KINDS
    ):
        return True
    if item.item_type in _CONDITIONAL_VISIBLE_TYPES:
        return (
            item.pending
            or item.requires_user_interaction
            or item.requires_approval
            or item.requires_confirmation
            or item.explicitly_visible
        )
    return item.explicitly_visible


def resolved_output_intent(request: DomainPresentationRequest) -> DomainOutputIntent:
    """Prefer an already-resolved request intent; otherwise use policy/default."""
    if request.output_intent is not None:
        return request.output_intent
    if request.policy.preferred_output_types:
        return DomainOutputIntent(
            DomainOutputIntentType(request.policy.preferred_output_types[0])
        )
    return DomainOutputIntent(DomainOutputIntentType.HUMAN_READABLE)


def preferred_output_type(
    policy: DomainPresentationPolicy,
) -> DomainOutputIntentType | None:
    if not policy.preferred_output_types:
        return None
    return DomainOutputIntentType(policy.preferred_output_types[0])


__all__ = [
    "composition_identifiers",
    "effective_required_sections",
    "effective_suppressed_sections",
    "preferred_output_type",
    "required_visibility_refs",
    "resolved_output_intent",
]
