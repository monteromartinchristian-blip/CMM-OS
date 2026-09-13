"""Phase 10.53 — Neurodivergence Domain Definition.

Builds the immutable ``domain:neurodivergence`` definition deterministically
using the shared ``DomainDefinition`` contract.  No global registration happens
at import time.

``domain:neurodivergence`` is a sibling first-party Domain Pack: it specializes
exploratory and longitudinal neurodevelopmental reasoning, evidence
organization, differential/overlap comparison and professional-assessment
preparation while Health keeps clinical authority.  A model inference never
becomes a confirmed diagnosis, certainty stays visible, all persistence stays
proposal-first, and no parallel infrastructure is introduced.
"""

from __future__ import annotations

from cmm.domains.contracts import DomainCapability, DomainDefinition, DomainMetadata
from cmm.domains.enums import DomainKind
from cmm.domains.neurodivergence.benchmarks import (
    build_neurodivergence_benchmark_suites,
)
from cmm.domains.neurodivergence.catalog import (
    CANONICAL_NEURODIVERGENCE_OPERATION_IDS,
    CANONICAL_NEURODIVERGENCE_RESOURCE_IDS,
    CANONICAL_NEURODIVERGENCE_RULE_IDS,
    CANONICAL_NEURODIVERGENCE_WORKFLOW_IDS,
    NEURODIVERGENCE_DOMAIN_ID,
    NEURODIVERGENCE_PROFILE_NAME,
)
from cmm.domains.neurodivergence.knowledge_package import (
    build_neurodivergence_knowledge_package_schema,
)
from cmm.domains.neurodivergence.model_policy import (
    build_neurodivergence_model_policy,
)
from cmm.domains.neurodivergence.privacy import (
    build_neurodivergence_privacy_policy,
)
from cmm.domains.neurodivergence.quality_metrics import (
    build_neurodivergence_quality_metrics,
)

NEURODIVERGENCE_DOMAIN_VERSION = "1.0.0"
NEURODIVERGENCE_MANIFEST_ID = "manifest:neurodivergence:1.0.0"

NEURODIVERGENCE_RESOURCE_IDS: tuple[str, ...] = CANONICAL_NEURODIVERGENCE_RESOURCE_IDS
NEURODIVERGENCE_RULE_IDS: tuple[str, ...] = CANONICAL_NEURODIVERGENCE_RULE_IDS
NEURODIVERGENCE_OPERATION_IDS: tuple[str, ...] = CANONICAL_NEURODIVERGENCE_OPERATION_IDS
NEURODIVERGENCE_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_NEURODIVERGENCE_WORKFLOW_IDS

NEURODIVERGENCE_PERMISSION_IDS: tuple[str, ...] = (
    "domain-permission:neurodivergence:1.0.0",
)


