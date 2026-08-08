"""Phase 10.20 — Health Domain Operations.

Twelve declarative operations.  No implementation is embedded here; an
operation without a provided implementation is registered as **UNAVAILABLE**
(fail-closed).  Sensitive operations (medical export, memory registration)
are approval-gated and never grant autonomy.
"""

from __future__ import annotations

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.enums import DomainOperationType
from cmm.domains.health.catalog import CANONICAL_HEALTH_OPERATION_IDS
from cmm.domains.operation_contracts import DomainOperationDefinition

HEALTH_OPERATION_IDS: tuple[str, ...] = CANONICAL_HEALTH_OPERATION_IDS

_OPERATION_TYPES = {
    "health.build_medical_timeline": DomainOperationType.ANALYSIS,
    "health.build_symptom_timeline": DomainOperationType.ANALYSIS,
    "health.compare_reports": DomainOperationType.ANALYSIS,
    "health.compare_test_results": DomainOperationType.ANALYSIS,
    "health.detect_open_medical_questions": DomainOperationType.ANALYSIS,
    "health.export_medical_context": DomainOperationType.EXTERNAL,
    "health.generate_medical_summary": DomainOperationType.PREPARATION,
    "health.prepare_medical_appointment": DomainOperationType.PREPARATION,
    "health.prepare_questions": DomainOperationType.PREPARATION,
    "health.register_symptom_update": DomainOperationType.MEMORY,
    "health.review_follow_up": DomainOperationType.ANALYSIS,
    "health.review_medication_changes": DomainOperationType.SENSITIVE,
}

_APPROVAL_REQUIRED = frozenset(
    {"health.export_medical_context", "health.register_symptom_update"}
)

_HIGHER_RISK = frozenset(
    {"health.export_medical_context", "health.register_symptom_update"}
)


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
    "health.build_medical_timeline": _schema(
        ("source_ids",), {"source_ids": _ids(1)}
    ),
    "health.build_symptom_timeline": _schema(
        ("source_ids",), {"source_ids": _ids(1)}
    ),
    "health.compare_reports": _schema(
        ("report_ids",), {"report_ids": _ids(2)}
    ),
    "health.compare_test_results": _schema(
        ("result_ids",), {"result_ids": _ids(2)}
    ),
    "health.detect_open_medical_questions": _schema(
        ("source_ids",), {"source_ids": _ids(1)}
    ),
    "health.export_medical_context": _schema(
        ("subject",),
        {"subject": {"type": "string"}, "purpose": {"type": "string"}},
    ),
    "health.generate_medical_summary": _schema(
        ("source_ids",), {"source_ids": _ids(1)}
    ),
    "health.prepare_medical_appointment": _schema(
        ("specialty",),
        {"specialty": {"type": "string"}, "topic": {"type": "string"}},
    ),
    "health.prepare_questions": _schema(
        ("topic",), {"topic": {"type": "string"}, "source_ids": _ID_ARRAY}
    ),
    "health.register_symptom_update": _schema(
        ("symptom",), {"symptom": {"type": "string"}, "started_at": {"type": "string"}}
    ),
    "health.review_follow_up": _schema(
        ("condition",), {"condition": {"type": "string"}}
    ),
    "health.review_medication_changes": _schema(
        ("medication",), {"medication": {"type": "string"}}
    ),
}

_OUTPUT_SCHEMAS = {
    "health.build_medical_timeline": _schema(
        ("events",), {"events": {"type": "array", "items": {"type": "object"}}}
    ),
    "health.build_symptom_timeline": _schema(
        ("events",), {"events": {"type": "array", "items": {"type": "object"}}}
    ),
    "health.compare_reports": _schema(
        ("comparison",), {"comparison": {"type": "object"}}
    ),
    "health.compare_test_results": _schema(
        ("comparison",), {"comparison": {"type": "object"}}
    ),
    "health.detect_open_medical_questions": _schema(
        ("questions",), {"questions": {"type": "array", "items": {"type": "string"}}}
    ),
    "health.export_medical_context": _schema(
        ("proposal", "binding"),
        {"proposal": {"type": "object"}, "binding": {"type": "object"}},
    ),
    "health.generate_medical_summary": _schema(
        ("summary",), {"summary": {"type": "string"}}
    ),
    "health.prepare_medical_appointment": _schema(
        ("preparation",), {"preparation": {"type": "object"}}
    ),
    "health.prepare_questions": _schema(
        ("questions",), {"questions": {"type": "array", "items": {"type": "string"}}}
    ),
    "health.register_symptom_update": _schema(
        ("proposal", "binding"),
        {"proposal": {"type": "object"}, "binding": {"type": "object"}},
    ),
    "health.review_follow_up": _schema(
        ("review",), {"review": {"type": "object"}}
    ),
    "health.review_medication_changes": _schema(
        ("review",), {"review": {"type": "object"}}
    ),
}


def build_health_operation_definitions() -> tuple[DomainOperationDefinition, ...]:
    """Build the twelve Health Domain operation definitions deterministically."""
    result = []
    for operation_id in HEALTH_OPERATION_IDS:
        operation_type = _OPERATION_TYPES[operation_id]
        operation_name = operation_id.split(".", 1)[1]
        requires_approval = operation_id in _APPROVAL_REQUIRED
        result.append(
            DomainOperationDefinition(
                operation_id=operation_id,
                domain_id="domain:health",
                version="1.0.0",
                name=operation_name.replace("_", " ").title(),
                description=f"Conservative structured operation for {operation_id}.",
                operation_type=operation_type,
                input_schema=_INPUT_SCHEMAS[operation_id],
                output_schema=_OUTPUT_SCHEMAS[operation_id],
                required_resources=(),
                required_permissions=(
                    ("resource.read", "memory.read")
                    if operation_type is DomainOperationType.READ
                    else ("resource.read",)
                ),
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
                    "phase": "10.20",
                    "domain": "health",
                    "proposal_only": requires_approval,
                },
            )
        )
    return tuple(result)


__all__ = ["HEALTH_OPERATION_IDS", "build_health_operation_definitions"]
