from datetime import datetime, timezone

from cmm.domains.enums import DomainStatus
from cmm.domains.errors import DomainResolverConfigurationError
from cmm.domains.general.definition import build_general_domain_definition
from cmm.domains.identifiers import DomainId
from cmm.domains.registry_contracts import (
    DomainRegistryRecord,
    DomainRegistrySnapshot,
)
from cmm.domains.resolution_builder import DomainResolutionContextBuilder
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionSignal,
)
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resolver_contracts import DomainScoringPolicy
from cmm.domains.selection_contracts import DomainSelectionPolicy

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


# ---------------------------------------------------------------------------
# Phase 10.31 Task 4A — selection-policy resolver contract
# ---------------------------------------------------------------------------


def test_resolver_accepts_and_exposes_selection_policy():
    policy = DomainSelectionPolicy(
        minimum_primary_confidence=0.75,
    )

    resolver = DefaultDomainResolver(
        selection_policy=policy,
    )

    assert resolver.selection_policy is policy


def test_resolver_without_explicit_selection_policy_uses_canonical_default():
    resolver = DefaultDomainResolver()

    assert isinstance(
        resolver.selection_policy,
        DomainSelectionPolicy,
    )
    assert resolver.selection_policy.to_dict() == DomainSelectionPolicy().to_dict()


def test_resolver_fallback_property_comes_from_effective_selection_policy():
    resolver = DefaultDomainResolver()

    assert resolver.fallback_domain == GENERAL
    assert resolver.fallback_domain == resolver.selection_policy.fallback_domain


def test_legacy_fallback_domain_overrides_default_policy_fallback():
    resolver = DefaultDomainResolver(
        fallback_domain=PROJECT,
    )

    assert resolver.fallback_domain == PROJECT
    assert resolver.selection_policy.fallback_domain == PROJECT


def test_matching_explicit_selection_policy_and_legacy_fallback_are_allowed():
    policy = DomainSelectionPolicy(
        fallback_domain=PROJECT,
    )

    resolver = DefaultDomainResolver(
        selection_policy=policy,
        fallback_domain=PROJECT,
    )

    assert resolver.selection_policy is policy
    assert resolver.fallback_domain == PROJECT


def test_conflicting_selection_policy_and_legacy_fallback_are_rejected():
    policy = DomainSelectionPolicy(
        fallback_domain=GENERAL,
    )

    try:
        DefaultDomainResolver(
            selection_policy=policy,
            fallback_domain=PROJECT,
        )
    except DomainResolverConfigurationError as exc:
        assert exc.field == "fallback_domain"
    else:
        raise AssertionError(
            "Expected conflicting fallback configuration to be rejected"
        )


# ---------------------------------------------------------------------------
# Phase 10.31 Task 4B — explicit/session/goal precedence + primary confidence
# ---------------------------------------------------------------------------


def _selection_context(
    *,
    explicit_domains=(),
    signals=(),
    available_domains=(GENERAL, PROJECT, LIFE_PLAN),
    authorized_domains=(GENERAL, PROJECT, LIFE_PLAN),
):
    return DomainResolutionContext(
        id="ctx-task4b",
        user_input="structured domain-selection fixture",
        explicit_domains=explicit_domains,
        available_domains=available_domains,
        authorized_domains=authorized_domains,
        signals=signals,
        created_at=NOW,
    )


def _signal(
    *,
    kind: str,
    domain_id: DomainId,
    weight: float = 1.0,
    confidence: float | None = 1.0,
):
    return DomainResolutionSignal(
        kind=kind,
        source="task4b-test",
        value=f"{kind}-evidence",
        domain_ids=(domain_id,),
        confidence=confidence,
        weight=weight,
        provenance={"source": "task4b_fixture"},
    )


def _candidate(result, domain_id: DomainId):
    return next(
        candidate
        for candidate in result.candidate_scores
        if candidate.domain_id == domain_id
    )


def test_explicit_domain_priority_beats_higher_raw_inferred_score():
    resolver = DefaultDomainResolver()

    result = resolver.resolve(
        _selection_context(
            explicit_domains=(PROJECT,),
            signals=(
                _signal(
                    kind="intent",
                    domain_id=LIFE_PLAN,
                    weight=10.0,
                ),
            ),
        )
    )

    explicit = _candidate(result, PROJECT)
    inferred = _candidate(result, LIFE_PLAN)

    assert explicit.score < inferred.score
    assert result.primary_domain == PROJECT


