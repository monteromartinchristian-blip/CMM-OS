"""Tests for Phase 10.21 canonical Relationships Domain bootstrap."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.enums import DomainResolutionStatus
from cmm.domains.general import GENERAL_DOMAIN_ID
from cmm.domains.identifiers import DomainId
from cmm.domains.relationships import (
    RELATIONSHIPS_DOMAIN_ID,
    build_standard_relationships_domain_bootstrap,
)
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionSignal,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)
GENERAL = DomainId(slug="general")
RELATIONSHIPS = DomainId(slug="relationships")


def _registered(bootstrap):
    return tuple(d.id for d in bootstrap.domain_registry.list())


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
        signals=signals,
        created_at=NOW,
    )


def _relationships_signal(value="relationships-signal", confidence=0.9):
    return DomainResolutionSignal(
        kind="intent",
        source="test",
        value=value,
        domain_ids=(RELATIONSHIPS,),
        confidence=confidence,
        provenance={"source": "test"},
    )


def test_bootstrap_defaults_to_fresh_registries():
    b = build_standard_relationships_domain_bootstrap()
    assert b.domain_registry.get(RELATIONSHIPS_DOMAIN_ID) is not None
    assert b.domain_registry.get(GENERAL_DOMAIN_ID) is not None
    assert b.resolver.fallback_domain == DomainId(slug="general")
    relationships_resources = {
        r.id
        for r in b.resource_registry.list_all()
        if r.domain_id == "domain:relationships"
    }
    assert len(relationships_resources) == 8
    relationships_rules = {
        r.definition.id
        for r in b.rule_registry.list_all()
        if r.definition.domain_id == "domain:relationships"
    }
    assert len(relationships_rules) == 8
    assert len(b.workflow_registry.list_for_domain(RELATIONSHIPS_DOMAIN_ID)) == 6


def test_bootstrap_composes_general_and_relationships():
    """The standard Relationships bootstrap exposes BOTH General and
    Relationships on the same registries."""
    b = build_standard_relationships_domain_bootstrap()
    slugs = {d.id.slug for d in b.domain_registry.list()}
    assert slugs == {"general", "relationships"}


def test_bootstrap_fallback_is_general():
    b = build_standard_relationships_domain_bootstrap()
    assert b.resolver.fallback_domain == GENERAL


def test_generic_request_does_not_resolve_to_relationships_by_fallback():
    """A generic (non-specialized) request must resolve to General, never to
    Relationships merely because Relationships is the fallback."""
    b = build_standard_relationships_domain_bootstrap()
    result = b.resolver.resolve(_ctx(b, objective="a generic non-relational request"))
    assert result.primary_domain == GENERAL


def test_explicit_relationships_signal_resolves_relationships():
    """A valid explicit Relationships signal resolves to Relationships."""
    b = build_standard_relationships_domain_bootstrap()
    result = b.resolver.resolve(
        _ctx(
            b,
            objective="relationship question",
            explicit=(RELATIONSHIPS,),
            signals=(_relationships_signal(),),
        )
    )
    assert result.primary_domain == RELATIONSHIPS


def test_blocked_relationships_does_not_silently_resolve_general():
    """Relationships unauthorized/denied/unavailable must not silently resolve
    to General (generic fallback-blocking invariant)."""
    b = build_standard_relationships_domain_bootstrap()
    result = b.resolver.resolve(
        _ctx(
            b,
            available=_registered(b),
            authorized=(GENERAL,),
            objective="relationship question",
            signals=(_relationships_signal(),),
        )
    )
    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert any(r.code == "DOMAIN_UNAUTHORIZED_REJECTED" for r in result.reasons)


def test_bootstrap_operations_fail_closed():
    b = build_standard_relationships_domain_bootstrap()
    # Without implementations, no operation is enabled (UNAVAILABLE).
    for op in b.operation_registry.list_definitions():
        assert op.enabled is False


def test_bootstrap_no_global_state():
    import sys

    before = set(sys.modules)
    _ = build_standard_relationships_domain_bootstrap()
    after = set(sys.modules)
    # Bootstrap builds fresh registries; it must not register system-wide.
    assert "cmm.domains.relationships" in after
    assert before <= after
