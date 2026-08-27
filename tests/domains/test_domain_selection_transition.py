from datetime import datetime, timezone

from cmm.domains.identifiers import DomainId
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionSignal,
)
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.selection import build_domain_selection_transition
from cmm.domains.selection_contracts import DomainSelectionTransition

GENERAL = DomainId.from_str("domain:general")
PROJECT = DomainId.from_str("domain:project")
HEALTH = DomainId.from_str("domain:health")
REFLECTION = DomainId.from_str("domain:reflection")

NOW = datetime(2026, 8, 27, 18, 0, tzinfo=timezone.utc)


def _resolver(result_id: str) -> DefaultDomainResolver:
    return DefaultDomainResolver(
        fallback_domain=GENERAL,
        id_factory=lambda: result_id,
        clock=lambda: NOW,
    )


def _resolved(
    *,
    result_id: str,
    context_id: str,
    primary: DomainId,
    supporting: DomainId | None = None,
):
    signals = [
        DomainResolutionSignal(
            kind="operation",
            source="test",
            value="primary-evidence",
            domain_ids=(primary,),
            confidence=1.0,
            weight=1.0,
            provenance={"source": "test_fixture"},
        )
    ]

    available = [GENERAL, primary]

    if supporting is not None:
        available.append(supporting)
        signals.append(
            DomainResolutionSignal(
                kind="intent",
                source="test",
                value="supporting-evidence",
                domain_ids=(supporting,),
                confidence=1.0,
                weight=1.0,
                provenance={"source": "test_fixture"},
            )
        )

    context = DomainResolutionContext(
        id=context_id,
        user_input="structured transition fixture",
        available_domains=tuple(available),
        authorized_domains=tuple(available),
        signals=tuple(signals),
        created_at=NOW,
    )

    result = _resolver(result_id).resolve(context)

    assert result.primary_domain == primary

    if supporting is None:
        assert result.supporting_domains == ()
    else:
        assert result.supporting_domains == (supporting,)

    return result


def test_transition_binds_exact_previous_and_new_resolution_ids():
    previous = _resolved(
        result_id="resolution-before",
        context_id="context-before",
        primary=PROJECT,
    )
    current = _resolved(
        result_id="resolution-after",
        context_id="context-after",
        primary=HEALTH,
    )

    transition = build_domain_selection_transition(previous, current)

    assert transition.previous_resolution_id == "resolution-before"
    assert transition.new_resolution_id == "resolution-after"


def test_transition_detects_primary_change():
    previous = _resolved(
        result_id="resolution-before",
        context_id="context-before",
        primary=PROJECT,
    )
    current = _resolved(
        result_id="resolution-after",
        context_id="context-after",
        primary=HEALTH,
    )

    transition = build_domain_selection_transition(previous, current)

    assert transition.previous_primary_domain == PROJECT
    assert transition.new_primary_domain == HEALTH
    assert transition.primary_changed is True
    assert transition.supporting_changed is False
    assert transition.reason_codes == (
        "DOMAIN_SELECTION_REEVALUATED",
        "DOMAIN_SELECTION_PRIMARY_CHANGED",
    )
    assert transition.requires_recomposition is True
    assert transition.requires_session_update is True


def test_transition_detects_supporting_only_change():
    previous = _resolved(
        result_id="resolution-before",
        context_id="context-before",
        primary=PROJECT,
    )
    current = _resolved(
        result_id="resolution-after",
        context_id="context-after",
        primary=PROJECT,
        supporting=REFLECTION,
    )

    transition = build_domain_selection_transition(previous, current)

    assert transition.primary_changed is False
    assert transition.supporting_changed is True
    assert transition.previous_supporting_domains == ()
    assert transition.new_supporting_domains == (REFLECTION,)
    assert transition.reason_codes == (
        "DOMAIN_SELECTION_REEVALUATED",
        "DOMAIN_SELECTION_COMPOSITION_CHANGED",
    )
    assert transition.requires_recomposition is True
    assert transition.requires_session_update is True


def test_transition_detects_primary_and_supporting_change():
    previous = _resolved(
        result_id="resolution-before",
        context_id="context-before",
        primary=PROJECT,
        supporting=REFLECTION,
    )
    current = _resolved(
        result_id="resolution-after",
        context_id="context-after",
        primary=HEALTH,
        supporting=PROJECT,
    )

    transition = build_domain_selection_transition(previous, current)

    assert transition.primary_changed is True
    assert transition.supporting_changed is True
    assert transition.reason_codes == (
        "DOMAIN_SELECTION_REEVALUATED",
        "DOMAIN_SELECTION_PRIMARY_CHANGED",
        "DOMAIN_SELECTION_COMPOSITION_CHANGED",
    )
    assert transition.requires_recomposition is True
    assert transition.requires_session_update is True


def test_unchanged_selection_has_no_transition_effects():
    previous = _resolved(
        result_id="resolution-before",
        context_id="context-before",
        primary=PROJECT,
        supporting=REFLECTION,
    )
    current = _resolved(
        result_id="resolution-after",
        context_id="context-after",
        primary=PROJECT,
        supporting=REFLECTION,
    )

    transition = build_domain_selection_transition(previous, current)

    assert transition.previous_resolution_id == "resolution-before"
    assert transition.new_resolution_id == "resolution-after"
    assert transition.primary_changed is False
    assert transition.supporting_changed is False
    assert transition.reason_codes == ()
    assert transition.requires_recomposition is False
    assert transition.requires_session_update is False


def test_transition_round_trip_preserves_identity_and_change_state():
    previous = _resolved(
        result_id="resolution-before",
        context_id="context-before",
        primary=PROJECT,
    )
    current = _resolved(
        result_id="resolution-after",
        context_id="context-after",
        primary=HEALTH,
    )

    transition = build_domain_selection_transition(previous, current)
    restored = DomainSelectionTransition.from_dict(transition.to_dict())

    assert restored.to_dict() == transition.to_dict()
    assert restored.previous_resolution_id == previous.id
    assert restored.new_resolution_id == current.id
