"""Phase 10.53 — Neurodivergence Domain Operations.

Eight declarative operations.  No implementation is embedded here; an
operation without a provided implementation is registered as **UNAVAILABLE**
(fail-closed): declaration never implies availability.

Safety posture (frozen design §12, §28):

- Every operation is an evidence-organization or preparation operation except
  ``propose_memory_update``, which is **memory-proposal only**.
- No operation performs an autonomous external action, communicates
  externally, or directly mutates persistent memory.
- ``propose_memory_update`` carries the proposed certainty state, so a proposal
  can never silently upgrade a hypothesis into a confirmed state.
- ``prepare_assessment_summary`` is approval-gated: an assessment summary is
  sensitive material prepared for a professional, not an autonomous clinical
  statement.
- ``required_resources`` uses strict AND semantics: an operation only declares a
  resource it structurally consumes.

Operations are declarative.  No Neurodivergence operation runtime, executor or
registry is introduced.
"""

from __future__ import annotations

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.enums import DomainOperationType
from cmm.domains.neurodivergence.catalog import NEURODIVERGENCE_OPERATION_IDS
from cmm.domains.operation_contracts import DomainOperationDefinition

__all__ = [
    "NEURODIVERGENCE_OPERATION_IDS",
    "build_neurodivergence_operation_definitions",
]

_OPERATION_TYPES: dict[str, DomainOperationType] = {
    "neurodivergence.build_developmental_timeline": DomainOperationType.ANALYSIS,
    "neurodivergence.review_evidence": DomainOperationType.ANALYSIS,
    "neurodivergence.compare_assessment_sources": DomainOperationType.ANALYSIS,
    "neurodivergence.map_certainty_states": DomainOperationType.ANALYSIS,
    "neurodivergence.review_functional_impact": DomainOperationType.ANALYSIS,
    "neurodivergence.analyze_differential_overlap": DomainOperationType.ANALYSIS,
    "neurodivergence.prepare_assessment_summary": DomainOperationType.PREPARATION,
    "neurodivergence.propose_memory_update": DomainOperationType.MEMORY,
}

#: Preparing a professional assessment summary and proposing a persistence
#: change both require the canonical approval path.
_APPROVAL_REQUIRED = frozenset(
    {
        "neurodivergence.prepare_assessment_summary",
        "neurodivergence.propose_memory_update",
    }
)

_HIGHER_RISK = frozenset(
    {
        "neurodivergence.prepare_assessment_summary",
        "neurodivergence.propose_memory_update",
    }
)

#: Proposal-only operations propose a write rather than perform one.
_PROPOSAL_ONLY = frozenset({"neurodivergence.propose_memory_update"})

# Resources each operation structurally consumes (AND semantics).
_REQUIRED_RESOURCES: dict[str, tuple[str, ...]] = {
    "neurodivergence.build_developmental_timeline": (
        "neurodivergence.developmental_history",
        "neurodivergence.longitudinal_evidence",
    ),
    "neurodivergence.review_evidence": (
        "neurodivergence.assessment_records",
        "neurodivergence.developmental_history",
    ),
    "neurodivergence.compare_assessment_sources": (
        "neurodivergence.assessment_records",
        "neurodivergence.psychometric_results",
    ),
    "neurodivergence.map_certainty_states": ("neurodivergence.assessment_records",),
    "neurodivergence.review_functional_impact": (
        "neurodivergence.functional_impact",
        "neurodivergence.executive_function_context",
        "neurodivergence.sensory_context",
    ),
    "neurodivergence.analyze_differential_overlap": (
        "neurodivergence.differential_overlap_context",
    ),
    "neurodivergence.prepare_assessment_summary": (
        "neurodivergence.assessment_records",
        "neurodivergence.psychometric_results",
    ),
    "neurodivergence.propose_memory_update": ("neurodivergence.longitudinal_evidence",),
}


def _schema(required: tuple[str, ...], properties: dict) -> dict:
    """Build a deterministic JSON object schema with closed properties."""
    return {
        "type": "object",
        "required": list(required),
        "properties": properties,
        "additionalProperties": False,
    }


def _ids(min_items: int) -> dict:
    return {"type": "array", "items": {"type": "string"}, "minItems": min_items}


