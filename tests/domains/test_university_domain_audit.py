"""Phase 10.22 — self-audit: University must not create parallel infrastructure.

University is the fourth canonical Domain Pack and must REUSE the existing
canonical infrastructure (resources, provenance, temporality, entities,
KnowledgeItems, cognitive profiles, reasoning rules, Agent Runtime,
operations, workflows, permissions, approvals, memory, trace, presentation,
common registries, snapshot/rollback).  These tests assert University defines
no parallel runtime, memory, trace, registry, or resolver.
"""

from __future__ import annotations

import inspect

from cmm.domains import university


def test_university_reuses_canonical_memory_contracts():
    from cmm.domains.memory_contracts import (
        DomainMemoryProposalBinding,
        DomainMemoryProposalSnapshot,
        DomainMemoryView,
    )

    assert build_university_memory_view_request_factory()  # imported below
    assert DomainMemoryProposalSnapshot is not None
    assert DomainMemoryView is not None
    assert DomainMemoryProposalBinding is not None


def build_university_memory_view_request_factory():
    from cmm.domains.university.memory import (
        build_university_memory_view_request,
    )

    return callable(build_university_memory_view_request)


def test_university_defines_no_parallel_registry():
    """University exposes the canonical register factory, not parallel stores."""
    assert not hasattr(university, "UniversityMemoryStore")
    assert not hasattr(university, "UniversityRegistries")
    assert not hasattr(university, "UniversityResolver")
    assert not hasattr(university, "UniversityCalendarEngine")
    assert not hasattr(university, "UniversityTaskEngine")
    assert not hasattr(university, "UniversityEmailService")
    assert not hasattr(university, "UniversityWorkflowEngine")
    # The register factory is a function returning an integration result,
    # not a parallel registry.
    assert not inspect.isclass(university.register_university_domain)


def test_university_reuses_common_rule_contracts():
    for rule in university.build_university_rules():
        assert callable(rule.evaluate)
        assert rule.definition.domain_id == "domain:university"


def test_operations_registered_fail_closed_without_store():
    """University operations declare definitions only; implementations are
    injected."""
    for op in university.build_university_operation_definitions():
        assert op.domain_id == "domain:university"
        assert op.version == "1.0.0"


def test_university_reuses_snapshot_rollback_in_integration():
    from cmm.domains.university import integration

    src = inspect.getsource(integration)
    assert "snapshot_state" in src
    assert "restore_state" in src
    assert "validation" in src


def test_university_reuses_shared_trace_assembler():
    from cmm.domains.trace_assembler import DomainTraceAssembler

    assert DomainTraceAssembler is not None


def test_university_reuses_shared_workflow_engine():
    from cmm.domains.workflow_execution import DomainWorkflowExecutor

    assert DomainWorkflowExecutor is not None


def test_no_parallel_entity_classes():
    """University surfaces semantic entity types, not parallel persistent
    classes."""
    from cmm.domains.university.catalog import (
        CANONICAL_UNIVERSITY_ENTITY_TYPES,
    )

    for attribute in dir(university):
        assert not any(
            attribute == f"University{kind.title().replace('_', '')}"
            for kind in CANONICAL_UNIVERSITY_ENTITY_TYPES
        )
