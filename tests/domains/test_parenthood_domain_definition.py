"""Tests for Phase 10.27 Parenthood Domain Definition."""

from __future__ import annotations

from cmm.domains.enums import DomainKind
from cmm.domains.parenthood.catalog import (
    CANONICAL_PARENTHOOD_OPERATION_IDS,
    CANONICAL_PARENTHOOD_RESOURCE_IDS,
    CANONICAL_PARENTHOOD_RULE_IDS,
    CANONICAL_PARENTHOOD_WORKFLOW_IDS,
)
from cmm.domains.parenthood.definition import (
    PARENTHOOD_DOMAIN_ID,
    PARENTHOOD_DOMAIN_VERSION,
    PARENTHOOD_MANIFEST_ID,
    PARENTHOOD_OPERATION_IDS,
    PARENTHOOD_PERMISSION_IDS,
    PARENTHOOD_PROFILE_NAME,
    PARENTHOOD_RESOURCE_IDS,
    PARENTHOOD_RULE_IDS,
    PARENTHOOD_WORKFLOW_IDS,
    build_parenthood_domain_definition,
)


def test_parenthood_domain_identity_contract() -> None:
    """Verify domain identity matches Phase 10.27 specifications."""
    definition = build_parenthood_domain_definition()
    assert str(definition.id) == "domain:parenthood"
    assert definition.name == "parenthood"
    assert definition.display_name == "Paternidad"
    assert definition.version == "1.0.0"
    assert definition.kind is DomainKind.PERSONAL
    assert definition.reasoning_profile == "ParenthoodProfile"
    assert definition.manifest_id == "manifest:parenthood:1.0.0"
    assert definition.metadata.metadata["phase"] == "10.27"
    assert build_parenthood_domain_definition().to_dict() == definition.to_dict()


def test_parenthood_domain_definition_catalogs() -> None:
    """Verify definition uses canonical catalog constants."""
    definition = build_parenthood_domain_definition()
    assert definition.resources == CANONICAL_PARENTHOOD_RESOURCE_IDS
    assert definition.rules == CANONICAL_PARENTHOOD_RULE_IDS
    assert definition.operations == CANONICAL_PARENTHOOD_OPERATION_IDS
    assert definition.workflows == CANONICAL_PARENTHOOD_WORKFLOW_IDS
    assert definition.permissions == PARENTHOOD_PERMISSION_IDS

    assert PARENTHOOD_RESOURCE_IDS == CANONICAL_PARENTHOOD_RESOURCE_IDS
    assert PARENTHOOD_RULE_IDS == CANONICAL_PARENTHOOD_RULE_IDS
    assert PARENTHOOD_OPERATION_IDS == CANONICAL_PARENTHOOD_OPERATION_IDS
    assert PARENTHOOD_WORKFLOW_IDS == CANONICAL_PARENTHOOD_WORKFLOW_IDS


def test_parenthood_domain_capabilities() -> None:
    """Verify the 10 canonical capabilities are properly declared."""
    definition = build_parenthood_domain_definition()
    capabilities = {c.name: c for c in definition.capabilities}
    assert len(capabilities) == 10

    expected_capabilities = (
        "parenthood_journey_planning",
        "parenthood_pathway_comparison",
        "parenthood_requirements_review",
        "parenthood_financial_scenario_review",
        "parenthood_child_workspace",
        "parenthood_developmental_review",
        "parenthood_parental_decision_support",
        "parenthood_family_context_review",
        "parenthood_journey_to_child_transition",
        "parenthood_multi_child_isolation",
    )
    for cap_name in expected_capabilities:
        assert cap_name in capabilities
        cap = capabilities[cap_name]
        assert cap.provided_by == PARENTHOOD_DOMAIN_ID
        assert cap.version == PARENTHOOD_DOMAIN_VERSION
        assert cap.metadata.get("phase") == "10.27"


def test_parenthood_presentation_policy() -> None:
    """Verify presentation policy requires uncertainty, provenance, and disclaimers."""
    definition = build_parenthood_domain_definition()
    policy = definition.presentation_policy
    assert policy.get("detail_level") == "detailed"
    assert policy.get("include_uncertainty") is True
    assert policy.get("include_provenance") is True
    assert policy.get("include_alternatives") is True
    assert policy.get("allow_speculation") is False
    assert policy.get("require_disclaimers") is True
