from datetime import datetime, timezone

from cmm.domains.identifiers import DomainId
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionPolicy,
    DomainResolutionSignal,
)
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resolver_contracts import DomainScoringPolicy
from cmm.domains.selection_contracts import DomainSelectionPolicy

NOW = datetime(2026, 8, 27, 19, 0, tzinfo=timezone.utc)

GENERAL = DomainId.from_str("domain:general")
PROJECT = DomainId.from_str("domain:project")
LIFE_PLAN = DomainId.from_str("domain:life-plan")
REFLECTION = DomainId.from_str("domain:reflection")
RELATIONSHIPS = DomainId.from_str("domain:relationships")


def _signal(
    domain_id: DomainId,
    *,
    confidence: float = 1.0,
) -> DomainResolutionSignal:
    return DomainResolutionSignal(
        kind="intent",
        source="task5-adversarial",
        value=f"evidence-{domain_id.slug}",
        domain_ids=(domain_id,),
        confidence=confidence,
        weight=1.0,
        provenance={"source": "task5_fixture"},
    )


def _context(
    *,
    supporters: tuple[tuple[DomainId, float], ...],
) -> DomainResolutionContext:
    domains = (
        GENERAL,
        PROJECT,
        *(domain_id for domain_id, _ in supporters),
    )

    return DomainResolutionContext(
        id="ctx-task5",
        user_input="structured multi-domain selection fixture",
        explicit_domains=(PROJECT,),
        available_domains=domains,
        authorized_domains=domains,
        signals=tuple(
            _signal(domain_id, confidence=confidence)
            for domain_id, confidence in supporters
        ),
        created_at=NOW,
    )


def _resolver(
    *,
    selection_policy: DomainSelectionPolicy,
) -> DefaultDomainResolver:
    return DefaultDomainResolver(
        scoring_policy=DomainScoringPolicy(
            intent_weight=1000.0,
            supporting_margin=1000.0,
            max_supporting_domains=5,
        ),
        selection_policy=selection_policy,
        id_factory=lambda: "resolution-task5",
        clock=lambda: NOW,
    )


def test_allow_multi_domain_false_forbids_all_supporting_domains():
    resolver = _resolver(
        selection_policy=DomainSelectionPolicy(
            allow_multi_domain=False,
        )
    )

    result = resolver.resolve(
        _context(
            supporters=(
                (LIFE_PLAN, 1.0),
                (REFLECTION, 1.0),
            )
        )
    )

    assert result.primary_domain == PROJECT
    assert result.supporting_domains == ()


def test_selection_policy_hard_caps_supporting_domains():
    resolver = _resolver(
        selection_policy=DomainSelectionPolicy(
            maximum_supporting_domains=1,
        )
    )

    result = resolver.resolve(
        _context(
            supporters=(
                (LIFE_PLAN, 1.0),
                (REFLECTION, 1.0),
                (RELATIONSHIPS, 1.0),
            )
        )
    )

    assert result.primary_domain == PROJECT
    assert len(result.supporting_domains) == 1


def test_supporting_candidate_below_055_declared_confidence_is_excluded():
    resolver = _resolver(
        selection_policy=DomainSelectionPolicy(
            minimum_supporting_confidence=0.55,
        )
    )

    result = resolver.resolve(
        _context(
            supporters=(
                (LIFE_PLAN, 0.54),
                (REFLECTION, 0.55),
            )
        )
    )

    assert result.primary_domain == PROJECT
    assert LIFE_PLAN not in result.supporting_domains
    assert REFLECTION in result.supporting_domains


def test_supporting_confidence_boundary_is_inclusive_at_055():
    resolver = _resolver(
        selection_policy=DomainSelectionPolicy(
            minimum_supporting_confidence=0.55,
        )
    )

    result = resolver.resolve(_context(supporters=((REFLECTION, 0.55),)))

    assert result.primary_domain == PROJECT
    assert REFLECTION in result.supporting_domains


def test_selection_cap_is_stricter_than_scoring_policy_cap():
    resolver = _resolver(
        selection_policy=DomainSelectionPolicy(
            maximum_supporting_domains=2,
        )
    )

    assert resolver.scoring_policy.max_supporting_domains == 5

    result = resolver.resolve(
        _context(
            supporters=(
                (LIFE_PLAN, 1.0),
                (REFLECTION, 1.0),
                (RELATIONSHIPS, 1.0),
            )
        )
    )

    assert result.primary_domain == PROJECT
    assert len(result.supporting_domains) == 2


# ---------------------------------------------------------------------------
# Phase 10.31 Task 5B — high-impact floor + required-domain cap conflict
# ---------------------------------------------------------------------------


def _high_impact_context(
    *,
    declared_confidence: float,
    system_minimum_confidence: float,
) -> DomainResolutionContext:
    policy = DomainResolutionPolicy(
        high_impact_domains=(PROJECT,),
        minimum_confidence=system_minimum_confidence,
    )

    return DomainResolutionContext(
        id="ctx-task5-high-impact",
        user_input="structured high-impact selection fixture",
        explicit_domains=(PROJECT,),
        available_domains=(GENERAL, PROJECT),
        authorized_domains=(GENERAL, PROJECT),
        signals=(
            _signal(
                PROJECT,
                confidence=declared_confidence,
            ),
        ),
        system_policy=policy,
        created_at=NOW,
    )


