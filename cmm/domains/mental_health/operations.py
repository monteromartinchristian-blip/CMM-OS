"""Phase 10.52 — Mental Health Domain Operations.

Eight declarative operations.  No implementation is embedded here; an
operation without a provided implementation is registered as **UNAVAILABLE**
(fail-closed): declaration never implies availability.

Safety posture (frozen design §19, §29):

- Every operation is an analysis/preparation operation except
  ``propose_memory_update``, which is **memory-proposal only**.
- No operation performs an autonomous external action, communicates
  externally, books anything, or directly mutates persistent memory.
- ``propose_memory_update`` produces only the canonical proposal/binding
  shape established by the Phase 10.18 Domain Memory Integration.  It can
  never call a memory store; ``PROPOSAL != MUTATION``.
- ``analyze_therapy_transcript`` structurally requires transcript
  provenance / speaker-separation inputs; without them it must not produce
  high-confidence output.
- ``required_resources`` uses strict AND semantics: an operation only
  declares a resource it structurally consumes.
"""

from __future__ import annotations

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.enums import DomainOperationType
from cmm.domains.mental_health.catalog import MENTAL_HEALTH_OPERATION_IDS
from cmm.domains.operation_contracts import DomainOperationDefinition

__all__ = ["MENTAL_HEALTH_OPERATION_IDS", "build_mental_health_operation_definitions"]

_OPERATION_TYPES: dict[str, DomainOperationType] = {
    "mental_health.review_emotional_context": DomainOperationType.ANALYSIS,
    "mental_health.prepare_therapy_session": DomainOperationType.PREPARATION,
    "mental_health.review_therapy_session": DomainOperationType.ANALYSIS,
    "mental_health.analyze_therapy_transcript": DomainOperationType.SENSITIVE,
    "mental_health.compare_emotional_periods": DomainOperationType.ANALYSIS,
    "mental_health.map_fact_interpretation_uncertainty": DomainOperationType.ANALYSIS,
    "mental_health.review_emotional_decision": DomainOperationType.ANALYSIS,
    "mental_health.propose_memory_update": DomainOperationType.MEMORY,
}

_APPROVAL_REQUIRED = frozenset(
    {
        "mental_health.propose_memory_update",
        "mental_health.analyze_therapy_transcript",
    }
)

_HIGHER_RISK = frozenset(
    {
        "mental_health.propose_memory_update",
        "mental_health.analyze_therapy_transcript",
    }
)

# Proposal-only operations: they propose a write rather than perform one.
# Independent of ``requires_approval`` and never implying direct mutation.
_PROPOSAL_ONLY = frozenset({"mental_health.propose_memory_update"})

