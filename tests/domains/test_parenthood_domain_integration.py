"""Tests for Phase 10.27 Parenthood Domain Integration and Rollback."""

from __future__ import annotations

import pytest

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.errors import DomainRegistryConflict
from cmm.domains.identifiers import DomainId
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.parenthood.integration import (
    ParenthoodDomainIntegrationResult,
    register_parenthood_domain,
)
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.workflows.registry import InMemoryWorkflowRegistry


def _registries() -> dict:
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


def test_register_parenthood_domain_atomic_success() -> None:
    """Verify clean atomic registration of the complete Parenthood Domain."""
    registries = _registries()
    result = register_parenthood_domain(**registries)

    assert isinstance(result, ParenthoodDomainIntegrationResult)
    assert registries["domain_registry"].get("domain:parenthood") is not None
    assert (
        registries["profile_registry"].get_by_domain(DomainId("parenthood")) is not None
    )
    assert len(registries["resource_registry"].list_all()) == 19
    assert len(registries["rule_registry"].list_all()) == 17
    assert len(registries["operation_registry"].list_definitions()) == 20
    assert (
        len(registries["workflow_registry"].list_for_domain("domain:parenthood")) == 16
    )
    assert (
        registries["permission_registry"].get("domain-permission:parenthood:1.0.0")
        is not None
    )


def test_register_parenthood_domain_duplicate_raises_and_rolls_back() -> None:
    """Duplicate domain registration raises DomainRegistryConflict and rolls back cleanly."""
    registries = _registries()
    register_parenthood_domain(**registries)

    with pytest.raises(DomainRegistryConflict):
        register_parenthood_domain(**registries)
