"""Pure helpers for Phase 10.31 domain-selection semantics."""

from __future__ import annotations

from collections.abc import Sequence

from cmm.domains.resolution_contracts import DomainResolutionContext
from cmm.domains.resolver_contracts import (
    DomainCandidateScore,
    DomainResolutionResult,
)
from cmm.domains.selection_contracts import DomainSelectionTransition

_DOMAIN_SELECTION_REEVALUATED = "DOMAIN_SELECTION_REEVALUATED"
_DOMAIN_SELECTION_PRIMARY_CHANGED = "DOMAIN_SELECTION_PRIMARY_CHANGED"
_DOMAIN_SELECTION_COMPOSITION_CHANGED = "DOMAIN_SELECTION_COMPOSITION_CHANGED"


def candidate_selection_confidence(
    context: DomainResolutionContext,
    candidate: DomainCandidateScore,
) -> float | None:
    """Return explicit probabilistic confidence for a candidate, when available.

    ``DomainCandidateScore.confidence`` is derived from aggregate scoring and
    therefore is not the same concept as Phase 10.31 selection confidence.

    A matching structured signal with ``confidence=None`` represents
    non-probabilistic structured evidence, so the probabilistic confidence
    floor is not applied to that candidate.
    """

    matching_signals = tuple(
        signal
        for signal in context.signals
        if any(
            domain_id.slug == candidate.domain_id.slug
            for domain_id in signal.domain_ids
        )
    )

    if not matching_signals:
        return None

    confidences = tuple(
        signal.confidence
        for signal in matching_signals
        if signal.confidence is not None
    )

    if not confidences:
        return None

    return max(confidences)


def explicit_candidates(
    context: DomainResolutionContext,
    eligible: Sequence[DomainCandidateScore],
) -> tuple[DomainCandidateScore, ...]:
    """Return eligible candidates explicitly requested by the user."""

    explicit_slugs = {domain_id.slug for domain_id in context.explicit_domains}

    return tuple(
        candidate
        for candidate in eligible
        if candidate.domain_id.slug in explicit_slugs
    )


def domain_signal_candidates(
    context: DomainResolutionContext,
    eligible: Sequence[DomainCandidateScore],
    *,
    kind: str,
) -> tuple[DomainCandidateScore, ...]:
    """Return eligible candidates referenced by one structured signal kind."""

    signal_slugs = {
        domain_id.slug
        for signal in context.signals
        if signal.kind == kind
        for domain_id in signal.domain_ids
    }

    return tuple(
        candidate for candidate in eligible if candidate.domain_id.slug in signal_slugs
    )


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
    "candidate_selection_confidence",
    "domain_signal_candidates",
    "explicit_candidates",
]
