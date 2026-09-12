"""Phase 10.52 — Mental Health Domain Definition.

Builds the immutable ``domain:mental-health`` definition deterministically
using the shared ``DomainDefinition`` contract.  No global registration happens
at import time.

``domain:mental-health`` is a sibling first-party Domain Pack: it specializes
ordinary emotional conversation, therapy continuity/analysis, longitudinal
emotional context and emotionally relevant decision support while Health keeps
clinical authority.  All persistence stays proposal-first and no parallel
infrastructure is introduced.
"""

from __future__ import annotations

from cmm.domains.contracts import DomainCapability, DomainDefinition, DomainMetadata
from cmm.domains.enums import DomainKind
from cmm.domains.mental_health.benchmarks import build_mental_health_benchmark_suites
from cmm.domains.mental_health.catalog import (
    CANONICAL_MENTAL_HEALTH_OPERATION_IDS,
    CANONICAL_MENTAL_HEALTH_RESOURCE_IDS,
    CANONICAL_MENTAL_HEALTH_RULE_IDS,
    CANONICAL_MENTAL_HEALTH_WORKFLOW_IDS,
    MENTAL_HEALTH_DOMAIN_ID,
    MENTAL_HEALTH_PROFILE_NAME,
)
from cmm.domains.mental_health.knowledge_package import (
    build_mental_health_knowledge_package_schema,
)
from cmm.domains.mental_health.model_policy import build_mental_health_model_policy
from cmm.domains.mental_health.privacy import build_mental_health_privacy_policy
from cmm.domains.mental_health.quality_metrics import (
    build_mental_health_quality_metrics,
)

MENTAL_HEALTH_DOMAIN_VERSION = "1.0.0"
MENTAL_HEALTH_MANIFEST_ID = "manifest:mental-health:1.0.0"

MENTAL_HEALTH_RESOURCE_IDS: tuple[str, ...] = CANONICAL_MENTAL_HEALTH_RESOURCE_IDS
MENTAL_HEALTH_RULE_IDS: tuple[str, ...] = CANONICAL_MENTAL_HEALTH_RULE_IDS
MENTAL_HEALTH_OPERATION_IDS: tuple[str, ...] = CANONICAL_MENTAL_HEALTH_OPERATION_IDS
MENTAL_HEALTH_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_MENTAL_HEALTH_WORKFLOW_IDS

MENTAL_HEALTH_PERMISSION_IDS: tuple[str, ...] = (
    "domain-permission:mental-health:1.0.0",
)


def build_mental_health_domain_definition() -> DomainDefinition:
    """Build the immutable ``domain:mental-health`` definition deterministically."""
    return DomainDefinition(
        id=MENTAL_HEALTH_DOMAIN_ID,
        name="mental-health",
        display_name="Mental Health",
        version=MENTAL_HEALTH_DOMAIN_VERSION,
        kind=DomainKind.PERSONAL,
        description=(
            "Personal Mental Health domain for ordinary emotional conversation, "
            "therapy continuity, pre- and post-therapy review, therapy "
            "transcript analysis, longitudinal emotional context and emotionally "
            "relevant decision support.  Mental Health keeps facts, "
            "observations, interpretations, hypotheses, fears, intuitions and "
            "uncertainty distinct; it never medicalizes ordinary distress, "
            "never invents a diagnosis or treatment authority, never fabricates "
            "a therapist statement, never persists a sensitive inference "
            "without the canonical proposal/approval path, and never overrides "
            "Health's authority over documented diagnosis, treatment, "
            "medication or medical safety."
        ),
        manifest_id=MENTAL_HEALTH_MANIFEST_ID,
        reasoning_profile=MENTAL_HEALTH_PROFILE_NAME,
        resources=MENTAL_HEALTH_RESOURCE_IDS,
        rules=MENTAL_HEALTH_RULE_IDS,
        operations=MENTAL_HEALTH_OPERATION_IDS,
        workflows=MENTAL_HEALTH_WORKFLOW_IDS,
        permissions=MENTAL_HEALTH_PERMISSION_IDS,
        validators=(),
        presentation_policy={
            "detail_level": "standard",
            "include_uncertainty": True,
            "include_provenance": True,
            "include_alternatives": True,
            "allow_speculation": False,
            "require_disclaimers": True,
        },
        # General remains the fallback.  Health/Relationships/Reflection/
        # Concerns participate only through normal cross-domain resolution and
        # never widen Mental Health authority.  Neurodivergence (Phase 10.53)
        # is intentionally absent and must not be required.
        dependencies=(),
        optional_dependencies=(),
        conflicts=(),
        capabilities=(
            DomainCapability(
                name="emotional_context_review",
                kind="reasoning",
                provided_by=MENTAL_HEALTH_DOMAIN_ID,
                version=MENTAL_HEALTH_DOMAIN_VERSION,
                metadata={"phase": "10.52"},
            ),
            DomainCapability(
                name="therapy_continuity",
                kind="reasoning",
                provided_by=MENTAL_HEALTH_DOMAIN_ID,
                version=MENTAL_HEALTH_DOMAIN_VERSION,
                metadata={"phase": "10.52"},
            ),
            DomainCapability(
                name="therapy_preparation",
                kind="preparation",
                provided_by=MENTAL_HEALTH_DOMAIN_ID,
                version=MENTAL_HEALTH_DOMAIN_VERSION,
                metadata={"phase": "10.52"},
            ),
            DomainCapability(
                name="therapy_transcript_analysis",
                kind="analysis",
                provided_by=MENTAL_HEALTH_DOMAIN_ID,
                version=MENTAL_HEALTH_DOMAIN_VERSION,
                metadata={"phase": "10.52"},
            ),
            DomainCapability(
                name="longitudinal_emotional_context",
                kind="analysis",
                provided_by=MENTAL_HEALTH_DOMAIN_ID,
                version=MENTAL_HEALTH_DOMAIN_VERSION,
                metadata={"phase": "10.52"},
            ),
            DomainCapability(
                name="emotional_decision_support",
                kind="reasoning",
                provided_by=MENTAL_HEALTH_DOMAIN_ID,
                version=MENTAL_HEALTH_DOMAIN_VERSION,
                metadata={"phase": "10.52"},
            ),
            DomainCapability(
                name="proportionate_safety_coordination",
                kind="safety",
                provided_by=MENTAL_HEALTH_DOMAIN_ID,
                version=MENTAL_HEALTH_DOMAIN_VERSION,
                metadata={"phase": "10.52"},
            ),
        ),
        enabled=True,
        metadata=DomainMetadata(
            author="CMM OS",
            license="internal",
            tags=("mental-health", "personal", "sensitive", "therapy"),
            metadata={"phase": "10.52"},
        ),
        model_policy=build_mental_health_model_policy(),
        benchmark_suites=build_mental_health_benchmark_suites(),
        quality_metrics=build_mental_health_quality_metrics(),
        knowledge_package_schema=build_mental_health_knowledge_package_schema(),
        privacy_policy=build_mental_health_privacy_policy(),
    )


__all__ = [
    "MENTAL_HEALTH_DOMAIN_ID",
    "MENTAL_HEALTH_DOMAIN_VERSION",
    "MENTAL_HEALTH_MANIFEST_ID",
    "MENTAL_HEALTH_OPERATION_IDS",
    "MENTAL_HEALTH_PERMISSION_IDS",
    "MENTAL_HEALTH_PROFILE_NAME",
    "MENTAL_HEALTH_RESOURCE_IDS",
    "MENTAL_HEALTH_RULE_IDS",
    "MENTAL_HEALTH_WORKFLOW_IDS",
    "build_mental_health_domain_definition",
]
