"""Phase 10.21 — Relationships Domain package.

A conservative, proposal-only, fail-closed Domain Pack for personal
relationships.  Relationships never diagnoses a third party, never attributes
intention as fact without direct evidence, never collapses ambivalence, never
adopts a relational decision without explicit confirmation, never modifies or
enforces a boundary autonomously, and never contacts or communicates with
another person automatically.
"""

from __future__ import annotations

from cmm.domains.relationships.bootstrap import (
    RelationshipsDomainBootstrap,
    build_standard_relationships_domain_bootstrap,
)
from cmm.domains.relationships.catalog import (
    CANONICAL_RELATIONSHIPS_ENTITY_TYPES,
    CANONICAL_RELATIONSHIPS_OPERATION_IDS,
    CANONICAL_RELATIONSHIPS_RESOURCE_IDS,
    CANONICAL_RELATIONSHIPS_RULE_IDS,
    CANONICAL_RELATIONSHIPS_WORKFLOW_IDS,
)
from cmm.domains.relationships.definition import (
    RELATIONSHIPS_DOMAIN_ID,
    RELATIONSHIPS_DOMAIN_VERSION,
    RELATIONSHIPS_MANIFEST_ID,
    RELATIONSHIPS_OPERATION_IDS,
    RELATIONSHIPS_PERMISSION_IDS,
    RELATIONSHIPS_RESOURCE_IDS,
    RELATIONSHIPS_RULE_IDS,
    RELATIONSHIPS_WORKFLOW_IDS,
    build_relationships_domain_definition,
)
from cmm.domains.relationships.integration import (
    RelationshipsDomainIntegrationResult,
    register_relationships_domain,
)
from cmm.domains.relationships.memory import (
    build_relationships_memory_binding,
    build_relationships_memory_proposal,
    build_relationships_memory_view,
    build_relationships_memory_view_request,
    validate_relationships_memory_binding,
)
from cmm.domains.relationships.operations import (
    build_relationships_operation_definitions,
)
from cmm.domains.relationships.permissions import (
    RELATIONSHIPS_PERMISSION_POLICY_ID,
    build_relationships_permission_policy,
)
from cmm.domains.relationships.presentation import (
    build_relationships_presentation_policy,
)
from cmm.domains.relationships.profile import (
    RELATIONSHIPS_PROFILE_ID,
    RELATIONSHIPS_PROFILE_NAME,
    RELATIONSHIPS_PROHIBITED_ACTIONS,
    build_relationships_profile,
)
from cmm.domains.relationships.resources import (
    RELATIONSHIPS_RESOURCE_KINDS,
    build_relationships_resource_definitions,
)
from cmm.domains.relationships.rules import (
    AmbivalencePreservationRule,
    BoundaryConsistencyRule,
    DoNotInferIntentRule,
    EmotionNeedDistinctionRule,
    PatternWithoutCertaintyRule,
    RelationshipTimelineRule,
    SelfOtherPerspectiveRule,
    SeparateRelationshipFactInterpretationRule,
    build_relationships_rules,
)
from cmm.domains.relationships.trace import (
    assemble_relationships_trace,
    build_relationships_trace_contribution,
    build_relationships_trace_reference,
    validate_relationships_trace,
)
from cmm.domains.relationships.workflows import (
    build_relationships_workflow_definitions,
)

__all__ = [
    "CANONICAL_RELATIONSHIPS_ENTITY_TYPES",
    "CANONICAL_RELATIONSHIPS_OPERATION_IDS",
    "CANONICAL_RELATIONSHIPS_RESOURCE_IDS",
    "CANONICAL_RELATIONSHIPS_RULE_IDS",
    "CANONICAL_RELATIONSHIPS_WORKFLOW_IDS",
    "RELATIONSHIPS_DOMAIN_ID",
    "RELATIONSHIPS_DOMAIN_VERSION",
    "RELATIONSHIPS_MANIFEST_ID",
    "RELATIONSHIPS_OPERATION_IDS",
    "RELATIONSHIPS_PERMISSION_IDS",
    "RELATIONSHIPS_PERMISSION_POLICY_ID",
    "RELATIONSHIPS_PROFILE_ID",
    "RELATIONSHIPS_PROFILE_NAME",
    "RELATIONSHIPS_PROHIBITED_ACTIONS",
    "RELATIONSHIPS_RESOURCE_IDS",
    "RELATIONSHIPS_RESOURCE_KINDS",
    "RELATIONSHIPS_RULE_IDS",
    "RELATIONSHIPS_WORKFLOW_IDS",
    "AmbivalencePreservationRule",
    "BoundaryConsistencyRule",
    "DoNotInferIntentRule",
    "EmotionNeedDistinctionRule",
    "PatternWithoutCertaintyRule",
    "RelationshipTimelineRule",
    "RelationshipsDomainBootstrap",
    "RelationshipsDomainIntegrationResult",
    "SelfOtherPerspectiveRule",
    "SeparateRelationshipFactInterpretationRule",
    "assemble_relationships_trace",
    "build_relationships_domain_definition",
    "build_relationships_memory_binding",
    "build_relationships_memory_proposal",
    "build_relationships_memory_view",
    "build_relationships_memory_view_request",
    "build_relationships_operation_definitions",
    "build_relationships_permission_policy",
    "build_relationships_presentation_policy",
    "build_relationships_profile",
    "build_relationships_resource_definitions",
    "build_relationships_rules",
    "build_relationships_trace_contribution",
    "build_relationships_trace_reference",
    "build_relationships_workflow_definitions",
    "build_standard_relationships_domain_bootstrap",
    "register_relationships_domain",
    "validate_relationships_memory_binding",
    "validate_relationships_trace",
]