# Resources each operation structurally consumes (AND semantics).
_REQUIRED_RESOURCES: dict[str, tuple[str, ...]] = {
    "mental_health.review_emotional_context": ("mental_health.conversation",),
    "mental_health.prepare_therapy_session": (
        "mental_health.therapy_session_note",
        "mental_health.user_reflection",
    ),
    "mental_health.review_therapy_session": ("mental_health.therapy_session_note",),
    "mental_health.analyze_therapy_transcript": ("mental_health.therapy_transcript",),
    "mental_health.compare_emotional_periods": ("mental_health.memory_reference",),
    "mental_health.map_fact_interpretation_uncertainty": (
        "mental_health.user_reflection",
    ),
    "mental_health.review_emotional_decision": ("mental_health.decision",),
    "mental_health.propose_memory_update": ("mental_health.memory_reference",),
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


_INPUT_SCHEMAS: dict[str, dict] = {
    "mental_health.review_emotional_context": _schema(
        ("conversation_refs",), {"conversation_refs": _ids(1)}
    ),
    "mental_health.prepare_therapy_session": _schema(
        ("session_date",),
        {"session_date": {"type": "string"}, "topic": {"type": "string"}},
    ),
    "mental_health.review_therapy_session": _schema(
        ("note_refs",), {"note_refs": _ids(1)}
    ),
    # Transcript analysis structurally requires speaker-separated, sourced
    # turns: without canonical source/provenance evidence the operation must
    # remain limited.  ``source_provenance`` carries the canonical
    # ``ResourceProvenance`` for the transcript resource and each turn carries
    # its own ``source_ref`` — speaker separation alone is not provenance.
    "mental_health.analyze_therapy_transcript": _schema(
        ("transcript_ref", "source_provenance", "speaker_turns"),
        {
            "transcript_ref": {"type": "string"},
            "source_provenance": {"type": "object"},
            "speaker_turns": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["turn_id", "speaker", "source_ref"],
                    "properties": {
                        "turn_id": {"type": "string"},
                        "speaker": {"type": "string"},
                        "source_ref": {"type": "string"},
                        "verbatim": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                "minItems": 1,
            },
        },
    ),
    "mental_health.compare_emotional_periods": _schema(
        ("period_refs",), {"period_refs": _ids(2)}
    ),
    "mental_health.map_fact_interpretation_uncertainty": _schema(
        ("statement_refs",), {"statement_refs": _ids(1)}
    ),
    "mental_health.review_emotional_decision": _schema(
        ("decision_ref",), {"decision_ref": {"type": "string"}}
    ),
    # Memory proposals carry the canonical proposal payload; they never carry
    # a direct-write instruction.
    "mental_health.propose_memory_update": _schema(
        ("content_kind", "summary"),
        {
            "content_kind": {"type": "string"},
            "summary": {"type": "string"},
            "affected_reference_ids": _ID_ARRAY,
        },
    ),
}

_OUTPUT_SCHEMAS: dict[str, dict] = {
    "mental_health.review_emotional_context": _schema(
        ("review",), {"review": {"type": "object"}}
    ),
    "mental_health.prepare_therapy_session": _schema(
        ("agenda", "questions", "unresolved_items"),
        {
            "agenda": {"type": "array", "items": {"type": "string"}},
            "questions": {"type": "array", "items": {"type": "string"}},
            "unresolved_items": {"type": "array", "items": {"type": "string"}},
        },
    ),
    "mental_health.review_therapy_session": _schema(
        ("review", "speaker_attribution"),
        {"review": {"type": "object"}, "speaker_attribution": {"type": "object"}},
    ),
    "mental_health.analyze_therapy_transcript": _schema(
        ("turns", "provenance", "uncertainty"),
        {
            "turns": {"type": "array", "items": {"type": "object"}},
            "provenance": {"type": "object"},
            "uncertainty": {"type": "object"},
        },
    ),
    "mental_health.compare_emotional_periods": _schema(
        ("comparison", "provenance"),
        {"comparison": {"type": "object"}, "provenance": {"type": "object"}},
    ),
    "mental_health.map_fact_interpretation_uncertainty": _schema(
        ("map",), {"map": {"type": "object"}}
    ),
    "mental_health.review_emotional_decision": _schema(
        ("review",), {"review": {"type": "object"}}
    ),
    "mental_health.propose_memory_update": _schema(
        ("proposal", "binding"),
        {"proposal": {"type": "object"}, "binding": {"type": "object"}},
    ),
}


def build_mental_health_operation_definitions() -> tuple[
    DomainOperationDefinition, ...
]:
    """Build the eight Mental Health operation definitions deterministically."""
    result = []
    for operation_id in MENTAL_HEALTH_OPERATION_IDS:
        operation_type = _OPERATION_TYPES[operation_id]
        operation_name = operation_id.split(".", 1)[1]
        result.append(
            DomainOperationDefinition(
                operation_id=operation_id,
                domain_id="domain:mental-health",
                version="1.0.0",
                name=operation_name.replace("_", " ").title(),
                description=(f"Conservative structured operation for {operation_id}."),
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
                requires_approval=operation_id in _APPROVAL_REQUIRED,
                validation_policy_id=None,
                rollback_policy_id=None,
                enabled=True,
                metadata={
                    "phase": "10.52",
                    "domain": "mental-health",
                    "proposal_only": operation_id in _PROPOSAL_ONLY,
                    # Direct memory mutation is structurally impossible for
                    # every Mental Health operation (frozen design §12).
                    "direct_memory_write": False,
                },
            )
        )
    return tuple(result)
