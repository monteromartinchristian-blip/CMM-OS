"""Phase 10.22 — University Domain Definition."""

from __future__ import annotations

from cmm.domains.contracts import DomainCapability, DomainDefinition, DomainMetadata
from cmm.domains.enums import DomainKind
from cmm.domains.university.catalog import (
    CANONICAL_UNIVERSITY_OPERATION_IDS,
    CANONICAL_UNIVERSITY_RESOURCE_IDS,
    CANONICAL_UNIVERSITY_RULE_IDS,
    CANONICAL_UNIVERSITY_WORKFLOW_IDS,
)

UNIVERSITY_DOMAIN_ID = "domain:university"
UNIVERSITY_DOMAIN_VERSION = "1.0.0"
UNIVERSITY_MANIFEST_ID = "manifest:university:1.0.0"
UNIVERSITY_PROFILE_NAME = "UniversityProfile"

UNIVERSITY_RESOURCE_IDS: tuple[str, ...] = CANONICAL_UNIVERSITY_RESOURCE_IDS
UNIVERSITY_RULE_IDS: tuple[str, ...] = CANONICAL_UNIVERSITY_RULE_IDS
UNIVERSITY_OPERATION_IDS: tuple[str, ...] = CANONICAL_UNIVERSITY_OPERATION_IDS
UNIVERSITY_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_UNIVERSITY_WORKFLOW_IDS

UNIVERSITY_PERMISSION_IDS: tuple[str, ...] = ("domain-permission:university:1.0.0",)


def build_university_domain_definition() -> DomainDefinition:
    """Build the immutable ``domain:university`` definition deterministically."""
    return DomainDefinition(
        id=UNIVERSITY_DOMAIN_ID,
        name="university",
        display_name="University",
        version=UNIVERSITY_DOMAIN_VERSION,
        kind=DomainKind.PERSONAL,
        description=(
            "University domain for structured reasoning and preparation about "
            "academic life: degrees, subjects, assignments, examinations, exam "
            "attempts, grades, deadlines, credits/ECTS, academic requirements, "
            "subject status, study planning, workload, observed academic "
            "performance, degree completion, TFG planning, and formal-procedure "
            "preparation.  University preserves source authority by attribute, "
            "provenance, temporality, uncertainty, academic-integrity "
            "constraints (Mode C), and user control.  It never adopts academic "
            "decisions, never sends email, never submits formal procedures, "
            "never modifies the official university record, and never infers "
            "intellectual capacity from observed performance."
        ),
        manifest_id=UNIVERSITY_MANIFEST_ID,
        reasoning_profile=UNIVERSITY_PROFILE_NAME,
        resources=UNIVERSITY_RESOURCE_IDS,
        rules=UNIVERSITY_RULE_IDS,
        operations=UNIVERSITY_OPERATION_IDS,
        workflows=UNIVERSITY_WORKFLOW_IDS,
        permissions=UNIVERSITY_PERMISSION_IDS,
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
                name="university_academic_record",
                kind="analysis",
                provided_by=UNIVERSITY_DOMAIN_ID,
                version=UNIVERSITY_DOMAIN_VERSION,
                metadata={"phase": "10.22"},
            ),
            DomainCapability(
                name="university_planning",
                kind="planning",
                provided_by=UNIVERSITY_DOMAIN_ID,
                version=UNIVERSITY_DOMAIN_VERSION,
                metadata={"phase": "10.22"},
            ),
            DomainCapability(
                name="university_preparation",
                kind="operation",
                provided_by=UNIVERSITY_DOMAIN_ID,
                version=UNIVERSITY_DOMAIN_VERSION,
                metadata={"phase": "10.22"},
            ),
            DomainCapability(
                name="university_deadline_tracking",
                kind="reasoning",
                provided_by=UNIVERSITY_DOMAIN_ID,
                version=UNIVERSITY_DOMAIN_VERSION,
                metadata={"phase": "10.22"},
            ),
            DomainCapability(
                name="university_decision_support",
                kind="safety",
                provided_by=UNIVERSITY_DOMAIN_ID,
                version=UNIVERSITY_DOMAIN_VERSION,
                metadata={"phase": "10.22"},
            ),
        ),
        enabled=True,
        metadata=DomainMetadata(
            author="CMM OS",
            license="internal",
            tags=("university", "academic", "planning", "personal"),
            metadata={"phase": "10.22"},
        ),
    )


__all__ = [
    "UNIVERSITY_DOMAIN_ID",
    "UNIVERSITY_DOMAIN_VERSION",
    "UNIVERSITY_MANIFEST_ID",
    "UNIVERSITY_OPERATION_IDS",
    "UNIVERSITY_PERMISSION_IDS",
    "UNIVERSITY_PROFILE_NAME",
    "UNIVERSITY_RESOURCE_IDS",
    "UNIVERSITY_RULE_IDS",
    "UNIVERSITY_WORKFLOW_IDS",
    "build_university_domain_definition",
]
