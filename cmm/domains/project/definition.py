"""Phase 10.30 — Project Domain Definition.

Builds the immutable ``domain:project`` definition deterministically using
the shared ``DomainDefinition`` contract. No global registration at import time.
"""

from __future__ import annotations

from cmm.domains.contracts import DomainCapability, DomainDefinition, DomainMetadata
from cmm.domains.enums import DomainKind
from cmm.domains.project.catalog import (
    CANONICAL_PROJECT_OPERATION_IDS,
    CANONICAL_PROJECT_RESOURCE_IDS,
    CANONICAL_PROJECT_RULE_IDS,
    CANONICAL_PROJECT_WORKFLOW_IDS,
    PROJECT_DOMAIN_ID,
    PROJECT_DOMAIN_VERSION,
    PROJECT_MANIFEST_ID,
    PROJECT_PROFILE_NAME,
)

PROJECT_RESOURCE_IDS: tuple[str, ...] = CANONICAL_PROJECT_RESOURCE_IDS
PROJECT_RULE_IDS: tuple[str, ...] = CANONICAL_PROJECT_RULE_IDS
PROJECT_OPERATION_IDS: tuple[str, ...] = CANONICAL_PROJECT_OPERATION_IDS
PROJECT_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_PROJECT_WORKFLOW_IDS

PROJECT_PERMISSION_IDS: tuple[str, ...] = ("domain-permission:project:1.0.0",)


def build_project_domain_definition() -> DomainDefinition:
    """Build the immutable ``domain:project`` definition deterministically."""
    return DomainDefinition(
        id=PROJECT_DOMAIN_ID,
        name="project",
        display_name="Project",
        version=PROJECT_DOMAIN_VERSION,
        kind=DomainKind.PROJECT,
        description=(
            "Generic project management with conditional software-project "
            "analysis, development, validation, and self-development capability."
        ),
        manifest_id=PROJECT_MANIFEST_ID,
        reasoning_profile=PROJECT_PROFILE_NAME,
        resources=PROJECT_RESOURCE_IDS,
        rules=PROJECT_RULE_IDS,
        operations=PROJECT_OPERATION_IDS,
        workflows=PROJECT_WORKFLOW_IDS,
        permissions=PROJECT_PERMISSION_IDS,
        validators=(),
        presentation_policy={
            "detail_level": "detailed",
            "include_uncertainty": True,
            "include_provenance": True,
            "include_alternatives": True,
            "allow_speculation": False,
            "require_disclaimers": False,
        },
        dependencies=(),
        optional_dependencies=(),
        conflicts=(),
        capabilities=(
            DomainCapability(
                name="project_management",
                kind="management",
                provided_by=PROJECT_DOMAIN_ID,
                version=PROJECT_DOMAIN_VERSION,
                metadata={"phase": "10.30"},
            ),
            DomainCapability(
                name="project_milestone_planning",
                kind="planning",
                provided_by=PROJECT_DOMAIN_ID,
                version=PROJECT_DOMAIN_VERSION,
                metadata={"phase": "10.30"},
            ),
            DomainCapability(
                name="project_dependency_tracking",
                kind="reasoning",
                provided_by=PROJECT_DOMAIN_ID,
                version=PROJECT_DOMAIN_VERSION,
                metadata={"phase": "10.30"},
            ),
            DomainCapability(
                name="project_status_review",
                kind="analysis",
                provided_by=PROJECT_DOMAIN_ID,
                version=PROJECT_DOMAIN_VERSION,
                metadata={"phase": "10.30"},
            ),
            DomainCapability(
                name="project_resource_analysis",
                kind="analysis",
                provided_by=PROJECT_DOMAIN_ID,
                version=PROJECT_DOMAIN_VERSION,
                metadata={"phase": "10.30"},
            ),
            DomainCapability(
                name="project_software_analysis",
                kind="analysis",
                provided_by=PROJECT_DOMAIN_ID,
                version=PROJECT_DOMAIN_VERSION,
                metadata={"phase": "10.30"},
            ),
            DomainCapability(
                name="project_software_development",
                kind="execution",
                provided_by=PROJECT_DOMAIN_ID,
                version=PROJECT_DOMAIN_VERSION,
                metadata={"phase": "10.30"},
            ),
            DomainCapability(
                name="project_self_development",
                kind="development",
                provided_by=PROJECT_DOMAIN_ID,
                version=PROJECT_DOMAIN_VERSION,
                metadata={"phase": "10.30"},
            ),
        ),
        enabled=True,
        metadata=DomainMetadata(
            author="CMM OS",
            license="internal",
            tags=(
                "project",
                "milestones",
                "dependencies",
                "status",
                "software",
                "self-development",
            ),
            metadata={"phase": "10.30"},
        ),
    )


__all__ = [
    "PROJECT_DOMAIN_ID",
    "PROJECT_DOMAIN_VERSION",
    "PROJECT_MANIFEST_ID",
    "PROJECT_OPERATION_IDS",
    "PROJECT_PERMISSION_IDS",
    "PROJECT_PROFILE_NAME",
    "PROJECT_RESOURCE_IDS",
    "PROJECT_RULE_IDS",
    "PROJECT_WORKFLOW_IDS",
    "build_project_domain_definition",
]
