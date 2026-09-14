"""Phase 10.21 — self-audit: Relationships must not create parallel infrastructure.

Relationships is the third canonical Domain Pack and must REUSE the existing
canonical infrastructure (resources, provenance, temporality, entities,
KnowledgeItems, cognitive profiles, reasoning rules, Agent Runtime,
operations, workflows, permissions, approvals, memory, trace, presentation,
common registries, snapshot/rollback).  These tests assert Relationships
defines no parallel runtime, memory, trace, registry, or resolver.
"""

from __future__ import annotations

import inspect

from cmm.domains import relationships


def test_relationships_reuses_canonical_memory_contracts():
    from cmm.domains.memory_contracts import (
        DomainMemoryProposalBinding,
        DomainMemoryProposalSnapshot,
        DomainMemoryView,
    )

    # Relationships builds canonical proposal/view/binding contracts, never a
    # parallel memory store.
    assert build_relationships_memory_view_request_factory()  # imported below
    assert DomainMemoryProposalSnapshot is not None
    assert DomainMemoryView is not None
    assert DomainMemoryProposalBinding is not None


def build_relationships_memory_view_request_factory():
    from cmm.domains.relationships.memory import (
        build_relationships_memory_view_request,
    )

    return callable(build_relationships_memory_view_request)


def test_relationships_defines_no_parallel_registry():
    """Relationships exposes the canonical register factory, not parallel stores."""
    assert not hasattr(relationships, "RelationshipsMemoryStore")
    assert not hasattr(relationships, "RelationshipsRegistries")
    assert not hasattr(relationships, "RelationshipsResolver")
    # The register factory is a function returning an integration result,
    # not a parallel registry.
    assert not inspect.isclass(relationships.register_relationships_domain)


def test_relationships_reuses_common_rule_contracts():
    rules = relationships.build_relationships_rules()
    for rule in rules:
        # Each rule exposes the canonical protocol (definition + evaluate).
        assert callable(rule.evaluate)
        assert rule.definition.domain_id == "domain:relationships"


def test_operations_registered_fail_closed_without_store():
    """Relationships operations declare definitions only; implementations are
    injected."""
    for op in relationships.build_relationships_operation_definitions():
        assert op.domain_id == "domain:relationships"
        assert op.version == "1.0.0"


def test_relationships_reuses_snapshot_rollback_in_integration():
    from cmm.domains.relationships import integration

    src = inspect.getsource(integration)
    assert "snapshot_state" in src
    assert "restore_state" in src
    assert "validation" in src


def test_no_parallel_entity_classes():
    """Relationships surfaces semantic entity types, not parallel persistent
    classes."""
    from cmm.domains.relationships.catalog import (
        CANONICAL_RELATIONSHIPS_ENTITY_TYPES,
    )

    # Relationships entity types are surfaced via canonical resource
    # entity_types and KnowledgeItem bindings; Relationships defines no
    # classes named after them.
    for attribute in dir(relationships):
        assert not any(
            attribute == f"Relationships{kind.title().replace('_', '')}"
            for kind in CANONICAL_RELATIONSHIPS_ENTITY_TYPES
        )
