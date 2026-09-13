"""Phase 10.53 — Neurodivergence Domain bootstrap and resolver tests.

The real ``DefaultDomainResolver`` selects Neurodivergence for eligible
neurodevelopmental requests, keeps General as fallback for generic requests,
and never silently absorbs a Neurodivergence signal when Neurodivergence is
unavailable or unauthorized.

Health keeps medication/medical-safety authority: a signal that names Health
stays Health-primary, and Neurodivergence never becomes the owner of a
documented medical fact.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.enums import DomainResolutionStatus
from cmm.domains.general import GENERAL_DOMAIN_ID
from cmm.domains.identifiers import DomainId
from cmm.domains.neurodivergence import (
    NEURODIVERGENCE_DOMAIN_ID,
    build_standard_neurodivergence_domain_bootstrap,
)
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionSignal,
)

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)
GENERAL = DomainId(slug="general")
NEURODIVERGENCE = DomainId(slug="neurodivergence")
HEALTH = DomainId(slug="health")


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
) -> DomainResolutionContext:
    available = _registered(bootstrap) if available is None else available
    authorized = available if authorized is None else authorized
    return DomainResolutionContext(
        id="ctx1",
        objective=objective,
        available_domains=available,
        authorized_domains=authorized,
        explicit_domains=explicit,
        system_policy=None,
        signals=signals,
        created_at=NOW,
    )


def _signal(domain, value, confidence=0.9):
    return DomainResolutionSignal(
        kind="intent",
        source="test",
        value=value,
        domain_ids=(domain,),
        confidence=confidence,
        provenance={"source": "test"},
    )


def _neurodivergence_signal(value="neurodivergence-signal", confidence=0.9):
    return _signal(NEURODIVERGENCE, value, confidence)


# ── Bootstrap ────────────────────────────────────────────────────────────────


def test_bootstrap_composes_general_and_neurodivergence():
    bootstrap = build_standard_neurodivergence_domain_bootstrap()
    slugs = {definition.id.slug for definition in bootstrap.domain_registry.list()}

    assert slugs == {"general", "neurodivergence"}
    assert bootstrap.domain_registry.get(GENERAL_DOMAIN_ID) is not None
    assert bootstrap.domain_registry.get(NEURODIVERGENCE_DOMAIN_ID) is not None


def test_bootstrap_fallback_remains_general():
    bootstrap = build_standard_neurodivergence_domain_bootstrap()

    assert bootstrap.resolver.fallback_domain == DomainId(slug="general")


def test_bootstrap_registers_full_pack_on_shared_registries():
    bootstrap = build_standard_neurodivergence_domain_bootstrap()

    resources = [
        resource
        for resource in bootstrap.resource_registry.list_all()
        if resource.domain_id == NEURODIVERGENCE_DOMAIN_ID
    ]
    rules = [
        rule
        for rule in bootstrap.rule_registry.list_all()
        if rule.definition.domain_id == NEURODIVERGENCE_DOMAIN_ID
    ]
    operations = [
        operation
        for operation in bootstrap.operation_registry.list_definitions()
        if operation.domain_id == NEURODIVERGENCE_DOMAIN_ID
    ]

    assert len(resources) == 10
    assert len(rules) == 14
    assert len(operations) == 8
    assert (
        len(bootstrap.workflow_registry.list_for_domain(NEURODIVERGENCE_DOMAIN_ID)) == 8
    )
    assert (
        bootstrap.permission_registry.active_for_domain(NEURODIVERGENCE_DOMAIN_ID)
        is not None
    )
    assert bootstrap.profile_registry.get_by_domain(NEURODIVERGENCE) is not None


def test_bootstrap_operations_are_unavailable_by_default():
    bootstrap = build_standard_neurodivergence_domain_bootstrap()

    for operation in bootstrap.operation_registry.list_definitions():
        assert operation.enabled is False


def test_bootstrap_registers_the_pack_exactly_once():
    bootstrap = build_standard_neurodivergence_domain_bootstrap()
    registered = [
        definition.id
        for definition in bootstrap.domain_registry.list()
        if str(definition.id) == NEURODIVERGENCE_DOMAIN_ID
    ]

    assert len(registered) == 1


def test_bootstrap_does_not_register_sibling_packs_or_globally():
    """Neurodivergence does not require or auto-register an implemented sibling."""
    import sys

    bootstrap = build_standard_neurodivergence_domain_bootstrap()

    assert not bootstrap.domain_registry.contains("domain:mental-health")
    assert not bootstrap.domain_registry.contains("domain:health")
    assert bootstrap.domain_registry.contains(NEURODIVERGENCE_DOMAIN_ID)
    assert "cmm.domains.neurodivergence" in set(sys.modules)
    # A fresh registry is created per call; no global state is touched.
    from cmm.domains.registry import DomainRegistry

    assert DomainRegistry().list() == ()


def test_bootstrap_package_export_surface_includes_the_bootstrap():
    import cmm.domains.neurodivergence as package

    assert hasattr(package, "build_standard_neurodivergence_domain_bootstrap")
    assert hasattr(package, "NEURODIVERGENCE_BOOTSTRAP_NAME")


# ── Resolver ─────────────────────────────────────────────────────────────────


def test_neurodivergence_signal_selects_neurodivergence_when_authorized():
    bootstrap = build_standard_neurodivergence_domain_bootstrap()
    result = bootstrap.resolver.resolve(
        _ctx(
            bootstrap,
            objective=(
                "explore whether these social and sensory patterns could fit a "
                "hypothesis"
            ),
            signals=(_neurodivergence_signal(),),
        )
    )

    assert result.primary_domain == NEURODIVERGENCE


def test_explicit_neurodivergence_resolves_neurodivergence():
    bootstrap = build_standard_neurodivergence_domain_bootstrap()
    result = bootstrap.resolver.resolve(
        _ctx(
            bootstrap,
            objective="organize assessment evidence for a neuropsychological review",
            explicit=(NEURODIVERGENCE,),
            signals=(_neurodivergence_signal(),),
        )
    )

    assert result.primary_domain == NEURODIVERGENCE


def test_generic_request_resolves_to_general_not_neurodivergence():
    bootstrap = build_standard_neurodivergence_domain_bootstrap()
    result = bootstrap.resolver.resolve(
        _ctx(bootstrap, objective="a generic non-specialized request")
    )

    assert result.primary_domain == GENERAL


def test_unavailable_or_unauthorized_neurodivergence_is_not_absorbed():
    bootstrap = build_standard_neurodivergence_domain_bootstrap()
    result = bootstrap.resolver.resolve(
        _ctx(
            bootstrap,
            available=_registered(bootstrap),
            authorized=(GENERAL,),
            objective="explore a neurodevelopmental hypothesis",
            signals=(_neurodivergence_signal(),),
        )
    )

    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert any(
        reason.code == "DOMAIN_UNAUTHORIZED_REJECTED" for reason in result.reasons
    )


def test_neurodivergence_disabled_does_not_fall_back_to_general():
    bootstrap = build_standard_neurodivergence_domain_bootstrap()
    disabled = tuple(
        domain for domain in _registered(bootstrap) if domain != NEURODIVERGENCE
    )
    result = bootstrap.resolver.resolve(
        _ctx(
            bootstrap,
            available=disabled,
            authorized=disabled,
            objective="explore a neurodevelopmental hypothesis",
            signals=(_neurodivergence_signal(),),
        )
    )

    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False


def test_resolver_is_not_special_cased_for_neurodivergence():
    bootstrap = build_standard_neurodivergence_domain_bootstrap()
    result = bootstrap.resolver.resolve(
        _ctx(
            bootstrap,
            objective="generic request",
            signals=(_neurodivergence_signal(confidence=0.01),),
        )
    )

    # The canonical resolver is used, never a Neurodivergence-specific one.
    assert bootstrap.resolver.__class__.__name__ == "DefaultDomainResolver"
    assert result.primary_domain in {GENERAL, NEURODIVERGENCE, None}


@pytest.mark.parametrize(
    "objective",
    (
        "explore whether this could fit autism",
        "review developmental history across childhood and now",
        "prepare a structured evidence summary for a professional assessment",
        "compare plausible explanations for these executive-function patterns",
    ),
)
def test_eligible_objectives_reach_neurodivergence(objective):
    bootstrap = build_standard_neurodivergence_domain_bootstrap()
    result = bootstrap.resolver.resolve(
        _ctx(
            bootstrap,
            objective=objective,
            explicit=(NEURODIVERGENCE,),
            signals=(_neurodivergence_signal(),),
        )
    )

    assert result.primary_domain == NEURODIVERGENCE


# ── Sibling authority boundaries ─────────────────────────────────────────────


def _health_and_neurodivergence_bootstrap():
    """Compose Neurodivergence with the canonical Health pack."""
    from cmm.domains.health.integration import register_health_domain
    from cmm.domains.neurodivergence.bootstrap import (
        build_standard_neurodivergence_domain_bootstrap,
    )

    bootstrap = build_standard_neurodivergence_domain_bootstrap()
    register_health_domain(
        domain_registry=bootstrap.domain_registry,
        profile_registry=bootstrap.profile_registry,
        resource_registry=bootstrap.resource_registry,
        rule_registry=bootstrap.rule_registry,
        operation_registry=bootstrap.operation_registry,
        workflow_registry=bootstrap.workflow_registry,
        permission_registry=bootstrap.permission_registry,
    )
    return bootstrap


def test_health_medication_signal_keeps_health_primary():
    """Medication/medical-safety authority stays with Health."""
    bootstrap = _health_and_neurodivergence_bootstrap()
    result = bootstrap.resolver.resolve(
        _ctx(
            bootstrap,
            objective="review my documented medication contraindication",
            explicit=(HEALTH,),
            signals=(_signal(HEALTH, "documented-medication-contraindication"),),
        )
    )

    assert result.primary_domain == HEALTH
    assert result.primary_domain != NEURODIVERGENCE


def test_neurodivergence_alone_never_becomes_health_primary():
    """A neurodevelopmental request does not acquire medical authority."""
    bootstrap = _health_and_neurodivergence_bootstrap()
    result = bootstrap.resolver.resolve(
        _ctx(
            bootstrap,
            objective=(
                "explore why a reported medication effect might relate to my "
                "attention patterns"
            ),
            explicit=(NEURODIVERGENCE,),
            signals=(_neurodivergence_signal(),),
        )
    )

    assert result.primary_domain == NEURODIVERGENCE
    assert str(result.primary_domain) != "domain:health"


def test_bootstrap_does_not_mutate_health_or_mental_health_definitions():
    """Registering Neurodivergence never rewrites a sibling's declaration."""
    from cmm.domains.health.definition import build_health_domain_definition
    from cmm.domains.mental_health.definition import (
        build_mental_health_domain_definition,
    )

    health_before = build_health_domain_definition().to_dict()
    mental_health_before = build_mental_health_domain_definition().to_dict()

    build_standard_neurodivergence_domain_bootstrap()

    assert build_health_domain_definition().to_dict() == health_before
    assert build_mental_health_domain_definition().to_dict() == mental_health_before
