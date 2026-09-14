"""Phase 10.30 — Project Domain Integration Tests."""

from __future__ import annotations

import pytest

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.errors import DomainRegistryConflict
from cmm.domains.identifiers import DomainId
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.project.catalog import (
    CANONICAL_PROJECT_OPERATION_IDS,
    CANONICAL_PROJECT_RESOURCE_IDS,
    CANONICAL_PROJECT_RULE_IDS,
    CANONICAL_PROJECT_WORKFLOW_IDS,
    PROJECT_DOMAIN_ID,
)
from cmm.domains.project.integration import (
    ProjectDomainIntegrationResult,
    register_project_domain,
)
from cmm.domains.registry import DomainRegistry
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.workflows.registry import InMemoryWorkflowRegistry


def _create_registries():
    domain_reg = DomainRegistry()
    profile_reg = InMemoryDomainProfileRegistry()
    res_reg = InMemoryDomainResourceRegistry()
    rule_reg = InMemoryReasoningRuleRegistry()
    common_op_reg = InMemoryAgentOperationRegistry()
    op_reg = InMemoryDomainOperationRegistry(common_op_reg)
    common_wf_reg = InMemoryWorkflowRegistry()
    wf_reg = InMemoryDomainWorkflowRegistry(common_wf_reg)
    perm_reg = DomainPermissionRegistry()
    return (
        domain_reg,
        profile_reg,
        res_reg,
        rule_reg,
        op_reg,
        wf_reg,
        perm_reg,
    )


def test_atomic_registration_succeeds_and_populates_all_registries() -> None:
    (
        domain_reg,
        profile_reg,
        res_reg,
        rule_reg,
        op_reg,
        wf_reg,
        perm_reg,
    ) = _create_registries()

    result = register_project_domain(
        domain_registry=domain_reg,
        profile_registry=profile_reg,
        resource_registry=res_reg,
        rule_registry=rule_reg,
        operation_registry=op_reg,
        workflow_registry=wf_reg,
        permission_registry=perm_reg,
    )
    assert isinstance(result, ProjectDomainIntegrationResult)

    # Domain definition
    assert domain_reg.get(PROJECT_DOMAIN_ID) is not None

    # Profile
    assert profile_reg.get_by_domain(DomainId.from_str(PROJECT_DOMAIN_ID)) is not None

    # Resources (22)
    assert len(res_reg.list_all()) == 22
    assert {r.id for r in res_reg.list_all()} == set(CANONICAL_PROJECT_RESOURCE_IDS)

    # Rules (18)
    assert len(rule_reg.list_all()) == 18
    assert {r.definition.id for r in rule_reg.list_all()} == set(
        CANONICAL_PROJECT_RULE_IDS
    )

    # Operations (20)
    assert len(op_reg.list_definitions()) == 20
    assert {op.operation_id for op in op_reg.list_definitions()} == set(
        CANONICAL_PROJECT_OPERATION_IDS
    )

    # Workflows (12)
    assert len(wf_reg.list_for_domain(PROJECT_DOMAIN_ID)) == 12
    assert {w.workflow_id for w in wf_reg.list_for_domain(PROJECT_DOMAIN_ID)} == set(
        CANONICAL_PROJECT_WORKFLOW_IDS
    )

    # Permission policy
    assert perm_reg.get("domain-permission:project:1.0.0") is not None


def test_atomic_registration_duplicate_domain_rolls_back() -> None:
    (
        domain_reg,
        profile_reg,
        res_reg,
        rule_reg,
        op_reg,
        wf_reg,
        perm_reg,
    ) = _create_registries()

    # First registration
    register_project_domain(
        domain_registry=domain_reg,
        profile_registry=profile_reg,
        resource_registry=res_reg,
        rule_registry=rule_reg,
        operation_registry=op_reg,
        workflow_registry=wf_reg,
        permission_registry=perm_reg,
    )

    # Duplicate registration fails validation-first without partial state
    with pytest.raises(DomainRegistryConflict, match="already registered"):
        register_project_domain(
            domain_registry=domain_reg,
            profile_registry=profile_reg,
            resource_registry=res_reg,
            rule_registry=rule_reg,
            operation_registry=op_reg,
            workflow_registry=wf_reg,
            permission_registry=perm_reg,
        )

    # State still intact from first registration
    assert len(res_reg.list_all()) == 22
    assert len(rule_reg.list_all()) == 18
    assert len(op_reg.list_definitions()) == 20
    assert len(wf_reg.list_for_domain(PROJECT_DOMAIN_ID)) == 12
