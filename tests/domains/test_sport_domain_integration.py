"""Tests for Phase 10.28 Sport Domain Integration."""

from __future__ import annotations

from typing import Any

import pytest

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.errors import DomainRegistryConflict
from cmm.domains.identifiers import DomainId
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.sport.catalog import (
    SPORT_OPERATION_IDS,
    SPORT_RESOURCE_IDS,
    SPORT_RULE_IDS,
    SPORT_WORKFLOW_IDS,
)
from cmm.domains.sport.definition import SPORT_DOMAIN_ID
from cmm.domains.sport.integration import (
    SportDomainIntegrationResult,
    register_sport_domain,
)
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


def test_sport_atomic_registration_success() -> None:
    regs = _create_registries()
    result = register_sport_domain(**regs)

    assert isinstance(result, SportDomainIntegrationResult)
    assert str(result.definition.id) == SPORT_DOMAIN_ID
    assert len(result.resources) == len(SPORT_RESOURCE_IDS)
    assert len(result.rules) == len(SPORT_RULE_IDS)
    assert len(result.operations) == len(SPORT_OPERATION_IDS)
    assert len(result.workflows) == len(SPORT_WORKFLOW_IDS)

    # Verify registered in store
    assert regs["domain_registry"].get(SPORT_DOMAIN_ID) is not None
    assert regs["profile_registry"].get_by_domain(DomainId("sport")) is not None
    assert len(regs["resource_registry"].list_all()) == 9
    assert len(regs["rule_registry"].list_all()) == 6
    assert len(regs["operation_registry"].list_definitions()) == 8
    assert len(regs["workflow_registry"].list_for_domain("domain:sport")) == 5


def test_sport_preflight_conflict_prevention() -> None:
    regs = _create_registries()
    register_sport_domain(**regs)

    with pytest.raises(DomainRegistryConflict):
        register_sport_domain(**regs)


def test_sport_rollback_parity_on_fault() -> None:
    regs = _create_registries()

    class FaultyPermissionRegistry(DomainPermissionRegistry):
        def register(self, policy: Any) -> Any:
            raise RuntimeError("Fault injected during permission registration")

    regs["permission_registry"] = FaultyPermissionRegistry()

    assert regs["domain_registry"].get(SPORT_DOMAIN_ID) is None

    with pytest.raises(RuntimeError, match="Fault injected"):
        register_sport_domain(**regs)

    assert regs["domain_registry"].get(SPORT_DOMAIN_ID) is None
