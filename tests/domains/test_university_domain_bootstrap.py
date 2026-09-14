"""Tests for Phase 10.22 canonical University Domain bootstrap."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.enums import DomainResolutionStatus
from cmm.domains.general import GENERAL_DOMAIN_ID
from cmm.domains.identifiers import DomainId
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionSignal,
)
from cmm.domains.university import (
    UNIVERSITY_DOMAIN_ID,
    build_standard_university_domain_bootstrap,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)
GENERAL = DomainId(slug="general")
UNIVERSITY = DomainId(slug="university")


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


def _university_signal(value="university-signal", confidence=0.9):
    return DomainResolutionSignal(
        kind="intent",
        source="test",
        value=value,
        domain_ids=(UNIVERSITY,),
        confidence=confidence,
        provenance={"source": "test"},
    )


def test_bootstrap_defaults_to_fresh_registries():
    b = build_standard_university_domain_bootstrap()
    assert b.domain_registry.get(UNIVERSITY_DOMAIN_ID) is not None
    assert b.domain_registry.get(GENERAL_DOMAIN_ID) is not None
    assert b.resolver.fallback_domain == DomainId(slug="general")
    university_resources = {
        r.id
        for r in b.resource_registry.list_all()
        if r.domain_id == "domain:university"
    }
    assert len(university_resources) == 12
    university_rules = {
        r.definition.id
        for r in b.rule_registry.list_all()
        if r.definition.domain_id == "domain:university"
    }
    assert len(university_rules) == 10
    assert len(b.workflow_registry.list_for_domain(UNIVERSITY_DOMAIN_ID)) == 7


def test_bootstrap_composes_general_and_university():
    """The standard University bootstrap exposes BOTH General and University
    on the same registries."""
    b = build_standard_university_domain_bootstrap()
    slugs = {d.id.slug for d in b.domain_registry.list()}
    assert slugs == {"general", "university"}


def test_bootstrap_fallback_is_general():
    b = build_standard_university_domain_bootstrap()
    assert b.resolver.fallback_domain == GENERAL


def test_generic_request_does_not_resolve_to_university_by_fallback():
    """A generic (non-specialized) request must resolve to General, never to
    University merely because University is present."""
    b = build_standard_university_domain_bootstrap()
    result = b.resolver.resolve(_ctx(b, objective="a generic non-academic request"))
    assert result.primary_domain == GENERAL


def test_explicit_university_signal_resolves_university():
    """A valid explicit University signal resolves to University."""
    b = build_standard_university_domain_bootstrap()
    result = b.resolver.resolve(
        _ctx(
            b,
            objective="academic planning question",
            explicit=(UNIVERSITY,),
            signals=(_university_signal(),),
        )
    )
    assert result.primary_domain == UNIVERSITY


def test_blocked_university_does_not_silently_resolve_general():
    """University unauthorized/denied/unavailable must not silently resolve
    to General (generic fallback-blocking invariant)."""
    b = build_standard_university_domain_bootstrap()
    result = b.resolver.resolve(
        _ctx(
            b,
            available=_registered(b),
            authorized=(GENERAL,),
            objective="academic planning question",
            signals=(_university_signal(),),
        )
    )
    assert result.status is DomainResolutionStatus.BLOCKED
    assert result.primary_domain is None
    assert result.fallback_used is False
    assert any(r.code == "DOMAIN_UNAUTHORIZED_REJECTED" for r in result.reasons)


def test_bootstrap_operations_fail_closed():
    b = build_standard_university_domain_bootstrap()
    # Without implementations, no operation is enabled (UNAVAILABLE).
    for op in b.operation_registry.list_definitions():
        assert op.enabled is False


def test_bootstrap_no_global_state():
    import sys

    before = set(sys.modules)
    _ = build_standard_university_domain_bootstrap()
    after = set(sys.modules)
    # Bootstrap builds fresh registries; it must not register system-wide.
    assert "cmm.domains.university" in after
    assert before <= after
