"""Phase 10.19 — General Domain Operations."""

from __future__ import annotations

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.enums import DomainOperationType
from cmm.domains.general.catalog import CANONICAL_GENERAL_OPERATION_IDS
from cmm.domains.operation_contracts import DomainOperationDefinition

GENERAL_OPERATION_IDS: tuple[str, ...] = CANONICAL_GENERAL_OPERATION_IDS

_OPERATION_TYPES = {
    "general.create_summary": DomainOperationType.ANALYSIS,
    "general.build_timeline": DomainOperationType.ANALYSIS,
    "general.compare_items": DomainOperationType.ANALYSIS,
    "general.prepare_questions": DomainOperationType.PREPARATION,
    "general.create_task": DomainOperationType.PLANNING,
    "general.update_goal": DomainOperationType.PLANNING,
    "general.generate_report": DomainOperationType.PREPARATION,
    "general.search_knowledge": DomainOperationType.READ,
}

_APPROVAL_REQUIRED = frozenset({"general.create_task", "general.update_goal"})

# ── Per-operation JSON schemas ─────────────────────────────────────────────────
#
# Every operation declares its own input/output schema so the shape of each
# request and result is explicit and validated.  No shared bare schema.

_INPUT_SCHEMAS = {
    "general.create_summary": {
        "type": "object",
        "required": ["source_ids"],
        "properties": {
            "source_ids": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "focus": {"type": "string"},
        },
        "additionalProperties": False,
    },
    "general.build_timeline": {
        "type": "object",
        "required": ["source_ids"],
        "properties": {
            "source_ids": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "start": {"type": "string"},
            "end": {"type": "string"},
        },
        "additionalProperties": False,
    },
    "general.compare_items": {
        "type": "object",
        "required": ["item_ids"],
        "properties": {
            "item_ids": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
            },
            "criteria": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": False,
    },
    "general.prepare_questions": {
        "type": "object",
        "required": ["topic"],
        "properties": {
            "topic": {"type": "string"},
            "source_ids": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": False,
    },
    "general.create_task": {
        "type": "object",
        "required": ["title"],
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "due_at": {"type": "string"},
        },
        "additionalProperties": False,
    },
    "general.update_goal": {
        "type": "object",
        "required": ["goal_id"],
        "properties": {
            "goal_id": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"},
        },
        "additionalProperties": False,
    },
    "general.generate_report": {
        "type": "object",
        "required": ["source_ids"],
        "properties": {
            "source_ids": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "title": {"type": "string"},
        },
        "additionalProperties": False,
    },
    "general.search_knowledge": {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string"},
            "resource_ids": {"type": "array", "items": {"type": "string"}},
            "limit": {"type": "integer", "minimum": 1},
        },
        "additionalProperties": False,
    },
}

_OUTPUT_SCHEMAS = {
    "general.create_summary": {
        "type": "object",
        "required": ["summary"],
        "properties": {
            "summary": {"type": "string"},
            "source_ids": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": False,
    },
    "general.build_timeline": {
        "type": "object",
        "required": ["events"],
        "properties": {
            "events": {"type": "array", "items": {"type": "object"}},
        },
        "additionalProperties": False,
    },
    "general.compare_items": {
        "type": "object",
        "required": ["comparison"],
        "properties": {
            "comparison": {"type": "object"},
        },
        "additionalProperties": False,
    },
    "general.prepare_questions": {
        "type": "object",
        "required": ["questions"],
        "properties": {
            "questions": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": False,
    },
    "general.create_task": {
        "type": "object",
        "required": ["proposal", "binding"],
        "properties": {
            "proposal": {"type": "object"},
            "binding": {"type": "object"},
        },
        "additionalProperties": False,
    },
    "general.update_goal": {
        "type": "object",
        "required": ["proposal", "binding"],
        "properties": {
            "proposal": {"type": "object"},
            "binding": {"type": "object"},
        },
        "additionalProperties": False,
    },
    "general.generate_report": {
        "type": "object",
        "required": ["report"],
        "properties": {
            "report": {"type": "string"},
        },
        "additionalProperties": False,
    },
    "general.search_knowledge": {
        "type": "object",
        "required": ["results"],
        "properties": {
            "results": {"type": "array", "items": {"type": "object"}},
        },
        "additionalProperties": False,
    },
}


def build_general_operation_definitions() -> tuple[DomainOperationDefinition, ...]:
    """Build the eight General Domain operation definitions deterministically."""
    result = []
    for operation_id in GENERAL_OPERATION_IDS:
        operation_type = _OPERATION_TYPES[operation_id]
        operation_name = operation_id.split(".", 1)[1]
        requires_approval = operation_id in _APPROVAL_REQUIRED
        # Resource dependencies are selected dynamically from the request/memory
        # view.  required_resources has AND semantics and cannot represent
        # alternative sources, so it stays empty by design.
        result.append(
            DomainOperationDefinition(
                operation_id=operation_id,
                domain_id="domain:general",
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
                risk_level=PolicyRiskLevel.LOW,
                reversible=False,
                requires_approval=requires_approval,
                validation_policy_id=None,
                rollback_policy_id=None,
                enabled=True,
                metadata={
                    "phase": "10.19",
                    "domain": "general",
                    "proposal_only": operation_id in _APPROVAL_REQUIRED,
                },
            )
        )
    return tuple(result)


__all__ = ["GENERAL_OPERATION_IDS", "build_general_operation_definitions"]