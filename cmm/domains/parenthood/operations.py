"""Phase 10.27 — Parenthood Domain Operations.

Twenty declarative parenthood operations built on the shared
``DomainOperationDefinition`` contract (9 journey + 11 child operations).
All operations are internal analysis, planning, or preparation operations:
no operation mutates external state, contacts providers, pays funds,
commits to legal or medical decisions autonomously, or writes to memory directly.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.enums import DomainOperationType
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.parenthood.catalog import (
    CANONICAL_PARENTHOOD_OPERATION_IDS,
)

_OPERATION_TYPES: dict[str, DomainOperationType] = {
    # Journey
    "parenthood.journey.build_timeline": DomainOperationType.PLANNING,
    "parenthood.journey.compare_pathways": DomainOperationType.ANALYSIS,
    "parenthood.journey.review_requirements": DomainOperationType.ANALYSIS,
    "parenthood.journey.review_financial_scenarios": DomainOperationType.ANALYSIS,
    "parenthood.journey.prepare_questions": DomainOperationType.PREPARATION,
    "parenthood.journey.track_decisions": DomainOperationType.PLANNING,
    "parenthood.journey.update_plan": DomainOperationType.PLANNING,
    "parenthood.journey.generate_documentation_checklist": DomainOperationType.PREPARATION,
    "parenthood.journey.review_risks": DomainOperationType.ANALYSIS,
    # Child
    "parenthood.child.review_needs": DomainOperationType.ANALYSIS,
    "parenthood.child.review_developmental_stage": DomainOperationType.ANALYSIS,
    "parenthood.child.plan_routines": DomainOperationType.PLANNING,
    "parenthood.child.prepare_parental_decision": DomainOperationType.PREPARATION,
    "parenthood.child.review_education_plan": DomainOperationType.ANALYSIS,
    "parenthood.child.review_family_context": DomainOperationType.ANALYSIS,
    "parenthood.child.track_milestones": DomainOperationType.PLANNING,
    "parenthood.child.prepare_questions": DomainOperationType.PREPARATION,
    "parenthood.child.track_decisions": DomainOperationType.PLANNING,
    "parenthood.child.update_parenting_plan": DomainOperationType.PLANNING,
    "parenthood.child.review_risks_and_needs": DomainOperationType.ANALYSIS,
}

_REQUIRED_RESOURCES: dict[str, tuple[str, ...]] = {
    # Journey
    "parenthood.journey.build_timeline": ("parenthood.resource.life_plan",),
    "parenthood.journey.compare_pathways": (
        "parenthood.resource.life_plan",
        "parenthood.resource.jurisdiction_information",
    ),
    "parenthood.journey.review_requirements": (
        "parenthood.resource.legal_document",
        "parenthood.resource.jurisdiction_information",
    ),
    "parenthood.journey.review_financial_scenarios": (
        "parenthood.resource.financial_plan",
    ),
    "parenthood.journey.prepare_questions": (
        "parenthood.resource.provider_information",
    ),
    "parenthood.journey.track_decisions": ("parenthood.resource.decision",),
    "parenthood.journey.update_plan": ("parenthood.resource.life_plan",),
    "parenthood.journey.generate_documentation_checklist": (
        "parenthood.resource.legal_document",
    ),
    "parenthood.journey.review_risks": ("parenthood.resource.life_plan",),
    # Child
    "parenthood.child.review_needs": (
        "parenthood.resource.parenting_note",
        "parenthood.resource.child_development_resource",
    ),
    "parenthood.child.review_developmental_stage": (
        "parenthood.resource.child_development_resource",
    ),
    "parenthood.child.plan_routines": (
        "parenthood.resource.schedule",
        "parenthood.resource.parenting_note",
    ),
    "parenthood.child.prepare_parental_decision": (
        "parenthood.resource.parental_decision",
    ),
    "parenthood.child.review_education_plan": (
        "parenthood.resource.education_document",
        "parenthood.resource.school_information",
    ),
    "parenthood.child.review_family_context": ("parenthood.resource.parenting_note",),
    "parenthood.child.track_milestones": (
        "parenthood.resource.child_development_resource",
    ),
    "parenthood.child.prepare_questions": ("parenthood.resource.parenting_note",),
    "parenthood.child.track_decisions": ("parenthood.resource.parental_decision",),
    "parenthood.child.update_parenting_plan": (
        "parenthood.resource.parenting_note",
        "parenthood.resource.schedule",
    ),
    "parenthood.child.review_risks_and_needs": (
        "parenthood.resource.parenting_note",
        "parenthood.resource.health_summary",
    ),
}

_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    op_id: {
        "type": "object",
        "properties": {
            "scope": {"type": "string"},
            "child_id": {"type": "string"} if "child" in op_id else {"type": "null"},
            "parameters": {"type": "object"},
        },
        "required": ["scope"] + (["child_id"] if "child" in op_id else []),
    }
    for op_id in CANONICAL_PARENTHOOD_OPERATION_IDS
}

_OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    op_id: {
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "is_proposal": {"type": "boolean"},
            "findings": {"type": "array"},
            "summary": {"type": "string"},
            "timestamp": {"type": "string"},
        },
        "required": ["status", "is_proposal"],
    }
    for op_id in CANONICAL_PARENTHOOD_OPERATION_IDS
}


def build_parenthood_operation_definitions() -> tuple[DomainOperationDefinition, ...]:
    """Build all twenty canonical Parenthood Domain operation definitions deterministically."""
    result = []
    for op_id in CANONICAL_PARENTHOOD_OPERATION_IDS:
        op_name = op_id.split(".", 1)[1].replace("_", " ").title()
        result.append(
            DomainOperationDefinition(
                operation_id=op_id,
                domain_id="domain:parenthood",
                version="1.0.0",
                name=op_name,
                description=f"Parenthood reasoning operation for {op_id}.",
                operation_type=_OPERATION_TYPES[op_id],
                risk_level=PolicyRiskLevel.LOW,
                required_resources=_REQUIRED_RESOURCES[op_id],
                input_schema=_INPUT_SCHEMAS[op_id],
                output_schema=_OUTPUT_SCHEMAS[op_id],
                metadata={
                    "phase": "10.27",
                    "proposal_only": True,
                    "no_external_mutation": True,
                },
            )
        )
    return tuple(result)


# ── Result Helpers (pure, deterministic) ──────────────────────────────────────


def compare_pathways_result(
    *,
    pathways: Sequence[str],
    criteria: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare multiple family-building pathways preserving uncertainty and non-adoption."""
    criteria_dict = dict(criteria or {})
    return {
        "status": "completed",
        "is_proposal": True,
        "pathways": list(pathways),
        "criteria": criteria_dict,
        "cost_uncertainty_preserved": True,
        "has_autonomous_decision": False,
        "comparison_matrix": {
            p: {
                "feasibility": "exploratory",
                "cost_range": criteria_dict.get("budget_range", (50000, 100000)),
            }
            for p in pathways
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def build_timeline_result(
    *,
    pathway: str,
    start_date: str | None = None,
) -> dict[str, Any]:
    """Build a milestone timeline proposal for a pathway."""
    return {
        "status": "completed",
        "is_proposal": True,
        "pathway": pathway,
        "estimated_start": start_date or "flexible",
        "milestones": [
            {"milestone": "Medical preparation & testing", "estimated_month": 1},
            {"milestone": "Legal & agency matching", "estimated_month": 3},
            {
                "milestone": "Embryo transfer / matching confirmation",
                "estimated_month": 6,
            },
            {
                "milestone": "Pregnancy / final administrative steps",
                "estimated_month": 9,
            },
            {
                "milestone": "Birth transition & civil registration",
                "estimated_month": 15,
            },
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def review_developmental_stage_result(
    *,
    child_id: str,
    stage: str,
    observations: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Review developmental stage with non-diagnostic normal variation invariant."""
    return {
        "status": "completed",
        "is_proposal": True,
        "child_id": child_id,
        "stage": stage,
        "observations": list(observations or []),
        "is_diagnostic": False,
        "normal_variation_confirmed": True,
        "guidance": f"Developmental expectations for {stage} stage provided without clinical labeling.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def plan_routines_result(
    *,
    child_id: str,
    stage: str,
    routines: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Plan routines for a child workspace."""
    return {
        "status": "completed",
        "is_proposal": True,
        "child_id": child_id,
        "stage": stage,
        "routines": dict(routines or {}),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def prepare_parental_decision_result(
    *,
    child_id: str,
    topic: str,
    options: Sequence[str],
    criteria: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Prepare a parental decision as a proposal requiring explicit user confirmation."""
    return {
        "status": "completed",
        "is_proposal": True,
        "child_id": child_id,
        "topic": topic,
        "options": list(options),
        "criteria": list(criteria or []),
        "decision_status": "proposed",
        "requires_explicit_user_adoption": True,
        "adopted_by_system": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


__all__ = [
    "build_parenthood_operation_definitions",
    "build_timeline_result",
    "compare_pathways_result",
    "plan_routines_result",
    "prepare_parental_decision_result",
    "review_developmental_stage_result",
]