def build_neurodivergence_domain_definition() -> DomainDefinition:
    """Build the immutable ``domain:neurodivergence`` definition deterministically."""
    return DomainDefinition(
        id=NEURODIVERGENCE_DOMAIN_ID,
        name="neurodivergence",
        display_name="Neurodivergence",
        version=NEURODIVERGENCE_DOMAIN_VERSION,
        kind=DomainKind.PERSONAL,
        description=(
            "Personal Neurodivergence domain for exploratory, longitudinal and "
            "evidence-sensitive neurodevelopmental reasoning: developmental "
            "history review, assessment-evidence organization, differential and "
            "overlap reasoning, functional-impact review and preparation for a "
            "professional assessment.  Neurodivergence keeps observations, "
            "self-report, third-party report, screening results, model "
            "interpretation, working hypotheses and negative or insufficient "
            "evidence distinct; it may explore freely and may hold useful "
            "working hypotheses, but it never promotes a model inference, a "
            "screening result, self-report or an isolated trait into a confirmed "
            "diagnosis, never overwrites Health's clinical authority, never "
            "claims a sibling domain's facts as its own, and never persists a "
            "sensitive label without the canonical proposal/approval path."
        ),
        manifest_id=NEURODIVERGENCE_MANIFEST_ID,
        reasoning_profile=NEURODIVERGENCE_PROFILE_NAME,
        resources=NEURODIVERGENCE_RESOURCE_IDS,
        rules=NEURODIVERGENCE_RULE_IDS,
        operations=NEURODIVERGENCE_OPERATION_IDS,
        workflows=NEURODIVERGENCE_WORKFLOW_IDS,
        permissions=NEURODIVERGENCE_PERMISSION_IDS,
        validators=(),
        presentation_policy={
            "detail_level": "standard",
            "include_uncertainty": True,
            "include_provenance": True,
            "include_alternatives": True,
            "allow_speculation": True,
            "require_disclaimers": False,
        },
        # General remains the fallback.  Health/Mental Health/University/
        # Relationships participate only through normal cross-domain resolution
        # and never widen Neurodivergence authority.  No sibling implementation
        # is required: cross-domain composition stays registry/permission-driven.
        dependencies=(),
        optional_dependencies=(),
        conflicts=(),
        capabilities=(
            DomainCapability(
                name="exploratory_neurodevelopmental_reasoning",
                kind="reasoning",
                provided_by=NEURODIVERGENCE_DOMAIN_ID,
                version=NEURODIVERGENCE_DOMAIN_VERSION,
                metadata={"phase": "10.53"},
            ),
            DomainCapability(
                name="developmental_history_review",
                kind="analysis",
                provided_by=NEURODIVERGENCE_DOMAIN_ID,
                version=NEURODIVERGENCE_DOMAIN_VERSION,
                metadata={"phase": "10.53"},
            ),
            DomainCapability(
                name="assessment_evidence_organization",
                kind="analysis",
                provided_by=NEURODIVERGENCE_DOMAIN_ID,
                version=NEURODIVERGENCE_DOMAIN_VERSION,
                metadata={"phase": "10.53"},
            ),
            DomainCapability(
                name="differential_overlap_reasoning",
                kind="reasoning",
                provided_by=NEURODIVERGENCE_DOMAIN_ID,
                version=NEURODIVERGENCE_DOMAIN_VERSION,
                metadata={"phase": "10.53"},
            ),
            DomainCapability(
                name="functional_impact_review",
                kind="analysis",
                provided_by=NEURODIVERGENCE_DOMAIN_ID,
                version=NEURODIVERGENCE_DOMAIN_VERSION,
                metadata={"phase": "10.53"},
            ),
            DomainCapability(
                name="professional_assessment_preparation",
                kind="preparation",
                provided_by=NEURODIVERGENCE_DOMAIN_ID,
                version=NEURODIVERGENCE_DOMAIN_VERSION,
                metadata={"phase": "10.53"},
            ),
        ),
        enabled=True,
        metadata=DomainMetadata(
            author="CMM OS",
            license="internal",
            tags=("neurodivergence", "personal", "sensitive", "developmental"),
            metadata={"phase": "10.53"},
        ),
        model_policy=build_neurodivergence_model_policy(),
        benchmark_suites=build_neurodivergence_benchmark_suites(),
        quality_metrics=build_neurodivergence_quality_metrics(),
        knowledge_package_schema=build_neurodivergence_knowledge_package_schema(),
        privacy_policy=build_neurodivergence_privacy_policy(),
    )


__all__ = [
    "NEURODIVERGENCE_DOMAIN_ID",
    "NEURODIVERGENCE_DOMAIN_VERSION",
    "NEURODIVERGENCE_MANIFEST_ID",
    "NEURODIVERGENCE_OPERATION_IDS",
    "NEURODIVERGENCE_PERMISSION_IDS",
    "NEURODIVERGENCE_PROFILE_NAME",
    "NEURODIVERGENCE_RESOURCE_IDS",
    "NEURODIVERGENCE_RULE_IDS",
    "NEURODIVERGENCE_WORKFLOW_IDS",
    "build_neurodivergence_domain_definition",
]
