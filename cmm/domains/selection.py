"""Pure helpers for Phase 10.31 domain-selection semantics."""

from __future__ import annotations

from cmm.domains.resolver_contracts import DomainResolutionResult
from cmm.domains.selection_contracts import DomainSelectionTransition

_DOMAIN_SELECTION_REEVALUATED = "DOMAIN_SELECTION_REEVALUATED"
_DOMAIN_SELECTION_PRIMARY_CHANGED = "DOMAIN_SELECTION_PRIMARY_CHANGED"
_DOMAIN_SELECTION_COMPOSITION_CHANGED = "DOMAIN_SELECTION_COMPOSITION_CHANGED"


def build_domain_selection_transition(
    previous: DomainResolutionResult,
    current: DomainResolutionResult,
) -> DomainSelectionTransition:
    """Compare two resolution results without performing side effects."""

    previous_supporting = tuple(previous.supporting_domains)
    current_supporting = tuple(current.supporting_domains)

    primary_changed = previous.primary_domain != current.primary_domain
    supporting_changed = previous_supporting != current_supporting

    reasons: list[str] = []

    if primary_changed or supporting_changed:
        reasons.append(_DOMAIN_SELECTION_REEVALUATED)

        if primary_changed:
            reasons.append(_DOMAIN_SELECTION_PRIMARY_CHANGED)

        if supporting_changed:
            reasons.append(_DOMAIN_SELECTION_COMPOSITION_CHANGED)

    requires_recomposition = primary_changed or supporting_changed
    requires_session_update = requires_recomposition

    return DomainSelectionTransition(
        previous_resolution_id=previous.id,
        new_resolution_id=current.id,
        previous_primary_domain=previous.primary_domain,
        new_primary_domain=current.primary_domain,
        previous_supporting_domains=previous_supporting,
        new_supporting_domains=current_supporting,
        primary_changed=primary_changed,
        supporting_changed=supporting_changed,
        reason_codes=tuple(reasons),
        requires_recomposition=requires_recomposition,
        requires_session_update=requires_session_update,
    )


__all__ = [
    "build_domain_selection_transition",
]
