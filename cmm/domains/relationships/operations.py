"""Phase 10.21 — Relationships Domain Operations.

Ten declarative operations.  No implementation is embedded here; an operation
without a provided implementation is registered as **UNAVAILABLE** (fail-closed).

Safety posture (spec §1, §8):
- No operation performs an autonomous relational action.  ``prepare_conversation``
  is PREPARATION only — it prepares material for a conversation and never sends,
  contacts, or initiates communication.  No EXTERNAL/send operation exists anywhere
  in the domain.
- ``review_boundaries`` only *reviews* boundary consistency; it never modifies,
  enforces, communicates, or withdraws a boundary.
- ``required_resources`` uses strict AND semantics: an operation only declares a
  resource it structurally consumes.  It is never mechanically populated.
- There are no MEMORY, PLANNING, or DESTRUCTIVE operations: the domain memory
  policy is read-only (``allow_write=False``) and relational decisions require
  explicit user confirmation.
"""

from __future__ import annotations

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.enums import DomainOperationType
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.relationships.catalog import CANONICAL_RELATIONSHIPS_OPERATION_IDS

RELATIONSHIPS_OPERATION_IDS: tuple[str, ...] = CANONICAL_RELATIONSHIPS_OPERATION_IDS

_OPERATION_TYPES = {
    "relationships.build_timeline": DomainOperationType.ANALYSIS,
    "relationships.compare_periods": DomainOperationType.ANALYSIS,
    "relationships.detect_patterns": DomainOperationType.ANALYSIS,
    "relationships.extract_events": DomainOperationType.ANALYSIS,
    "relationships.generate_relationship_summary": DomainOperationType.PREPARATION,
    "relationships.identify_needs": DomainOperationType.ANALYSIS,
    "relationships.prepare_conversation": DomainOperationType.PREPARATION,
    "relationships.review_boundaries": DomainOperationType.SENSITIVE,
    "relationships.separate_facts_interpretations": DomainOperationType.ANALYSIS,
    "relationships.track_open_questions": DomainOperationType.ANALYSIS,
}

_APPROVAL_REQUIRED = frozenset(
    {
        "relationships.prepare_conversation",
        "relationships.review_boundaries",
    }
)

_HIGHER_RISK = frozenset(
    {
        "relationships.prepare_conversation",
        "relationships.review_boundaries",
    }
)

# No proposal-only operations: the domain memory policy is read-only and no
# operation proposes a memory write.  Relational decisions are never adopted.
_PROPOSAL_ONLY = frozenset()

# Resources each operation structurally consumes (AND semantics).  Only
# operations that genuinely read a Relationships resource declare it here.
_REQUIRED_RESOURCES = {
    "relationships.build_timeline": ("relationships.timeline",),
    "relationships.compare_periods": ("relationships.timeline",),
    "relationships.detect_patterns": ("relationships.timeline",),
    "relationships.extract_events": ("relationships.conversation",),
    "relationships.generate_relationship_summary": ("relationships.timeline",),
    "relationships.identify_needs": ("relationships.user_message",),
    "relationships.prepare_conversation": ("relationships.conversation",),
    "relationships.review_boundaries": ("relationships.user_message",),
    "relationships.separate_facts_interpretations": ("relationships.user_message",),
    "relationships.track_open_questions": ("relationships.user_message",),
}


def _schema(required: tuple[str, ...], properties: dict) -> dict:
    """Build a deterministic JSON object schema with closed properties."""
    return {
        "type": "object",
        "required": list(required),
        "properties": properties,
        "additionalProperties": False,
    }


_ID_ARRAY = {"type": "array", "items": {"type": "string"}}


def _ids(min_items: int) -> dict:
    return {"type": "array", "items": {"type": "string"}, "minItems": min_items}


