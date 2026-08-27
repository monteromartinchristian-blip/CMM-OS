from datetime import datetime, timezone

from cmm.domains.enums import DomainStatus
from cmm.domains.general.definition import build_general_domain_definition
from cmm.domains.identifiers import DomainId
from cmm.domains.registry_contracts import (
    DomainRegistryRecord,
    DomainRegistrySnapshot,
)
from cmm.domains.resolution_builder import DomainResolutionContextBuilder
from cmm.domains.resolution_contracts import DomainResolutionSignal

NOW = datetime(2026, 8, 27, 18, 30, tzinfo=timezone.utc)

GENERAL = DomainId.from_str("domain:general")
PROJECT = DomainId.from_str("domain:project")
LIFE_PLAN = DomainId.from_str("domain:life-plan")


def _builder() -> DomainResolutionContextBuilder:
    return DomainResolutionContextBuilder(
        clock=lambda: NOW,
        id_factory=lambda: "ctx-selection-test",
    )


def _matching_signals(context, *, kind: str, domain_id: DomainId):
    return tuple(
        signal
        for signal in context.signals
        if signal.kind == kind
        and any(item.slug == domain_id.slug for item in signal.domain_ids)
    )


def test_builder_session_signal_is_structured_and_canonical():
    context = _builder().build(
        user_input="continue current work",
        session_id="session-123",
        session_domain=PROJECT,
    )

    signals = _matching_signals(
        context,
        kind="session",
        domain_id=PROJECT,
    )

    assert len(signals) == 1

    signal = signals[0]

    assert signal.source == "domain_resolution_context_builder"
    assert signal.value == "session_domain"
    assert signal.domain_ids == (PROJECT,)
    assert signal.confidence == 1.0
    assert signal.weight == 10.0
    assert dict(signal.provenance) == {
        "source": "explicit_session_domain",
    }


def test_builder_goal_signal_is_structured_and_canonical():
    context = _builder().build(
        user_input="continue active goal",
        goal_id="goal-123",
        active_goal_domain=LIFE_PLAN,
    )

    signals = _matching_signals(
        context,
        kind="goal",
        domain_id=LIFE_PLAN,
    )

    assert len(signals) == 1

    signal = signals[0]

    assert signal.source == "domain_resolution_context_builder"
    assert signal.value == "active_goal_domain"
    assert signal.domain_ids == (LIFE_PLAN,)
    assert signal.confidence == 1.0
    assert signal.weight == 10.0
    assert dict(signal.provenance) == {
        "source": "explicit_active_goal_domain",
    }


def test_builder_emits_session_and_goal_signals_together():
    context = _builder().build(
        user_input="resolve using structured continuity",
        session_id="session-123",
        goal_id="goal-123",
        session_domain=PROJECT,
        active_goal_domain=LIFE_PLAN,
    )

    assert (
        len(
            _matching_signals(
                context,
                kind="session",
                domain_id=PROJECT,
            )
        )
        == 1
    )

    assert (
        len(
            _matching_signals(
                context,
                kind="goal",
                domain_id=LIFE_PLAN,
            )
        )
        == 1
    )


def test_builder_session_signal_deduplicates_equivalent_supplied_signal():
    supplied = DomainResolutionSignal(
        kind="session",
        source="caller",
        value="existing-session-domain",
        domain_ids=(PROJECT,),
        confidence=0.9,
        weight=7.0,
        provenance={"source": "caller_fixture"},
    )

    context = _builder().build(
        user_input="continue session",
        session_domain=PROJECT,
        signals=(supplied,),
    )

    matches = _matching_signals(
        context,
        kind="session",
        domain_id=PROJECT,
    )

    assert matches == (supplied,)


def test_builder_goal_signal_deduplicates_equivalent_supplied_signal():
    supplied = DomainResolutionSignal(
        kind="goal",
        source="caller",
        value="existing-goal-domain",
        domain_ids=(LIFE_PLAN,),
        confidence=0.9,
        weight=7.0,
        provenance={"source": "caller_fixture"},
    )

    context = _builder().build(
        user_input="continue goal",
        active_goal_domain=LIFE_PLAN,
        signals=(supplied,),
    )

    matches = _matching_signals(
        context,
        kind="goal",
        domain_id=LIFE_PLAN,
    )

    assert matches == (supplied,)


def test_builder_registry_active_domain_is_not_session_continuity():
    definition = build_general_domain_definition()

    record = DomainRegistryRecord(
        definition=definition,
        status=DomainStatus.ACTIVE,
        registered_at=NOW,
        updated_at=NOW,
    )

    snapshot = DomainRegistrySnapshot(
        captured_at=NOW,
        records=(record,),
    )

    context = _builder().build(
        registry_snapshot=snapshot,
        user_input="ordinary request",
    )

    assert GENERAL in context.active_domains

    assert not any(signal.kind == "session" for signal in context.signals)


def test_builder_goal_id_alone_does_not_create_goal_domain_signal():
    context = _builder().build(
        user_input="ordinary goal-linked request",
        goal_id="goal-123",
    )

    assert not any(signal.kind == "goal" for signal in context.signals)


def test_builder_session_id_alone_does_not_create_session_domain_signal():
    context = _builder().build(
        user_input="ordinary session-linked request",
        session_id="session-123",
    )

    assert not any(signal.kind == "session" for signal in context.signals)
