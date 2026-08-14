"""Phase 10.23 — Opposition Domain atomic integration tests (validation-first)."""

from __future__ import annotations

import pytest

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.oppositions import (
    OPPOSITIONS_DOMAIN_ID,
    build_oppositions_operation_definitions,
    register_oppositions_domain,
)
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
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
        for op in build_oppositions_operation_definitions()
    }


def test_registers_all_parts():
    r = _registries()
    result = register_oppositions_domain(
        **r, operation_implementations=_implementations()
    )
    assert str(result.definition.id) == OPPOSITIONS_DOMAIN_ID
    assert len(result.resources) == 11
    assert len(result.rules) == 6
    assert len(result.operations) == 10
    assert len(result.workflows) == 7
    assert result.permission_policy is not None
    assert r["domain_registry"].get(OPPOSITIONS_DOMAIN_ID) is not None


def test_operations_unavailable_without_implementations():
    from cmm.domains.operation_registry import DomainOperationRegistryError

    r = _registries()
    register_oppositions_domain(**r)
    for op in build_oppositions_operation_definitions():
        registered = r["operation_registry"].get(op.operation_id, op.version)
        assert registered.enabled is False
        with pytest.raises(DomainOperationRegistryError):
            r["operation_registry"].get_implementation(op.operation_id, op.version)


def test_validation_first_rejects_unknown_implementation():
    r = _registries()
    with pytest.raises(ValueError):
        register_oppositions_domain(
            domain_registry=r["domain_registry"],
            operation_registry=r["operation_registry"],
            operation_implementations={"oppositions.not_an_operation": object()},
        )
    assert r["domain_registry"].get(OPPOSITIONS_DOMAIN_ID) is None
    assert len(r["operation_registry"].list_definitions()) == 0


def test_validation_first_rejects_duplicate_domain():
    from cmm.domains.errors import DomainRegistryConflict

    r = _registries()
    register_oppositions_domain(**r)
    with pytest.raises(DomainRegistryConflict):
        register_oppositions_domain(**r)


def test_deterministic_registration_order():
    a = _registries()
    register_oppositions_domain(**a, operation_implementations=_implementations())
    ops_a = [d.operation_id for d in a["operation_registry"].list_definitions()]
    b = _registries()
    register_oppositions_domain(**b, operation_implementations=_implementations())
    ops_b = [d.operation_id for d in b["operation_registry"].list_definitions()]
    assert ops_a == ops_b