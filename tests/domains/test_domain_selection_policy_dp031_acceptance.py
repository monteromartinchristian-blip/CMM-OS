"""AT-DP-031 — connected acceptance for Phase 10.31 Domain Selection Policies."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone

import cmm.domains.selection as selection_module
from cmm.domains import (
    DefaultDomainComposer,
    DefaultDomainResolver,
    DomainCompositionStatus,
    DomainDefinition,
    DomainId,
    DomainKind,
    DomainManifestId,
    DomainRegistryRecord,
    DomainRegistrySnapshot,
    DomainResolutionContext,
    DomainResolutionContextBuilder,
    DomainResolutionPolicy,
    DomainResolutionSignal,
    DomainResolutionStatus,
    DomainScoringPolicy,
    DomainSelectionPolicy,
    DomainSelectionTransition,
    DomainStatus,
    build_domain_selection_transition,
)

NOW = datetime(2026, 8, 27, 20, 0, tzinfo=timezone.utc)

GENERAL = DomainId.from_str("domain:general")
PROJECT = DomainId.from_str("domain:project")
LIFE_PLAN = DomainId.from_str("domain:life-plan")
REFLECTION = DomainId.from_str("domain:reflection")


def _signal(
    domain_id: DomainId,
    *,
    confidence: float | None = 1.0,
    weight: float = 1.0,
    kind: str = "intent",
) -> DomainResolutionSignal:
    return DomainResolutionSignal(
        kind=kind,
        source="at-dp031",
        value=f"{kind}:{domain_id.slug}",
        domain_ids=(domain_id,),
        confidence=confidence,
        weight=weight,
        provenance=({"source": "at-dp031"} if confidence is not None else None),
    )


def _definition(slug: str) -> DomainDefinition:
    return DomainDefinition(
        id=DomainId.from_str(f"domain:{slug}"),
        name=slug,
        display_name=slug.replace("-", " ").title(),
        version="1.0.0",
        kind=DomainKind.CORE,
        description=f"AT-DP-031 fixture for {slug}",
        manifest_id=DomainManifestId(
            slug=slug,
            version="1.0.0",
        ),
        enabled=True,
    )


def _record(
    slug: str,
    *,
    status: DomainStatus = DomainStatus.ACTIVE,
) -> DomainRegistryRecord:
    return DomainRegistryRecord(
        definition=_definition(slug),
        status=status,
        registered_at=NOW,
        updated_at=NOW,
    )


def _snapshot() -> DomainRegistrySnapshot:
    return DomainRegistrySnapshot(
        captured_at=NOW,
        records=[
            _record("general"),
            _record("project"),
            _record("life-plan"),
            _record("reflection"),
        ],
    )


def _resolver(
    *,
    selection_policy: DomainSelectionPolicy | None = None,
    scoring_policy: DomainScoringPolicy | None = None,
    resolution_id: str = "resolution-at-dp031",
) -> DefaultDomainResolver:
    return DefaultDomainResolver(
        selection_policy=selection_policy,
        scoring_policy=scoring_policy,
        id_factory=lambda: resolution_id,
        clock=lambda: NOW,
    )


def _context(
    *,
    explicit_domains: tuple[DomainId, ...] = (),
    signals: tuple[DomainResolutionSignal, ...] = (),
    system_policy: DomainResolutionPolicy | None = None,
    available_domains: tuple[DomainId, ...] = (
        GENERAL,
        PROJECT,
        LIFE_PLAN,
        REFLECTION,
    ),
    authorized_domains: tuple[DomainId, ...] = (
        GENERAL,
        PROJECT,
        LIFE_PLAN,
        REFLECTION,
    ),
    context_id: str = "ctx-at-dp031",
) -> DomainResolutionContext:
    return DomainResolutionContext(
        id=context_id,
        user_input="AT-DP-031 acceptance fixture",
        explicit_domains=explicit_domains,
        available_domains=available_domains,
        authorized_domains=authorized_domains,
        signals=signals,
        system_policy=system_policy,
        created_at=NOW,
    )


def test_at_dp031_01_selection_policy_contract():
    """AT-DP-031-01: canonical immutable selection policy contract."""

    policy = DomainSelectionPolicy()

    assert policy.explicit_domain_priority is True
    assert policy.session_domain_priority is True
    assert policy.goal_domain_priority is True
    assert policy.allow_multi_domain is True
    assert policy.maximum_supporting_domains == 3
    assert policy.minimum_primary_confidence == 0.70
    assert policy.minimum_supporting_confidence == 0.55
    assert policy.fallback_domain == GENERAL
    assert policy.ambiguity_strategy == "clarify_or_fallback"
    assert DomainSelectionPolicy.from_dict(policy.to_dict()) == policy


def test_at_dp031_02_explicit_priority_over_ordinary_evidence():
    """AT-DP-031-02: one eligible explicit domain wins ordinary scoring."""

    result = _resolver().resolve(
        _context(
            explicit_domains=(PROJECT,),
            signals=(
                _signal(
                    LIFE_PLAN,
                    confidence=1.0,
                    weight=20.0,
                ),
            ),
        )
    )

    assert result.status == DomainResolutionStatus.RESOLVED
    assert result.primary_domain == PROJECT


def test_at_dp031_03_safety_precedes_explicit_selection():
    """AT-DP-031-03: safety denial overrides explicit selection."""

    result = _resolver().resolve(
        _context(
            explicit_domains=(PROJECT,),
            signals=(_signal(PROJECT),),
            system_policy=DomainResolutionPolicy(
                denied_domains=(PROJECT,),
                require_authorization=False,
            ),
            authorized_domains=(),
            available_domains=(GENERAL, PROJECT),
        )
    )

    assert result.status == DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert PROJECT in result.rejected_domains
    assert any(reason.code == "DOMAIN_POLICY_DENIED" for reason in result.reasons)


def test_at_dp031_04_multiple_explicit_domains_are_ambiguous_regardless_of_score_gap():
    """AT-DP-031-04: explicit ambiguity may never be broken by ordinary scoring."""

    context = _context(
        explicit_domains=(PROJECT, LIFE_PLAN),
        available_domains=(PROJECT, LIFE_PLAN),
        authorized_domains=(PROJECT, LIFE_PLAN),
        signals=(
            _signal(
                PROJECT,
                confidence=1.0,
                weight=10.0,
            ),
        ),
        context_id="ctx-at-dp031-explicit-ambiguity",
    )

    result = _resolver(resolution_id="resolution-at-dp031-explicit-ambiguity").resolve(
        context
    )

    assert result.status == DomainResolutionStatus.AMBIGUOUS
    assert result.primary_domain is None
    assert {domain.slug for domain in result.ambiguous_domains} == {
        "project",
        "life-plan",
    }
    assert result.requires_clarification is True


def test_at_dp031_05_session_continuity_precedes_ordinary_evidence():
    """AT-DP-031-05: structured session continuity has declared precedence."""

    builder = DomainResolutionContextBuilder(
        clock=lambda: NOW,
        id_factory=lambda: "ctx-at-dp031-session",
    )
    context = builder.build(
        registry_snapshot=_snapshot(),
        user_input="continue the session",
        session_domain=LIFE_PLAN,
        authorized_domains=(
            GENERAL,
            PROJECT,
            LIFE_PLAN,
            REFLECTION,
        ),
        signals=(
            _signal(
                PROJECT,
                confidence=1.0,
                weight=10.0,
            ),
        ),
    )

    result = _resolver(resolution_id="resolution-at-dp031-session").resolve(context)

    assert any(
        signal.kind == "session" and LIFE_PLAN in signal.domain_ids
        for signal in context.signals
    )
    assert result.status == DomainResolutionStatus.RESOLVED
    assert result.primary_domain == LIFE_PLAN


def test_at_dp031_06_active_goal_precedes_ordinary_evidence():
    """AT-DP-031-06: structured active-goal domain has declared precedence."""

    builder = DomainResolutionContextBuilder(
        clock=lambda: NOW,
        id_factory=lambda: "ctx-at-dp031-goal",
    )
    context = builder.build(
        registry_snapshot=_snapshot(),
        user_input="continue active goal",
        active_goal_domain=REFLECTION,
        authorized_domains=(
            GENERAL,
            PROJECT,
            LIFE_PLAN,
            REFLECTION,
        ),
        signals=(
            _signal(
                PROJECT,
                confidence=1.0,
                weight=10.0,
            ),
        ),
    )

    result = _resolver(resolution_id="resolution-at-dp031-goal").resolve(context)

    assert any(
        signal.kind == "goal" and REFLECTION in signal.domain_ids
        for signal in context.signals
    )
    assert result.status == DomainResolutionStatus.RESOLVED
    assert result.primary_domain == REFLECTION


def test_at_dp031_07_session_goal_disagreement_requires_resolution_evidence():
    """AT-DP-031-07: session/goal disagreement is not arbitrarily tie-broken."""

    builder = DomainResolutionContextBuilder(
        clock=lambda: NOW,
        id_factory=lambda: "ctx-at-dp031-session-goal",
    )
    context = builder.build(
        registry_snapshot=_snapshot(),
        user_input="session and goal disagree",
        session_domain=PROJECT,
        active_goal_domain=LIFE_PLAN,
        authorized_domains=(
            GENERAL,
            PROJECT,
            LIFE_PLAN,
            REFLECTION,
        ),
    )

    result = _resolver(resolution_id="resolution-at-dp031-session-goal").resolve(
        context
    )

    assert result.status == DomainResolutionStatus.AMBIGUOUS
    assert result.requires_clarification is True
    assert {d.slug for d in result.ambiguous_domains} >= {
        "project",
        "life-plan",
    }


def test_at_dp031_08_primary_selection_confidence_floor_is_070():
    """AT-DP-031-08: declared primary confidence boundary is inclusive."""

    below = _resolver(resolution_id="resolution-at-dp031-primary-below").resolve(
        _context(
            signals=(
                _signal(
                    PROJECT,
                    confidence=0.69,
                ),
            ),
            context_id="ctx-at-dp031-primary-below",
        )
    )

    boundary = _resolver(resolution_id="resolution-at-dp031-primary-boundary").resolve(
        _context(
            signals=(
                _signal(
                    PROJECT,
                    confidence=0.70,
                ),
            ),
            context_id="ctx-at-dp031-primary-boundary",
        )
    )

    assert below.primary_domain != PROJECT
    assert boundary.status == DomainResolutionStatus.RESOLVED
    assert boundary.primary_domain == PROJECT


def test_at_dp031_09_high_impact_uses_most_restrictive_confidence_floor():
    """AT-DP-031-09: system policy may raise but never weaken high-impact floor."""

    result = _resolver(
        scoring_policy=DomainScoringPolicy(
            high_impact_minimum_confidence=0.80,
        ),
        selection_policy=DomainSelectionPolicy(
            minimum_primary_confidence=0.70,
        ),
        resolution_id="resolution-at-dp031-high-impact",
    ).resolve(
        _context(
            explicit_domains=(PROJECT,),
            signals=(
                _signal(
                    PROJECT,
                    confidence=0.85,
                ),
            ),
            system_policy=DomainResolutionPolicy(
                high_impact_domains=(PROJECT,),
                minimum_confidence=0.90,
            ),
            context_id="ctx-at-dp031-high-impact",
        )
    )

    assert result.status != DomainResolutionStatus.RESOLVED
    assert any(
        reason.code == "DOMAIN_HIGH_IMPACT_LOW_CONFIDENCE" for reason in result.reasons
    )


def test_at_dp031_10_supporting_confidence_floor_is_055():
    """AT-DP-031-10: 0.54 is rejected while 0.55 is eligible supporting evidence."""

    result = _resolver(
        scoring_policy=DomainScoringPolicy(
            intent_weight=1000.0,
            supporting_margin=1000.0,
            max_supporting_domains=5,
        ),
        resolution_id="resolution-at-dp031-supporting-confidence",
    ).resolve(
        _context(
            explicit_domains=(PROJECT,),
            signals=(
                _signal(
                    LIFE_PLAN,
                    confidence=0.54,
                ),
                _signal(
                    REFLECTION,
                    confidence=0.55,
                ),
            ),
            context_id="ctx-at-dp031-supporting-confidence",
        )
    )

    supporting = {domain.slug for domain in result.supporting_domains}

    assert "life-plan" not in supporting
    assert "reflection" in supporting


def test_at_dp031_11_multi_domain_can_be_disabled():
    """AT-DP-031-11: allow_multi_domain=False disables ordinary supporting domains."""

    result = _resolver(
        selection_policy=DomainSelectionPolicy(
            allow_multi_domain=False,
        ),
        scoring_policy=DomainScoringPolicy(
            intent_weight=1000.0,
            supporting_margin=1000.0,
        ),
        resolution_id="resolution-at-dp031-single-domain",
    ).resolve(
        _context(
            explicit_domains=(PROJECT,),
            signals=(_signal(LIFE_PLAN),),
            context_id="ctx-at-dp031-single-domain",
        )
    )

    assert result.status == DomainResolutionStatus.RESOLVED
    assert result.primary_domain == PROJECT
    assert result.supporting_domains == ()


def test_at_dp031_12_selection_supporting_limit_is_hard():
    """AT-DP-031-12: selection cap cannot be widened by scoring policy."""

    result = _resolver(
        selection_policy=DomainSelectionPolicy(
            maximum_supporting_domains=1,
        ),
        scoring_policy=DomainScoringPolicy(
            intent_weight=1000.0,
            supporting_margin=1000.0,
            max_supporting_domains=5,
        ),
        resolution_id="resolution-at-dp031-supporting-cap",
    ).resolve(
        _context(
            explicit_domains=(PROJECT,),
            signals=(
                _signal(LIFE_PLAN),
                _signal(REFLECTION),
            ),
            context_id="ctx-at-dp031-supporting-cap",
        )
    )

    assert len(result.supporting_domains) == 1


def test_at_dp031_13_general_is_canonical_fallback():
    """AT-DP-031-13: General is canonical fallback for weak specialized evidence."""

    result = _resolver(resolution_id="resolution-at-dp031-general-fallback").resolve(
        _context(
            signals=(
                _signal(
                    PROJECT,
                    confidence=0.69,
                    weight=10.0,
                ),
            ),
            available_domains=(GENERAL, PROJECT),
            authorized_domains=(GENERAL, PROJECT),
            context_id="ctx-at-dp031-general-fallback",
        )
    )

    assert result.status == DomainResolutionStatus.INSUFFICIENT_INFORMATION
    assert result.primary_domain == GENERAL
    assert result.supporting_domains == ()
    assert result.fallback_used is True
    assert any(reason.code == "DOMAIN_FALLBACK_SELECTED" for reason in result.reasons)


def test_at_dp031_14_general_fallback_is_fail_closed():
    """AT-DP-031-14: denied General cannot be used as fallback."""

    result = _resolver(resolution_id="resolution-at-dp031-fail-closed").resolve(
        _context(
            signals=(
                _signal(
                    PROJECT,
                    confidence=0.69,
                    weight=10.0,
                ),
            ),
            system_policy=DomainResolutionPolicy(
                denied_domains=(GENERAL,),
                require_authorization=False,
            ),
            available_domains=(GENERAL, PROJECT),
            authorized_domains=(),
            context_id="ctx-at-dp031-fail-closed",
        )
    )

    assert result.status == DomainResolutionStatus.INSUFFICIENT_INFORMATION
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert GENERAL in result.rejected_domains
    assert not any(
        reason.code == "DOMAIN_FALLBACK_SELECTED" for reason in result.reasons
    )


def test_at_dp031_15_ambiguity_strategy_requires_clarification():
    """AT-DP-031-15: clarify_or_fallback preserves explicit ambiguity."""

    result = _resolver(
        selection_policy=DomainSelectionPolicy(
            ambiguity_strategy="clarify_or_fallback",
        ),
        resolution_id="resolution-at-dp031-ambiguity-strategy",
    ).resolve(
        _context(
            explicit_domains=(PROJECT, LIFE_PLAN),
            context_id="ctx-at-dp031-ambiguity-strategy",
        )
    )

    assert result.status == DomainResolutionStatus.AMBIGUOUS
    assert result.requires_clarification is True
    assert {d.slug for d in result.ambiguous_domains} == {
        "project",
        "life-plan",
    }


def _transition_fixture() -> DomainSelectionTransition:
    previous = _resolver(
        selection_policy=DomainSelectionPolicy(
            allow_multi_domain=False,
        ),
        resolution_id="resolution-at-dp031-before",
    ).resolve(
        _context(
            explicit_domains=(PROJECT,),
            context_id="ctx-at-dp031-before",
        )
    )

    current = _resolver(
        selection_policy=DomainSelectionPolicy(
            allow_multi_domain=False,
        ),
        resolution_id="resolution-at-dp031-after",
    ).resolve(
        _context(
            explicit_domains=(LIFE_PLAN,),
            context_id="ctx-at-dp031-after",
        )
    )

    return build_domain_selection_transition(
        previous,
        current,
    )


def test_at_dp031_16_transition_preserves_exact_resolution_identity_and_change():
    """AT-DP-031-16: transition records exact before/after IDs and primary change."""

    transition = _transition_fixture()

    assert transition.previous_resolution_id == "resolution-at-dp031-before"
    assert transition.new_resolution_id == "resolution-at-dp031-after"
    assert transition.previous_primary_domain == PROJECT
    assert transition.new_primary_domain == LIFE_PLAN
    assert transition.primary_changed is True


def test_at_dp031_17_transition_reason_codes_are_declarative():
    """AT-DP-031-17: reevaluation reasons are explicit and deterministic."""

    transition = _transition_fixture()

    assert transition.reason_codes == (
        "DOMAIN_SELECTION_REEVALUATED",
        "DOMAIN_SELECTION_PRIMARY_CHANGED",
    )


def test_at_dp031_18_changed_selection_requires_recomposition():
    """AT-DP-031-18: composition invalidation is declarative."""

    transition = _transition_fixture()

    assert transition.requires_recomposition is True


def test_at_dp031_19_session_update_is_declarative_only():
    """AT-DP-031-19: session update requirement is surfaced without mutation."""

    transition = _transition_fixture()

    assert transition.requires_session_update is True


def test_at_dp031_20_transition_has_no_operation_replay_or_side_effect_path():
    """AT-DP-031-20: reevaluation helper remains pure and operation-free."""

    source = inspect.getsource(build_domain_selection_transition)

    assert "execute(" not in source
    assert "operation_orchestrator" not in source
    assert "workflow_orchestrator" not in source
    assert "session_store" not in source


def test_at_dp031_21_connected_builder_resolver_composer_transition_chain():
    """AT-DP-031-21: real builder→resolver→composer→resolver→transition chain."""

    snapshot = _snapshot()

    before_context = DomainResolutionContextBuilder(
        clock=lambda: NOW,
        id_factory=lambda: "ctx-at-dp031-connected-before",
    ).build(
        registry_snapshot=snapshot,
        user_input="work on the project",
        explicit_domains=(PROJECT,),
        authorized_domains=(
            GENERAL,
            PROJECT,
            LIFE_PLAN,
            REFLECTION,
        ),
    )

    before = _resolver(
        selection_policy=DomainSelectionPolicy(
            allow_multi_domain=False,
        ),
        resolution_id="resolution-at-dp031-connected-before",
    ).resolve(before_context)

    composition = DefaultDomainComposer(
        clock=lambda: NOW,
        id_factory=lambda: "composition-at-dp031",
    ).compose(
        before,
        (_definition("project"),),
    )

    after_context = DomainResolutionContextBuilder(
        clock=lambda: NOW,
        id_factory=lambda: "ctx-at-dp031-connected-after",
    ).build(
        registry_snapshot=snapshot,
        user_input="switch to life plan",
        explicit_domains=(LIFE_PLAN,),
        session_domain=PROJECT,
        authorized_domains=(
            GENERAL,
            PROJECT,
            LIFE_PLAN,
            REFLECTION,
        ),
    )

    after = _resolver(
        selection_policy=DomainSelectionPolicy(
            allow_multi_domain=False,
        ),
        resolution_id="resolution-at-dp031-connected-after",
    ).resolve(after_context)

    transition = build_domain_selection_transition(
        before,
        after,
    )

    assert before.primary_domain == PROJECT
    assert composition.status == DomainCompositionStatus.COMPOSED
    assert composition.resolution_id == before.id
    assert composition.primary_domain == PROJECT
    assert after.primary_domain == LIFE_PLAN
    assert transition.previous_resolution_id == before.id
    assert transition.new_resolution_id == after.id
    assert transition.primary_changed is True
    assert transition.requires_recomposition is True
    assert transition.requires_session_update is True


def test_at_dp031_22_selection_layer_preserves_runtime_execution_boundary():
    """AT-DP-031-22: selection remains a pure domain-layer mechanism."""

    source = inspect.getsource(selection_module)

    forbidden_dependencies = (
        "cmm.agent_runtime",
        "operation_orchestrator",
        "workflow_orchestrator",
        "execute_operation",
        "execute_workflow",
        "session_store",
    )

    for dependency in forbidden_dependencies:
        assert dependency not in source
