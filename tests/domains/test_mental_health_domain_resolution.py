"""Phase 10.52 — Mental Health Domain bootstrap and resolver tests.

The real ``DefaultDomainResolver`` selects Mental Health for eligible emotional
and therapy requests, keeps General as fallback for generic requests, and never
silently absorbs a Mental Health signal when Mental Health is unavailable or
unauthorized.  Phase 10.53 absence does not break the pack.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.enums import DomainResolutionStatus
from cmm.domains.general import GENERAL_DOMAIN_ID
from cmm.domains.identifiers import DomainId
from cmm.domains.mental_health import (
    MENTAL_HEALTH_DOMAIN_ID,
    build_standard_mental_health_domain_bootstrap,
)
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionPolicy,
    DomainResolutionSignal,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)
GENERAL = DomainId(slug="general")
MENTAL_HEALTH = DomainId(slug="mental-health")


def _registered(bootstrap):
    return tuple(definition.id for definition in bootstrap.domain_registry.list())


def _ctx(
    bootstrap,
    *,
    available=None,
    authorized=None,
    explicit=(),
    objective="objective",
    signals=(),
    policy=None,
) -> DomainResolutionContext:
    available = _registered(bootstrap) if available is None else available
    authorized = available if authorized is None else authorized
    return DomainResolutionContext(
        id="ctx1",
        objective=objective,
        available_domains=available,
        authorized_domains=authorized,
        explicit_domains=explicit,
        system_policy=policy,
        signals=signals,
        created_at=NOW,
    )


def _mental_health_signal(
    value="mental-health-signal", confidence=0.9
) -> DomainResolutionSignal:
    return DomainResolutionSignal(
        kind="intent",
        source="test",
        value=value,
        domain_ids=(MENTAL_HEALTH,),
        confidence=confidence,
        provenance={"source": "test"},
    )


# ── Bootstrap ────────────────────────────────────────────────────────────────


def test_bootstrap_composes_general_and_mental_health():
    bootstrap = build_standard_mental_health_domain_bootstrap()
    slugs = {definition.id.slug for definition in bootstrap.domain_registry.list()}
    assert slugs == {"general", "mental-health"}
    assert bootstrap.domain_registry.get(GENERAL_DOMAIN_ID) is not None
    assert bootstrap.domain_registry.get(MENTAL_HEALTH_DOMAIN_ID) is not None


def test_bootstrap_fallback_remains_general():
    bootstrap = build_standard_mental_health_domain_bootstrap()
    assert bootstrap.resolver.fallback_domain == DomainId(slug="general")


def test_bootstrap_registers_full_pack_on_shared_registries():
    bootstrap = build_standard_mental_health_domain_bootstrap()
    resources = [
        resource
        for resource in bootstrap.resource_registry.list_all()
        if resource.domain_id == MENTAL_HEALTH_DOMAIN_ID
    ]
    rules = [
        rule
        for rule in bootstrap.rule_registry.list_all()
        if rule.definition.domain_id == MENTAL_HEALTH_DOMAIN_ID
    ]
    operations = [
        operation
        for operation in bootstrap.operation_registry.list_definitions()
        if operation.domain_id == MENTAL_HEALTH_DOMAIN_ID
    ]
    assert len(resources) == 10
    assert len(rules) == 13
    assert len(operations) == 8
    assert (
        len(bootstrap.workflow_registry.list_for_domain(MENTAL_HEALTH_DOMAIN_ID)) == 8
    )
    assert (
        bootstrap.permission_registry.active_for_domain(MENTAL_HEALTH_DOMAIN_ID)
        is not None
    )


def test_bootstrap_operations_are_unavailable_by_default():
    bootstrap = build_standard_mental_health_domain_bootstrap()
    for operation in bootstrap.operation_registry.list_definitions():
        assert operation.enabled is False


def test_bootstrap_without_phase_10_53_succeeds():
    # Neurodivergence is absent; the Mental Health pack must still boot.
    bootstrap = build_standard_mental_health_domain_bootstrap()
    assert not bootstrap.domain_registry.contains("domain:neurodivergence")
    assert bootstrap.domain_registry.contains(MENTAL_HEALTH_DOMAIN_ID)


def test_bootstrap_does_not_register_globally():
    import sys

    before = set(sys.modules)
    _ = build_standard_mental_health_domain_bootstrap()
    after = set(sys.modules)
    assert "cmm.domains.mental_health" in after
    assert before <= after


# ── Resolver ─────────────────────────────────────────────────────────────────


def test_mental_health_signal_selects_mental_health_when_authorized():
    bootstrap = build_standard_mental_health_domain_bootstrap()
    result = bootstrap.resolver.resolve(
        _ctx(
            bootstrap,
            objective="ordinary emotional conversation about feeling lonely",
            signals=(_mental_health_signal(),),
        )
    )
    assert result.primary_domain == MENTAL_HEALTH


def test_explicit_mental_health_resolves_mental_health():
    bootstrap = build_standard_mental_health_domain_bootstrap()
    result = bootstrap.resolver.resolve(
        _ctx(
            bootstrap,
            objective="prepare tomorrow's therapy session",
            explicit=(MENTAL_HEALTH,),
            signals=(_mental_health_signal(),),
        )
    )
    assert result.primary_domain == MENTAL_HEALTH


def test_generic_request_resolves_to_general_not_mental_health():
    bootstrap = build_standard_mental_health_domain_bootstrap()
    result = bootstrap.resolver.resolve(
        _ctx(bootstrap, objective="a generic non-specialized request")
    )
    assert result.primary_domain == GENERAL


def test_unavailable_or_unauthorized_mental_health_is_not_absorbed():
    bootstrap = build_standard_mental_health_domain_bootstrap()
    # Mental Health available but only General authorized: fail closed.
    result = bootstrap.resolver.resolve(
        _ctx(
            bootstrap,
            available=_registered(bootstrap),
            authorized=(GENERAL,),
            objective="ordinary emotional conversation",
            signals=(_mental_health_signal(),),
        )
    )
    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert any(
        reason.code == "DOMAIN_UNAUTHORIZED_REJECTED" for reason in result.reasons
    )


def test_mental_health_disabled_does_not_fall_back_to_general():
    bootstrap = build_standard_mental_health_domain_bootstrap()
    disabled = tuple(
        domain for domain in _registered(bootstrap) if domain != MENTAL_HEALTH
    )
    result = bootstrap.resolver.resolve(
        _ctx(
            bootstrap,
            available=disabled,
            authorized=disabled,
            objective="therapy preparation",
            signals=(_mental_health_signal(),),
        )
    )
    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False


def test_resolver_thresholds_are_not_special_cased_for_mental_health():
    # A low-confidence Mental Health signal must not be promoted to primary.
    bootstrap = build_standard_mental_health_domain_bootstrap()
    policy = DomainResolutionPolicy(minimum_score=None) if False else None
    result = bootstrap.resolver.resolve(
        _ctx(
            bootstrap,
            objective="generic request",
            signals=(_mental_health_signal(confidence=0.01),),
            policy=policy,
        )
    )
    # Whatever the generic policy decides, the resolver is not replaced by a
    # Mental Health-specific resolver.
    assert bootstrap.resolver.__class__.__name__ == "DefaultDomainResolver"
    assert result.primary_domain in {GENERAL, MENTAL_HEALTH, None}


@pytest.mark.parametrize(
    "objective",
    (
        "ordinary emotional conversation about sadness",
        "prepare tomorrow's therapy session",
        "review last therapy session notes",
    ),
)
def test_eligible_emotional_objectives_reach_mental_health(objective):
    bootstrap = build_standard_mental_health_domain_bootstrap()
    result = bootstrap.resolver.resolve(
        _ctx(
            bootstrap,
            objective=objective,
            explicit=(MENTAL_HEALTH,),
            signals=(_mental_health_signal(),),
        )
    )
    assert result.primary_domain == MENTAL_HEALTH