def test_high_impact_uses_scoring_floor_when_system_floor_is_lower():
    resolver = DefaultDomainResolver(
        scoring_policy=DomainScoringPolicy(
            high_impact_minimum_confidence=0.80,
        ),
        selection_policy=DomainSelectionPolicy(
            minimum_primary_confidence=0.70,
        ),
        id_factory=lambda: "resolution-high-impact",
        clock=lambda: NOW,
    )

    result = resolver.resolve(
        _high_impact_context(
            declared_confidence=0.75,
            system_minimum_confidence=0.60,
        )
    )

    assert result.status.value != "resolved"
    assert result.primary_domain != PROJECT
    assert any(
        reason.code == "DOMAIN_HIGH_IMPACT_LOW_CONFIDENCE" for reason in result.reasons
    )


def test_high_impact_boundary_at_effective_080_is_inclusive():
    resolver = DefaultDomainResolver(
        scoring_policy=DomainScoringPolicy(
            high_impact_minimum_confidence=0.80,
        ),
        selection_policy=DomainSelectionPolicy(
            minimum_primary_confidence=0.70,
        ),
        id_factory=lambda: "resolution-high-impact-boundary",
        clock=lambda: NOW,
    )

    result = resolver.resolve(
        _high_impact_context(
            declared_confidence=0.80,
            system_minimum_confidence=0.60,
        )
    )

    assert result.status.value == "resolved"
    assert result.primary_domain == PROJECT


def test_high_impact_system_floor_can_raise_effective_floor_to_090():
    resolver = DefaultDomainResolver(
        scoring_policy=DomainScoringPolicy(
            high_impact_minimum_confidence=0.80,
        ),
        selection_policy=DomainSelectionPolicy(
            minimum_primary_confidence=0.70,
        ),
        id_factory=lambda: "resolution-high-impact-system-floor",
        clock=lambda: NOW,
    )

    result = resolver.resolve(
        _high_impact_context(
            declared_confidence=0.85,
            system_minimum_confidence=0.90,
        )
    )

    assert result.status.value != "resolved"
    assert result.primary_domain != PROJECT
    assert any(
        reason.code == "DOMAIN_HIGH_IMPACT_LOW_CONFIDENCE" for reason in result.reasons
    )


def test_high_impact_boundary_at_system_floor_090_is_inclusive():
    resolver = DefaultDomainResolver(
        scoring_policy=DomainScoringPolicy(
            high_impact_minimum_confidence=0.80,
        ),
        selection_policy=DomainSelectionPolicy(
            minimum_primary_confidence=0.70,
        ),
        id_factory=lambda: "resolution-high-impact-system-boundary",
        clock=lambda: NOW,
    )

    result = resolver.resolve(
        _high_impact_context(
            declared_confidence=0.90,
            system_minimum_confidence=0.90,
        )
    )

    assert result.status.value == "resolved"
    assert result.primary_domain == PROJECT


def test_required_supporting_domains_over_hard_cap_fail_closed():
    resolver = _resolver(
        selection_policy=DomainSelectionPolicy(
            maximum_supporting_domains=1,
        )
    )

    system_policy = DomainResolutionPolicy(
        required_domains=(
            LIFE_PLAN,
            REFLECTION,
        ),
    )

    context = DomainResolutionContext(
        id="ctx-task5-required-overflow",
        user_input="required domains exceed supporting limit",
        explicit_domains=(PROJECT,),
        available_domains=(
            GENERAL,
            PROJECT,
            LIFE_PLAN,
            REFLECTION,
        ),
        authorized_domains=(
            GENERAL,
            PROJECT,
            LIFE_PLAN,
            REFLECTION,
        ),
        signals=(
            _signal(LIFE_PLAN),
            _signal(REFLECTION),
        ),
        system_policy=system_policy,
        created_at=NOW,
    )

    result = resolver.resolve(context)

    assert result.status.value != "resolved"
    assert result.primary_domain is None
    assert result.supporting_domains == ()
    assert any(
        reason.code == "DOMAIN_SELECTION_REQUIRED_DOMAIN_LIMIT_CONFLICT"
        for reason in result.reasons
    )


def test_required_supporting_domain_conflicts_with_multi_domain_disabled():
    resolver = _resolver(
        selection_policy=DomainSelectionPolicy(
            allow_multi_domain=False,
        )
    )

    system_policy = DomainResolutionPolicy(
        required_domains=(LIFE_PLAN,),
    )

    context = DomainResolutionContext(
        id="ctx-task5-required-single-domain",
        user_input="required supporting domain with multi-domain disabled",
        explicit_domains=(PROJECT,),
        available_domains=(
            GENERAL,
            PROJECT,
            LIFE_PLAN,
        ),
        authorized_domains=(
            GENERAL,
            PROJECT,
            LIFE_PLAN,
        ),
        signals=(_signal(LIFE_PLAN),),
        system_policy=system_policy,
        created_at=NOW,
    )

    result = resolver.resolve(context)

    assert result.status.value != "resolved"
    assert result.primary_domain is None
    assert result.supporting_domains == ()
    assert any(
        reason.code == "DOMAIN_SELECTION_REQUIRED_DOMAIN_LIMIT_CONFLICT"
        for reason in result.reasons
    )
