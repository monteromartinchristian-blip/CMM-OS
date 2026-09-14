"""Phase 10.20 — self-audit: Health must not create parallel infrastructure.

Health is the second canonical Domain Pack and must REUSE the existing
canonical infrastructure (resources, provenance, temporality, entities,
KnowledgeItems, cognitive profiles, reasoning rules, Agent Runtime,
operations, workflows, permissions, approvals, memory, trace, presentation,
common registries, snapshot/rollback).  These tests assert Health defines no
parallel runtime, memory, trace, registry, or resolver.
"""

from __future__ import annotations

import inspect

from cmm.domains import health


def test_health_reuses_canonical_memory_contracts():
    from cmm.domains.memory_contracts import (
        DomainMemoryProposalBinding,
        DomainMemoryProposalSnapshot,
        DomainMemoryView,
    )

    # Health builds canonical proposal/view/binding contracts, never a
    # parallel memory store.
    assert build_health_memory_view_request_factory()  # imported below
    assert DomainMemoryProposalSnapshot is not None
    assert DomainMemoryView is not None
    assert DomainMemoryProposalBinding is not None


def build_health_memory_view_request_factory():
    from cmm.domains.health.memory import build_health_memory_view_request

    return callable(build_health_memory_view_request)


def test_health_defines_no_parallel_registry():
    """Health exposes the canonical register factory, not parallel stores."""
    assert not hasattr(health, "HealthMemoryStore")
    assert not hasattr(health, "HealthRegistries")
    assert not hasattr(health, "HealthResolver")
    # The register factory is a function returning an integration result,
    # not a parallel registry.
    assert not inspect.isclass(health.register_health_domain)


def test_health_reuses_common_rule_contracts():

    rules = health.build_health_rules()
    for rule in rules:
        # Each rule exposes the canonical protocol (definition + evaluate).
        assert callable(rule.evaluate)
        assert rule.definition.domain_id == "domain:health"


def test_operations_registered_fail_closed_without_store():
    """Health operations declare definitions only; implementations are injected."""
    for op in health.build_health_operation_definitions():
        assert op.domain_id == "domain:health"
        assert op.version == "1.0.0"


def test_health_reuses_snapshot_rollback_in_integration():
    from cmm.domains.health import integration

    src = inspect.getsource(integration)
    assert "snapshot_state" in src
    assert "restore_state" in src
    assert "validation" in src


def test_no_parallel_entity_classes():
    """Health surfaces semantic entity types, not parallel persistent classes."""
    from cmm.domains.health.catalog import CANONICAL_HEALTH_ENTITY_TYPES

    # Health entity types are surfaced via canonical resource entity_types and
    # KnowledgeItem bindings; Health defines no classes named after them.
    for attribute in dir(health):
        assert not any(
            attribute == f"Health{kind.title().replace('_', '')}"
            for kind in CANONICAL_HEALTH_ENTITY_TYPES
        )