def _reference_array() -> dict:
    """An array of canonical reference objects (never a source body)."""
    return {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["ref_id"],
            "properties": {
                "ref_id": {"type": "string"},
                "source_domain": {"type": "string"},
                "source_ref": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "minItems": 1,
    }


_INPUT_SCHEMAS: dict[str, dict] = {
    # A developmental timeline needs referenced sources and explicit periods;
    # it never carries the developmental record text itself.
    "neurodivergence.build_developmental_timeline": _schema(
        ("source_refs", "periods"),
        {
            "source_refs": _reference_array(),
            "periods": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["period", "kind"],
                    "properties": {
                        "period": {"type": "string"},
                        "kind": {"type": "string"},
                        "source_ref": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                "minItems": 1,
            },
        },
    ),
    "neurodivergence.review_evidence": _schema(
        ("evidence_refs", "objective"),
        {
            "evidence_refs": _reference_array(),
            "objective": {"type": "string"},
            "hypothesis_labels": _ids(0),
        },
    ),
    # Comparing sources structurally requires at least two of them.
    "neurodivergence.compare_assessment_sources": _schema(
        ("source_refs",),
        {
            "source_refs": _reference_array(),
            "observed_period": {"type": "string"},
        },
    ),
    "neurodivergence.map_certainty_states": _schema(
        ("claim_refs",),
        {
            "claim_refs": _reference_array(),
            "include_negative_states": {"type": "boolean"},
        },
    ),
    "neurodivergence.review_functional_impact": _schema(
        ("observation_refs", "domains"),
        {
            "observation_refs": _reference_array(),
            "domains": _ids(1),
        },
    ),
    "neurodivergence.analyze_differential_overlap": _schema(
        ("evidence_refs", "hypothesis_labels"),
        {
            "evidence_refs": _reference_array(),
            "hypothesis_labels": _ids(1),
            "include_alternatives": {"type": "boolean"},
        },
    ),
    "neurodivergence.prepare_assessment_summary": _schema(
        ("evidence_refs", "objective"),
        {
            "evidence_refs": _reference_array(),
            "objective": {"type": "string"},
            "include_questions": {"type": "boolean"},
        },
    ),
    # A memory proposal always carries the proposed certainty state so a
    # hypothesis can never be proposed as a confirmed state.
    "neurodivergence.propose_memory_update": _schema(
        ("source_refs", "proposed_claim", "certainty_state"),
        {
            "source_refs": _reference_array(),
            "proposed_claim": {"type": "string"},
            "certainty_state": {"type": "string"},
            "proposed_state": {"type": "string"},
        },
    ),
}

_OUTPUT_SCHEMAS: dict[str, dict] = {
    "neurodivergence.build_developmental_timeline": _schema(
        ("timeline", "provenance"),
        {"timeline": {"type": "object"}, "provenance": {"type": "object"}},
    ),
    "neurodivergence.review_evidence": _schema(
        ("evidence", "uncertainty", "provenance"),
        {
            "evidence": {"type": "array", "items": {"type": "object"}},
            "uncertainty": {"type": "object"},
            "provenance": {"type": "object"},
        },
    ),
    "neurodivergence.compare_assessment_sources": _schema(
        ("comparison", "source_authority", "provenance"),
        {
            "comparison": {"type": "object"},
            "source_authority": {"type": "object"},
            "provenance": {"type": "object"},
        },
    ),
    "neurodivergence.map_certainty_states": _schema(
        ("certainty_states", "uncertainty"),
        {"certainty_states": {"type": "object"}, "uncertainty": {"type": "object"}},
    ),
    "neurodivergence.review_functional_impact": _schema(
        ("observations", "functional_relevance", "uncertainty"),
        {
            "observations": {"type": "array", "items": {"type": "object"}},
            "functional_relevance": {"type": "object"},
            "uncertainty": {"type": "object"},
        },
    ),
    "neurodivergence.analyze_differential_overlap": _schema(
        ("differential", "alternatives", "uncertainty"),
        {
            "differential": {"type": "object"},
            "alternatives": {"type": "array", "items": {"type": "object"}},
            "uncertainty": {"type": "object"},
        },
    ),
    "neurodivergence.prepare_assessment_summary": _schema(
        ("summary", "questions", "uncertainty", "provenance"),
        {
            "summary": {"type": "object"},
            "questions": {"type": "array", "items": {"type": "string"}},
            "uncertainty": {"type": "object"},
            "provenance": {"type": "object"},
        },
    ),
    "neurodivergence.propose_memory_update": _schema(
        ("proposal", "binding"),
        {"proposal": {"type": "object"}, "binding": {"type": "object"}},
    ),
}


def build_neurodivergence_operation_definitions() -> tuple[
    DomainOperationDefinition, ...
]:
    """Build the eight Neurodivergence operation definitions deterministically."""
    result = []
    for operation_id in NEURODIVERGENCE_OPERATION_IDS:
        operation_type = _OPERATION_TYPES[operation_id]
        operation_name = operation_id.split(".", 1)[1]
        result.append(
            DomainOperationDefinition(
                operation_id=operation_id,
                domain_id="domain:neurodivergence",
                version="1.0.0",
                name=operation_name.replace("_", " ").title(),
                description=(
                    "Evidence-organization and preparation operation for "
                    f"{operation_id}; never an autonomous diagnosis."
                ),
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
                    "phase": "10.53",
                    "domain": "neurodivergence",
                    "proposal_only": operation_id in _PROPOSAL_ONLY,
                    # Direct memory mutation is structurally impossible for
                    # every Neurodivergence operation (frozen design §12, §20).
                    "direct_memory_write": False,
                    # No operation reaches an external party autonomously.
                    "autonomous_external_action": False,
                    "diagnosis_authority": "none",
                },
            )
        )
    return tuple(result)
