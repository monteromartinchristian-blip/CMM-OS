"""Tests for Phase 10.21 Relationships Domain atomic integration
(validation-first)."""

from __future__ import annotations

import pytest

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.operation_registry import (
    DomainOperationRegistryError,
    InMemoryDomainOperationRegistry,
)
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.relationships import (
    RELATIONSHIPS_DOMAIN_ID,
    build_relationships_operation_definitions,
    register_relationships_domain,
)
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.workflows.registry import InMemoryWorkflowRegistry


class _FakeImplementation:
    def __init__(self, definition):
        self.definition = definition

    def execute(self, request, memory_view=None):
        return {"success": True, "output": {}, "effects": ()}


def _registries():
    return {
        "domain_registry": DomainRegistry(),
        "profile_registry": InMemoryDomainProfileRegistry(),
        "resource_registry": InMemoryDomainResourceRegistry(),
        "rule_registry": InMemoryReasoningRuleRegistry(),
        "operation_registry": InMemoryDomainOperationRegistry(
            InMemoryAgentOperationRegistry()
        ),
        "workflow_registry": InMemoryDomainWorkflowRegistry(InMemoryWorkflowRegistry()),
        "permission_registry": DomainPermissionRegistry(),
    }


def _implementations():
    return {
        op.operation_id: _FakeImplementation(op)
        for op in build_relationships_operation_definitions()
    }


def _implementations_wrapped(r):
    return {
        "domain_registry": r["domain_registry"],
        "profile_registry": r["profile_registry"],
        "resource_registry": r["resource_registry"],
        "rule_registry": r["rule_registry"],
        "operation_registry": r["operation_registry"],
        "workflow_registry": r["workflow_registry"],
        "permission_registry": r["permission_registry"],
        "operation_implementations": _implementations(),
    }


def test_registers_all_parts():
    r = _registries()
    result = register_relationships_domain(**_implementations_wrapped(r))
    assert str(result.definition.id) == RELATIONSHIPS_DOMAIN_ID
    assert r["domain_registry"].get(RELATIONSHIPS_DOMAIN_ID) is not None
    assert r["profile_registry"].get("relationships.profile") is not None
    assert len(r["resource_registry"].list_all()) == 8
    assert len(r["rule_registry"].list_all()) == 8
    assert len(r["workflow_registry"].list_for_domain(RELATIONSHIPS_DOMAIN_ID)) == 6
    assert (
        r["permission_registry"].get("domain-permission:relationships:1.0.0")
        is not None
    )


def test_operations_unavailable_without_implementations():
    """Without implementations, operations are fail-closed (UNAVAILABLE)."""
    r = _registries()
    register_relationships_domain(
        domain_registry=r["domain_registry"],
        profile_registry=r["profile_registry"],
        resource_registry=r["resource_registry"],
        rule_registry=r["rule_registry"],
        operation_registry=r["operation_registry"],
        workflow_registry=r["workflow_registry"],
        permission_registry=r["permission_registry"],
    )
    for op in build_relationships_operation_definitions():
        registered = r["operation_registry"].get(op.operation_id, op.version)
        # Fail-closed: without an implementation the operation must not be
        # enabled (it would otherwise be resolvable yet unexecutable).
        assert registered.enabled is False
        with pytest.raises(DomainOperationRegistryError):
            r["operation_registry"].get_implementation(op.operation_id, op.version)


def test_validation_first_rejects_unknown_implementation():
    r = _registries()
    with pytest.raises(ValueError):
        register_relationships_domain(
            domain_registry=r["domain_registry"],
            operation_registry=r["operation_registry"],
            operation_implementations={"relationships.not_an_operation": object()},
        )
    # No mutation occurred: domain and operation registries are still empty.
    assert r["domain_registry"].get(RELATIONSHIPS_DOMAIN_ID) is None
    assert len(r["operation_registry"].list_definitions()) == 0


def test_validation_first_rejects_pre_registered_permission_policy():
    """A pre-registered permission policy is caught before any mutation."""
    r = _registries()
    from cmm.domains.errors import DomainPermissionRegistryError
    from cmm.domains.relationships.permissions import (
        build_relationships_permission_policy,
    )

    r["permission_registry"].register(build_relationships_permission_policy())
    with pytest.raises(DomainPermissionRegistryError):
        register_relationships_domain(
            domain_registry=r["domain_registry"],
            profile_registry=r["profile_registry"],
            resource_registry=r["resource_registry"],
            rule_registry=r["rule_registry"],
            operation_registry=r["operation_registry"],
            workflow_registry=r["workflow_registry"],
            permission_registry=r["permission_registry"],
        )
    # Validation-first: no mutation occurred.
    assert r["domain_registry"].get(RELATIONSHIPS_DOMAIN_ID) is None
    assert len(r["operation_registry"].list_definitions()) == 0


def test_validation_first_rejects_duplicate_domain():
    r = _registries()
    register_relationships_domain(
        domain_registry=r["domain_registry"],
        profile_registry=r["profile_registry"],
        resource_registry=r["resource_registry"],
        rule_registry=r["rule_registry"],
        operation_registry=r["operation_registry"],
        workflow_registry=r["workflow_registry"],
        permission_registry=r["permission_registry"],
    )
    from cmm.domains.errors import DomainRegistryConflict

    with pytest.raises(DomainRegistryConflict):
        register_relationships_domain(
            domain_registry=r["domain_registry"],
            profile_registry=r["profile_registry"],
            resource_registry=r["resource_registry"],
            rule_registry=r["rule_registry"],
            operation_registry=r["operation_registry"],
            workflow_registry=r["workflow_registry"],
            permission_registry=r["permission_registry"],
        )
