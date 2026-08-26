"""Phase 10.30 — Project Domain Public API Tests."""

from __future__ import annotations

import cmm.domains.project as project_pkg


def test_public_api_symbols_exported() -> None:
    expected_symbols = (
        "PROJECT_DOMAIN_ID",
        "PROJECT_DOMAIN_VERSION",
        "PROJECT_PROFILE_NAME",
        "PROJECT_RESOURCE_IDS",
        "PROJECT_RULE_IDS",
        "PROJECT_OPERATION_IDS",
        "PROJECT_WORKFLOW_IDS",
        "CANONICAL_PROJECT_RESOURCE_KINDS",
        "CANONICAL_PROJECT_RESOURCE_IDS",
        "CANONICAL_PROJECT_RULE_IDS",
        "CANONICAL_PROJECT_OPERATION_IDS",
        "CANONICAL_PROJECT_WORKFLOW_IDS",
        "build_project_domain_definition",
        "build_project_profile",
        "project_software_capability_active",
        "build_project_resource_definitions",
        "build_project_rules",
        "build_project_operation_definitions",
        "build_project_workflow_definitions",
        "build_project_permission_policy",
        "build_project_life_plan_projection",
        "build_project_memory_binding",
        "build_project_memory_proposal",
        "build_project_memory_view",
        "build_project_memory_view_request",
        "validate_project_memory_binding",
        "validate_project_memory_proposal_content",
        "assemble_project_trace",
        "build_project_trace_contribution",
        "build_project_trace_reference",
        "build_supporting_trace_contribution",
        "validate_project_trace",
        "build_project_presentation_policy",
        "present_project_result",
        "ProjectDomainIntegrationResult",
        "register_project_domain",
        "ProjectDomainBootstrap",
        "build_standard_project_domain_bootstrap",
    )

    for symbol in expected_symbols:
        assert hasattr(project_pkg, symbol), f"Missing symbol {symbol} in cmm.domains.project"
        assert symbol in project_pkg.__all__, f"Symbol {symbol} not in __all__"
