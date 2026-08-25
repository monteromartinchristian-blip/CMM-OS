"""Tests for Phase 10.29 Life Plan Domain Integration."""

from __future__ import annotations

from typing import Any

import pytest

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.errors import DomainRegistryConflict
from cmm.domains.identifiers import DomainId
from cmm.domains.life_plan.catalog import (
    LIFE_PLAN_DOMAIN_ID,
    LIFE_PLAN_OPERATION_IDS,
    LIFE_PLAN_RESOURCE_IDS,
    LIFE_PLAN_RULE_IDS,
    LIFE_PLAN_WORKFLOW_IDS,
)
from cmm.domains.life_plan.integration import (
    LifePlanDomainIntegrationResult,
    register_life_plan_domain,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.workflows.registry import InMemoryWorkflowRegistry


def _create_registries() -> dict:
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


def test_life_plan_atomic_registration_success() -> None:
    regs = _create_registries()
    result = register_life_plan_domain(**regs)

    assert isinstance(result, LifePlanDomainIntegrationResult)
    assert str(result.definition.id) == LIFE_PLAN_DOMAIN_ID
    assert len(result.resources) == len(LIFE_PLAN_RESOURCE_IDS)
    assert len(result.rules) == len(LIFE_PLAN_RULE_IDS)
    assert len(result.operations) == len(LIFE_PLAN_OPERATION_IDS)
    assert len(result.workflows) == len(LIFE_PLAN_WORKFLOW_IDS)

    # Verify registered in store
    assert regs["domain_registry"].get(LIFE_PLAN_DOMAIN_ID) is not None
    assert regs["profile_registry"].get_by_domain(DomainId("life-plan")) is not None
    assert len(regs["resource_registry"].list_all()) == 12
    assert len(regs["rule_registry"].list_all()) == 8
    assert len(regs["operation_registry"].list_definitions()) == 10
    assert len(regs["workflow_registry"].list_for_domain(LIFE_PLAN_DOMAIN_ID)) == 7


def test_life_plan_preflight_conflict_prevention() -> None:
    regs = _create_registries()
    register_life_plan_domain(**regs)

    with pytest.raises(DomainRegistryConflict):
        register_life_plan_domain(**regs)


def test_life_plan_rollback_parity_on_fault() -> None:
    regs = _create_registries()

    class FaultyPermissionRegistry(DomainPermissionRegistry):
        def register(self, policy: Any) -> Any:
            raise RuntimeError("Fault injected during permission registration")

    regs["permission_registry"] = FaultyPermissionRegistry()

    assert regs["domain_registry"].get(LIFE_PLAN_DOMAIN_ID) is None

    with pytest.raises(RuntimeError, match="Fault injected"):
        register_life_plan_domain(**regs)

    assert regs["domain_registry"].get(LIFE_PLAN_DOMAIN_ID) is None