def test_single_session_domain_has_priority_over_stronger_ordinary_evidence():
    resolver = DefaultDomainResolver()

    result = resolver.resolve(
        _selection_context(
            signals=(
                _signal(
                    kind="session",
                    domain_id=PROJECT,
                    weight=10.0,
                ),
                _signal(
                    kind="intent",
                    domain_id=LIFE_PLAN,
                    weight=10.0,
                ),
            ),
        )
    )

    session = _candidate(result, PROJECT)
    inferred = _candidate(result, LIFE_PLAN)

    assert session.confidence >= resolver.selection_policy.minimum_primary_confidence
    assert session.score < inferred.score
    assert result.primary_domain == PROJECT


def test_single_active_goal_domain_has_priority_over_stronger_ordinary_evidence():
    resolver = DefaultDomainResolver()

    result = resolver.resolve(
        _selection_context(
            signals=(
                _signal(
                    kind="goal",
                    domain_id=PROJECT,
                    weight=10.0,
                ),
                _signal(
                    kind="intent",
                    domain_id=LIFE_PLAN,
                    weight=10.0,
                ),
            ),
        )
    )

    goal = _candidate(result, PROJECT)
    inferred = _candidate(result, LIFE_PLAN)

    assert goal.confidence >= resolver.selection_policy.minimum_primary_confidence
    assert goal.score < inferred.score
    assert result.primary_domain == PROJECT


def test_same_session_and_goal_domain_does_not_duplicate_selected_domain():
    resolver = DefaultDomainResolver()

    result = resolver.resolve(
        _selection_context(
            signals=(
                _signal(
                    kind="session",
                    domain_id=PROJECT,
                    weight=10.0,
                ),
                _signal(
                    kind="goal",
                    domain_id=PROJECT,
                    weight=10.0,
                ),
            ),
        )
    )

    assert result.primary_domain == PROJECT
    assert PROJECT not in result.supporting_domains


def test_session_goal_disagreement_without_clear_lead_requires_clarification():
    resolver = DefaultDomainResolver()

    result = resolver.resolve(
        _selection_context(
            signals=(
                _signal(
                    kind="session",
                    domain_id=PROJECT,
                    weight=10.0,
                ),
                _signal(
                    kind="goal",
                    domain_id=LIFE_PLAN,
                    weight=10.0,
                ),
            ),
        )
    )

    assert result.requires_clarification is True
    assert set(result.ambiguous_domains) == {
        PROJECT,
        LIFE_PLAN,
    }


def test_session_goal_disagreement_allows_clear_normal_evidence_lead():
    resolver = DefaultDomainResolver()

    result = resolver.resolve(
        _selection_context(
            signals=(
                _signal(
                    kind="session",
                    domain_id=PROJECT,
                    weight=10.0,
                ),
                _signal(
                    kind="goal",
                    domain_id=LIFE_PLAN,
                    weight=10.0,
                ),
                _signal(
                    kind="intent",
                    domain_id=LIFE_PLAN,
                    weight=10.0,
                ),
            ),
        )
    )

    assert result.primary_domain == LIFE_PLAN
    assert result.requires_clarification is False


def test_inferred_primary_below_selection_confidence_floor_cannot_win():
    resolver = DefaultDomainResolver()

    result = resolver.resolve(
        _selection_context(
            available_domains=(GENERAL, PROJECT),
            authorized_domains=(GENERAL, PROJECT),
            signals=(
                _signal(
                    kind="intent",
                    domain_id=PROJECT,
                    confidence=0.69,
                ),
            ),
        )
    )

    project = _candidate(result, PROJECT)

    assert project.score >= resolver.scoring_policy.minimum_resolution_score
    assert result.primary_domain != PROJECT


def test_inferred_primary_at_or_above_selection_confidence_floor_can_win():
    resolver = DefaultDomainResolver()

    result = resolver.resolve(
        _selection_context(
            available_domains=(GENERAL, PROJECT),
            authorized_domains=(GENERAL, PROJECT),
            signals=(
                _signal(
                    kind="intent",
                    domain_id=PROJECT,
                    confidence=0.70,
                ),
            ),
        )
    )

    project = _candidate(result, PROJECT)

    assert project.score >= resolver.scoring_policy.minimum_resolution_score
    assert result.primary_domain == PROJECT


def test_explicit_primary_is_exempt_from_ordinary_primary_confidence_floor():
    scoring = DomainScoringPolicy(
        explicit_weight=50.0,
    )
    resolver = DefaultDomainResolver(
        scoring_policy=scoring,
    )

    result = resolver.resolve(
        _selection_context(
            explicit_domains=(PROJECT,),
            available_domains=(GENERAL, PROJECT),
            authorized_domains=(GENERAL, PROJECT),
        )
    )

    project = _candidate(result, PROJECT)

    assert project.confidence < 0.70
    assert result.primary_domain == PROJECT
