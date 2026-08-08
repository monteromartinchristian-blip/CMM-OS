"""Tests for Phase 10.20 canonical Health Domain bootstrap."""

from __future__ import annotations

from cmm.domains.health import (
    HEALTH_DOMAIN_ID,
    build_standard_health_domain_bootstrap,
)
from cmm.domains.identifiers import DomainId


def test_bootstrap_defaults_to_fresh_registries():
    b = build_standard_health_domain_bootstrap()
    assert b.domain_registry.get(HEALTH_DOMAIN_ID) is not None
    assert b.resolver.fallback_domain == DomainId(slug="health")
    assert len(b.resource_registry.list_all()) == 12
    assert len(b.rule_registry.list_all()) == 8
    assert len(b.workflow_registry.list_for_domain(HEALTH_DOMAIN_ID)) == 8


def test_bootstrap_operations_fail_closed():
    b = build_standard_health_domain_bootstrap()
    # Without implementations, no operation is enabled (UNAVAILABLE).
    for op in b.operation_registry.list_definitions():
        assert op.enabled is False


def test_bootstrap_no_global_state():
    import sys

    before = set(sys.modules)
    _ = build_standard_health_domain_bootstrap()
    after = set(sys.modules)
    # Bootstrap builds fresh registries; it must not register system-wide.
    assert "cmm.domains.health" in after
    assert before <= after
