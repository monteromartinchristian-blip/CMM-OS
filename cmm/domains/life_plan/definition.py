"""Phase 10.29 — Life Plan Domain Definition.

Builds the immutable ``domain:life-plan`` definition deterministically using
the shared ``DomainDefinition`` contract. No global registration at import time.
"""

from __future__ import annotations

from cmm.domains.contracts import DomainCapability, DomainDefinition, DomainMetadata
from cmm.domains.enums import DomainKind
from cmm.domains.life_plan.catalog import (
    CANONICAL_LIFE_PLAN_OPERATION_IDS,
    CANONICAL_LIFE_PLAN_RESOURCE_IDS,
    CANONICAL_LIFE_PLAN_RULE_IDS,
    CANONICAL_LIFE_PLAN_WORKFLOW_IDS,
)

LIFE_PLAN_DOMAIN_ID = "domain:life-plan"
LIFE_PLAN_DOMAIN_VERSION = "1.0.0"
LIFE_PLAN_MANIFEST_ID = "manifest:life-plan:1.0.0"
LIFE_PLAN_PROFILE_NAME = "LifePlanProfile"

LIFE_PLAN_RESOURCE_IDS: tuple[str, ...] = CANONICAL_LIFE_PLAN_RESOURCE_IDS
LIFE_PLAN_RULE_IDS: tuple[str, ...] = CANONICAL_LIFE_PLAN_RULE_IDS
LIFE_PLAN_OPERATION_IDS: tuple[str, ...] = CANONICAL_LIFE_PLAN_OPERATION_IDS
LIFE_PLAN_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_LIFE_PLAN_WORKFLOW_IDS

LIFE_PLAN_PERMISSION_IDS: tuple[str, ...] = ("domain-permission:life-plan:1.0.0",)


def build_life_plan_domain_definition() -> DomainDefinition:
    """Build the immutable ``domain:life-plan`` definition deterministically."""
    return DomainDefinition(
        id=LIFE_PLAN_DOMAIN_ID,
        name="life-plan",
        display_name="Life Plan",
        version=LIFE_PLAN_DOMAIN_VERSION,
        kind=DomainKind.PERSONAL,
        description=(
            "Life Plan coordinating domain for medium- and long-term goals, "
            "scenarios, dependencies, resources, constraints, risks, decisions, "
            "milestones, and plan drift. Coordinates authorized, purpose-minimized "
            "supporting-domain contributions without taking ownership of specialized "
            "domain semantics."
        ),
        manifest_id=LIFE_PLAN_MANIFEST_ID,
        reasoning_profile=LIFE_PLAN_PROFILE_NAME,
        resources=LIFE_PLAN_RESOURCE_IDS,
        rules=LIFE_PLAN_RULE_IDS,
        operations=LIFE_PLAN_OPERATION_IDS,
        workflows=LIFE_PLAN_WORKFLOW_IDS,
        permissions=LIFE_PLAN_PERMISSION_IDS,
        validators=(),
        presentation_policy={
            "detail_level": "detailed",
            "include_uncertainty": True,
            "include_provenance": True,
            "include_alternatives": True,
            "allow_speculation": False,
            "require_disclaimers": True,
        },
        dependencies=(),
        optional_dependencies=(),
        conflicts=(),
        capabilities=(
            DomainCapability(
                name="life_plan_goal_review",
                kind="analysis",
                provided_by=LIFE_PLAN_DOMAIN_ID,
                version=LIFE_PLAN_DOMAIN_VERSION,
                metadata={"phase": "10.29"},
            ),
            DomainCapability(
                name="life_plan_scenario_comparison",
                kind="analysis",
                provided_by=LIFE_PLAN_DOMAIN_ID,
                version=LIFE_PLAN_DOMAIN_VERSION,
                metadata={"phase": "10.29"},
            ),
            DomainCapability(
                name="life_plan_dependency_analysis",
                kind="reasoning",
                provided_by=LIFE_PLAN_DOMAIN_ID,
                version=LIFE_PLAN_DOMAIN_VERSION,
                metadata={"phase": "10.29"},
            ),
            DomainCapability(
                name="life_plan_resource_constraint_review",
                kind="analysis",
                provided_by=LIFE_PLAN_DOMAIN_ID,
                version=LIFE_PLAN_DOMAIN_VERSION,
                metadata={"phase": "10.29"},
            ),
            DomainCapability(
                name="life_plan_decision_tracking",
                kind="reasoning",
                provided_by=LIFE_PLAN_DOMAIN_ID,
                version=LIFE_PLAN_DOMAIN_VERSION,
                metadata={"phase": "10.29"},
            ),
            DomainCapability(
                name="life_plan_timeline_planning",
                kind="planning",
                provided_by=LIFE_PLAN_DOMAIN_ID,
                version=LIFE_PLAN_DOMAIN_VERSION,
                metadata={"phase": "10.29"},
            ),
            DomainCapability(
                name="life_plan_feasibility_review",
                kind="analysis",
                provided_by=LIFE_PLAN_DOMAIN_ID,
                version=LIFE_PLAN_DOMAIN_VERSION,
                metadata={"phase": "10.29"},
            ),
            DomainCapability(
                name="life_plan_cross_domain_coordination",
                kind="reasoning",
                provided_by=LIFE_PLAN_DOMAIN_ID,
                version=LIFE_PLAN_DOMAIN_VERSION,
                metadata={"phase": "10.29"},
            ),
            DomainCapability(
                name="life_plan_plan_drift_review",
                kind="analysis",
                provided_by=LIFE_PLAN_DOMAIN_ID,
                version=LIFE_PLAN_DOMAIN_VERSION,
                metadata={"phase": "10.29"},
            ),
            DomainCapability(
                name="life_plan_periodic_review",
                kind="planning",
                provided_by=LIFE_PLAN_DOMAIN_ID,
                version=LIFE_PLAN_DOMAIN_VERSION,
                metadata={"phase": "10.29"},
            ),
        ),
        enabled=True,
        metadata=DomainMetadata(
            author="CMM OS",
            license="internal",
            tags=(
                "life-plan",
                "goals",
                "scenarios",
                "milestones",
                "timeline",
                "coordination",
            ),
            metadata={"phase": "10.29"},
        ),
    )


__all__ = [
    "LIFE_PLAN_DOMAIN_ID",
    "LIFE_PLAN_DOMAIN_VERSION",
    "LIFE_PLAN_MANIFEST_ID",
    "LIFE_PLAN_OPERATION_IDS",
    "LIFE_PLAN_PERMISSION_IDS",
    "LIFE_PLAN_PROFILE_NAME",
    "LIFE_PLAN_RESOURCE_IDS",
    "LIFE_PLAN_RULE_IDS",
    "LIFE_PLAN_WORKFLOW_IDS",
    "build_life_plan_domain_definition",
]
