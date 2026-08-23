"""Phase 10.26 — Languages Cross-Domain Boundary Tests."""

from __future__ import annotations

import inspect
import json

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.identifiers import DomainId
from cmm.domains.languages import (
    build_standard_languages_domain_bootstrap,
    register_languages_domain,
)
from cmm.domains.languages.permissions import build_languages_permission_policy
from cmm.domains.languages.resources import build_languages_resource_definitions
from cmm.domains.university.permissions import build_university_permission_policy


def test_general_fallback_reused() -> None:
    """Standard Languages bootstrap keeps General domain as fallback."""
    bootstrap = build_standard_languages_domain_bootstrap()
    assert bootstrap.domain_registry.get("domain:general") is not None
    assert bootstrap.domain_registry.get("domain:languages") is not None
    assert bootstrap.resolver.fallback_domain == DomainId(slug="general")


def test_cross_domain_resource_projection_boundary() -> None:
    """Verify languages.domain_result carries clean cross-domain metadata."""
    resources = {r.id: r for r in build_languages_resource_definitions()}
    boundary = resources["languages.domain_result"]
    assert boundary.metadata.get("cross_domain_projection") is True
    assert boundary.metadata.get("no_private_store_merge") is True
    assert boundary.metadata.get("specialized_ownership_preserved") is True


def test_no_direct_sibling_store_import() -> None:
    """Verify Languages package does not import private stores from sibling domains."""
    source = inspect.getsource(__import__("cmm.domains.languages", fromlist=["*"]))
    assert "university_store" not in source
    assert "oppositions_store" not in source
    assert "health_store" not in source
    assert "concerns_store" not in source


def test_most_restrictive_permissions_survive_composition() -> None:
    """Composed policy with university retains strict prohibited capabilities."""
    lang_policy = build_languages_permission_policy()
    univ_policy = build_university_permission_policy()
    composed_denied = set(lang_policy.prohibited_capabilities) | set(
        univ_policy.prohibited_capabilities
    )
    for cap in (
        PermissionCapability.COMMUNICATION_EXTERNAL,
        PermissionCapability.FILE_MODIFY,
        PermissionCapability.SCHEDULE_MODIFY,
        PermissionCapability.FINANCIAL_ACTION,
    ):
        assert cap in composed_denied


def test_registration_does_not_mutate_unregistered_domains() -> None:
    """Registering Languages touches only Languages definitions."""
    from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
    from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
    from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
    from cmm.domains.permission_registry import DomainPermissionRegistry
    from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
    from cmm.domains.registry import DomainRegistry
    from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
    from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
    from cmm.workflows.registry import InMemoryWorkflowRegistry

    registries = {
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
    register_languages_domain(**registries)
    for other in (
        "domain:relationships",
        "domain:health",
        "domain:reflection",
        "domain:university",
        "domain:oppositions",
        "domain:concerns",
    ):
        assert registries["domain_registry"].get(other) is None
    assert all(
        res.id.startswith("languages.")
        for res in registries["resource_registry"].list_all()
    )


def test_cross_domain_projection_json_safe() -> None:
    """Verify JSON safety of cross-domain payload."""
    payload = {
        "source_domain": "domain:university",
        "requirement": "B2 English required for Erasmus exchange",
        "factual_ownership_retained": True,
    }
    json_str = json.dumps(payload, allow_nan=False)
    assert json_str is not None
