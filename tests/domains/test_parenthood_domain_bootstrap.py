"""Tests for Phase 10.27 Parenthood Domain Bootstrap."""

from __future__ import annotations

from cmm.domains.identifiers import DomainId
from cmm.domains.parenthood.bootstrap import (
    PARENTHOOD_BOOTSTRAP_NAME,
    ParenthoodDomainBootstrap,
    build_standard_parenthood_domain_bootstrap,
)


def test_build_standard_parenthood_domain_bootstrap() -> None:
    """Verify building standard domain bootstrap with parenthood domain integrated."""
    bootstrap = build_standard_parenthood_domain_bootstrap()

    assert isinstance(bootstrap, ParenthoodDomainBootstrap)
    assert PARENTHOOD_BOOTSTRAP_NAME == "ParenthoodDomainBootstrap"

    # Both General and Parenthood must be registered
    assert bootstrap.domain_registry.get("domain:general") is not None
    assert bootstrap.domain_registry.get("domain:parenthood") is not None

    # Profiles registered
    assert bootstrap.profile_registry.get_by_domain(DomainId("general")) is not None
    assert bootstrap.profile_registry.get_by_domain(DomainId("parenthood")) is not None

    # Counts
    assert len(bootstrap.resource_registry.list_all()) >= 19
    assert len(bootstrap.rule_registry.list_all()) >= 17
    assert len(bootstrap.operation_registry.list_definitions()) >= 20
    assert len(bootstrap.workflow_registry.list_for_domain("domain:parenthood")) == 16


def test_package_exports() -> None:
    """Verify __init__.py exports all domain symbols cleanly without import-time side effects."""
    from cmm.domains import parenthood

    assert hasattr(parenthood, "build_parenthood_domain_definition")
    assert hasattr(parenthood, "build_parenthood_profile")
    assert hasattr(parenthood, "build_parenthood_permission_policy")
    assert hasattr(parenthood, "build_child_workspace")
    assert hasattr(parenthood, "build_parenthood_resource_definitions")
    assert hasattr(parenthood, "build_parenthood_rules")
    assert hasattr(parenthood, "build_parenthood_operation_definitions")
    assert hasattr(parenthood, "build_parenthood_workflow_definitions")
    assert hasattr(parenthood, "build_parenthood_memory_proposal")
    assert hasattr(parenthood, "present_parenthood_result")
    assert hasattr(parenthood, "assemble_parenthood_trace")
    assert hasattr(parenthood, "register_parenthood_domain")
    assert hasattr(parenthood, "build_standard_parenthood_domain_bootstrap")