_INPUT_SCHEMAS = {
    "relationships.build_timeline": _schema(("source_ids",), {"source_ids": _ids(1)}),
    "relationships.compare_periods": _schema(
        ("period_a", "period_b"),
        {
            "period_a": _schema(("start", "end"), {}),
            "period_b": _schema(("start", "end"), {}),
        },
    ),
    "relationships.detect_patterns": _schema(("source_ids",), {"source_ids": _ids(1)}),
    "relationships.extract_events": _schema(
        ("conversation_id",), {"conversation_id": {"type": "string"}}
    ),
    "relationships.generate_relationship_summary": _schema(
        ("source_ids",), {"source_ids": _ids(1)}
    ),
    "relationships.identify_needs": _schema(("source_ids",), {"source_ids": _ids(1)}),
    "relationships.prepare_conversation": _schema(
        ("topic",),
        {"topic": {"type": "string"}, "source_ids": _ID_ARRAY},
    ),
    "relationships.review_boundaries": _schema(
        ("boundary_ids",), {"boundary_ids": _ids(1)}
    ),
    "relationships.separate_facts_interpretations": _schema(
        ("source_ids",), {"source_ids": _ids(1)}
    ),
    "relationships.track_open_questions": _schema(
        ("source_ids",), {"source_ids": _ids(1)}
    ),
}

_OUTPUT_SCHEMAS = {
    "relationships.build_timeline": _schema(
        ("events",), {"events": {"type": "array", "items": {"type": "object"}}}
    ),
    "relationships.compare_periods": _schema(
        ("comparison",), {"comparison": {"type": "object"}}
    ),
    "relationships.detect_patterns": _schema(
        ("patterns",), {"patterns": {"type": "array", "items": {"type": "object"}}}
    ),
    "relationships.extract_events": _schema(
        ("events",), {"events": {"type": "array", "items": {"type": "object"}}}
    ),
    "relationships.generate_relationship_summary": _schema(
        ("summary",), {"summary": {"type": "string"}}
    ),
    "relationships.identify_needs": _schema(
        ("needs",), {"needs": {"type": "array", "items": {"type": "object"}}}
    ),
    "relationships.prepare_conversation": _schema(
        ("preparation",), {"preparation": {"type": "object"}}
    ),
    "relationships.review_boundaries": _schema(
        ("review",), {"review": {"type": "object"}}
    ),
    "relationships.separate_facts_interpretations": _schema(
        ("category_map",), {"category_map": {"type": "object"}}
    ),
    "relationships.track_open_questions": _schema(
        ("questions",), {"questions": {"type": "array", "items": {"type": "string"}}}
    ),
}


def build_relationships_operation_definitions() -> tuple[
    DomainOperationDefinition, ...
]:
    """Build the ten Relationships Domain operation definitions deterministically."""
    result = []
    for operation_id in RELATIONSHIPS_OPERATION_IDS:
        operation_type = _OPERATION_TYPES[operation_id]
        operation_name = operation_id.split(".", 1)[1]
        requires_approval = operation_id in _APPROVAL_REQUIRED
        result.append(
            DomainOperationDefinition(
                operation_id=operation_id,
                domain_id="domain:relationships",
                version="1.0.0",
                name=operation_name.replace("_", " ").title(),
                description=f"Conservative structured operation for {operation_id}.",
                operation_type=operation_type,
                input_schema=_INPUT_SCHEMAS[operation_id],
                output_schema=_OUTPUT_SCHEMAS[operation_id],
                required_resources=_REQUIRED_RESOURCES[operation_id],
                required_permissions=(),
                risk_level=(
                    PolicyRiskLevel.MEDIUM
                    if operation_id in _HIGHER_RISK
                    else PolicyRiskLevel.LOW
                ),
                reversible=False,
                requires_approval=requires_approval,
                validation_policy_id=None,
                rollback_policy_id=None,
                enabled=True,
                metadata={
                    "phase": "10.21",
                    "domain": "relationships",
                    "proposal_only": operation_id in _PROPOSAL_ONLY,
                },
            )
        )
    return tuple(result)


__all__ = [
    "RELATIONSHIPS_OPERATION_IDS",
    "build_relationships_operation_definitions",
]
