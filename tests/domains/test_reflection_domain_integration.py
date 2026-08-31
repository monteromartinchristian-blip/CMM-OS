"""Phase 10.24 — Reflection Domain integration tests.

Validation-first atomic registration across all shared registries:
the full pack registers atomically, duplicates fail before any mutation, and
the bootstrap composes General + Reflection through the shared mechanisms
(spec §39, §40).
"""

from __future__ import annotations

import pytest

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.reflection import (
    REFLECTION_DOMAIN_ID,
    REFLECTION_PERMISSION_IDS,
    build_reflection_domain_definition,
    register_reflection_domain,
)
from cmm.domains.reflection.bootstrap import (
    REFLECTION_BOOTSTRAP_NAME,
    ReflectionDomainBootstrap,
    build_standard_reflection_domain_bootstrap,
)
from cmm.domains.reflection.catalog import (
    CANONICAL_REFLECTION_OPERATION_IDS,
    CANONICAL_REFLECTION_RESOURCE_IDS,
    CANONICAL_REFLECTION_RULE_IDS,
    CANONICAL_REFLECTION_WORKFLOW_IDS,
)
from cmm.domains.reflection.definition import REFLECTION_PROFILE_NAME
from cmm.domains.registry import DomainRegistry
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.workflows.registry import InMemoryWorkflowRegistry


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


def test_registers_complete_pack():
    registries = _registries()
    result = register_reflection_domain(**registries)
    assert str(result.definition.id) == REFLECTION_DOMAIN_ID
    assert registries["domain_registry"].get(REFLECTION_DOMAIN_ID) is not None
    assert len(registries["resource_registry"].list_all()) == 9
    assert len(registries["rule_registry"].list_all()) == 6
    assert len(registries["operation_registry"].list_definitions()) == 9
    assert (
        len(registries["workflow_registry"].list_for_domain(REFLECTION_DOMAIN_ID)) == 6
    )
    assert registries["profile_registry"].get("reflection.profile") is not None
    assert (
        registries["permission_registry"].get(REFLECTION_PERMISSION_IDS[0]).policy_id
        == "domain-permission:reflection:1.0.0"
    )


def test_duplicate_registration_fails_validation_first():
    registries = _registries()
    register_reflection_domain(**registries)
    from cmm.domains.errors import DomainRegistryConflict

    before_domain = registries["domain_registry"].snapshot_state()
    with pytest.raises(DomainRegistryConflict):
        register_reflection_domain(**registries)
    # validation-first: no partial mutation on the second attempt
    assert registries["domain_registry"].snapshot_state() == before_domain


def test_definition_reconciles_full_catalog():
    definition = build_reflection_domain_definition()
    assert set(definition.resources) == set(CANONICAL_REFLECTION_RESOURCE_IDS)
    assert set(definition.rules) == set(CANONICAL_REFLECTION_RULE_IDS)
    assert set(definition.operations) == set(CANONICAL_REFLECTION_OPERATION_IDS)
    assert set(definition.workflows) == set(CANONICAL_REFLECTION_WORKFLOW_IDS)
    assert definition.reasoning_profile == REFLECTION_PROFILE_NAME


def test_bootstrap_builds_general_plus_reflection():
    bootstrap = build_standard_reflection_domain_bootstrap()
    assert isinstance(bootstrap, ReflectionDomainBootstrap)
    assert bootstrap.domain_registry.get("domain:general") is not None
    assert bootstrap.domain_registry.get(REFLECTION_DOMAIN_ID) is not None
    # General is the fallback resolver
    assert str(bootstrap.resolver.fallback_domain) == "domain:general"
    assert bootstrap.profile_registry.get("general.profile") is not None
    assert bootstrap.profile_registry.get("reflection.profile") is not None


def test_bootstrap_name():
    assert REFLECTION_BOOTSTRAP_NAME == "ReflectionDomainBootstrap"


def test_import_has_no_side_effects():
    import cmm.domains.reflection  # noqa: F401

    registry = DomainRegistry()
    assert registry.get(REFLECTION_DOMAIN_ID) is None
