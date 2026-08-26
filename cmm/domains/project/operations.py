"""Phase 10.30 — Project Domain Operations.

Twenty declarative Project operations built on the shared ``DomainOperationDefinition`` contract:
- 7 generic project management operations
- 13 software-project specialization operations

All Project operations are declarations and UNAVAILABLE by default until an implementation
is explicitly injected into the operation registry.
No operation performs direct execution or commits.
"""

from __future__ import annotations

from typing import Any

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.enums import DomainOperationType
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.project.catalog import (
    CANONICAL_PROJECT_OPERATION_IDS,
    PROJECT_DOMAIN_ID,
    PROJECT_DOMAIN_VERSION,
)
from cmm.domains.project.rules import (
    evaluate_dependency_consistency,
    evaluate_milestone_consistency,
    evaluate_project_progress_evidence,
    evaluate_project_resource_constraints,
    evaluate_project_scope_consistency,
    evaluate_project_status_transition,
    evaluate_project_temporal_validity,
)

_OPERATION_TYPES: dict[str, DomainOperationType] = {
    # Generic (7)
    "project.create_project_overview": DomainOperationType.ANALYSIS,
    "project.review_status": DomainOperationType.ANALYSIS,
    "project.plan_milestones": DomainOperationType.PLANNING,
    "project.review_dependencies": DomainOperationType.ANALYSIS,
    "project.review_resources": DomainOperationType.ANALYSIS,
    "project.review_risks": DomainOperationType.ANALYSIS,
    "project.generate_progress_summary": DomainOperationType.ANALYSIS,
    # Software (13)
    "project.analyse_architecture": DomainOperationType.ANALYSIS,
    "project.detect_technical_debt": DomainOperationType.ANALYSIS,
    "project.compare_code_documentation": DomainOperationType.ANALYSIS,
    "project.detect_dead_code": DomainOperationType.ANALYSIS,
    "project.detect_duplication": DomainOperationType.ANALYSIS,
    "project.generate_adr": DomainOperationType.PLANNING,
    "project.create_implementation_plan": DomainOperationType.PLANNING,
    "project.modify_code": DomainOperationType.DESTRUCTIVE,
    "project.run_validation": DomainOperationType.ANALYSIS,
    "project.prepare_commit": DomainOperationType.PREPARATION,
    "project.review_change": DomainOperationType.ANALYSIS,
    "project.update_documentation": DomainOperationType.PREPARATION,
    "project.generate_release_notes": DomainOperationType.PREPARATION,
}

_REQUIRED_RESOURCES: dict[str, tuple[str, ...]] = {
    "project.create_project_overview": (
        "project.resource.project_brief",
        "project.resource.project_plan",
    ),
    "project.review_status": (
        "project.resource.status_report",
        "project.resource.milestone_record",
    ),
    "project.plan_milestones": (
        "project.resource.project_plan",
        "project.resource.milestone_record",
    ),
    "project.review_dependencies": (
        "project.resource.dependency_record",
        "project.resource.milestone_record",
    ),
    "project.review_resources": (
        "project.resource.resource_record",
        "project.resource.project_plan",
    ),
    "project.review_risks": (
        "project.resource.risk_record",
        "project.resource.project_brief",
    ),
    "project.generate_progress_summary": (
        "project.resource.status_report",
        "project.resource.milestone_record",
    ),
    "project.analyse_architecture": (
        "project.resource.source_code",
        "project.resource.architecture_document",
    ),
    "project.detect_technical_debt": (
        "project.resource.source_code",
        "project.resource.issue",
    ),
    "project.compare_code_documentation": (
        "project.resource.source_code",
        "project.resource.documentation",
    ),
    "project.detect_dead_code": ("project.resource.source_code",),
    "project.detect_duplication": ("project.resource.source_code",),
    "project.generate_adr": (
        "project.resource.architecture_document",
        "project.resource.decision_record",
    ),
    "project.create_implementation_plan": (
        "project.resource.project_plan",
        "project.resource.source_code",
    ),
    "project.modify_code": ("project.resource.source_code",),
    "project.run_validation": (
        "project.resource.test_result",
        "project.resource.validation_result",
    ),
    "project.prepare_commit": (
        "project.resource.git_history",
        "project.resource.validation_result",
    ),
    "project.review_change": (
        "project.resource.source_code",
        "project.resource.commit",
    ),
    "project.update_documentation": (
        "project.resource.documentation",
        "project.resource.source_code",
    ),
    "project.generate_release_notes": (
        "project.resource.git_history",
        "project.resource.roadmap",
    ),
}

_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    op_id: {
        "type": "object",
        "properties": {
            "parameters": {"type": "object"},
        },
        "additionalProperties": True,
    }
    for op_id in CANONICAL_PROJECT_OPERATION_IDS
}

_OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    op_id: {
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "result": {"type": "object"},
        },
        "required": ["status"],
        "additionalProperties": True,
    }
    for op_id in CANONICAL_PROJECT_OPERATION_IDS
}


def build_project_operation_definitions() -> tuple[DomainOperationDefinition, ...]:
    """Build all 20 Project Domain operation definitions deterministically."""
    definitions: list[DomainOperationDefinition] = []

    for op_id in CANONICAL_PROJECT_OPERATION_IDS:
        op_type = _OPERATION_TYPES[op_id]
        requires_approval = (
            op_id == "project.modify_code" or op_type is DomainOperationType.DESTRUCTIVE
        )
        risk_level = PolicyRiskLevel.HIGH if requires_approval else PolicyRiskLevel.LOW
        reversible = True
        rollback_policy = f"rollback.{op_id}" if reversible else None

        req_permissions = ["domain-permission:project:1.0.0"]
        if requires_approval:
            req_permissions.append("permission.file.modify")

        defn = DomainOperationDefinition(
            operation_id=op_id,
            domain_id=PROJECT_DOMAIN_ID,
            version=PROJECT_DOMAIN_VERSION,
            name=op_id.split(".", 1)[1],
            description=f"Project domain operation {op_id}",
            operation_type=op_type,
            input_schema=_INPUT_SCHEMAS[op_id],
            output_schema=_OUTPUT_SCHEMAS[op_id],
            required_resources=_REQUIRED_RESOURCES.get(op_id, ()),
            required_permissions=tuple(req_permissions),
            risk_level=risk_level,
            reversible=reversible,
            requires_approval=requires_approval,
            validation_policy_id=f"validation.{op_id}",
            rollback_policy_id=rollback_policy,
            enabled=True,
            metadata={"phase": "10.30"},
        )
        definitions.append(defn)

    return tuple(definitions)


# ── Pure Generic Result Builders ──────────────────────────────────────────────


def create_project_overview_result(
    *,
    project_id: str,
    title: str,
    objective: str,
    scope: dict[str, Any] | None = None,
    proposed_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build structured proposal for project overview."""
    scope_eval = evaluate_project_scope_consistency(scope, proposed_items)
    return {
        "project_id": project_id,
        "title": title,
        "objective": objective,
        "scope": scope or {},
        "scope_evaluation": scope_eval,
        "is_proposal": True,
    }


def review_project_status_result(
    *,
    project_id: str,
    status: str,
    milestones: list[dict[str, Any]] | None = None,
    current_status: str = "planned",
    evidence: Any = None,
) -> dict[str, Any]:
    """Build structured proposal for project status review."""
    transition_eval = evaluate_project_status_transition(
        current_status, status, evidence=evidence
    )
    ms_eval = evaluate_milestone_consistency(milestones)
    return {
        "project_id": project_id,
        "status": status,
        "transition_evaluation": transition_eval,
        "milestones_evaluation": ms_eval,
        "is_proposal": True,
    }


def plan_project_milestones_result(
    *,
    project_id: str,
    proposed_milestones: list[dict[str, Any]] | None = None,
    timeline: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build structured proposal for milestone planning."""
    ms_eval = evaluate_milestone_consistency(proposed_milestones)
    temporal_eval = evaluate_project_temporal_validity(proposed_milestones, timeline)
    return {
        "project_id": project_id,
        "proposed_milestones": proposed_milestones or [],
        "milestones_evaluation": ms_eval,
        "temporal_evaluation": temporal_eval,
        "is_proposal": True,
    }


def review_project_dependencies_result(
    *,
    dependencies: list[dict[str, Any]] | None = None,
    nodes: list[str] | None = None,
) -> dict[str, Any]:
    """Build structured proposal for project dependency review."""
    dep_eval = evaluate_dependency_consistency(dependencies, nodes)
    return {
        **dep_eval,
        "dependencies": dependencies or [],
        "is_proposal": True,
    }


def review_project_resources_result(
    *,
    resources: list[dict[str, Any]] | None = None,
    requirements: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build structured proposal for project resource review."""
    res_eval = evaluate_project_resource_constraints(resources, requirements)
    return {
        **res_eval,
        "resources": resources or [],
        "requirements": requirements or [],
        "is_proposal": True,
    }


def review_project_risks_result(
    *,
    risks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build structured proposal for project risk review."""
    return {
        "risks": risks or [],
        "is_proposal": True,
    }


def generate_project_progress_summary_result(
    *,
    project_id: str,
    progress_claims: list[dict[str, Any]] | None = None,
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build structured proposal for project progress summary."""
    prog_eval = evaluate_project_progress_evidence(progress_claims, evidence)
    return {
        "project_id": project_id,
        **prog_eval,
        "is_proposal": True,
    }


# ── Commit Readiness Evaluator (No Git Commit) ───────────────────────────────


def build_prepare_commit_readiness_result(
    *,
    change_id: str,
    validation_passed: bool,
    validation_reference: str | None = None,
    commit_gate_allowed: bool = False,
    approval_reference: str | None = None,
    authoritative_commit_reference: str | None = None,
) -> dict[str, Any]:
    """Evaluate commit readiness without executing external commits or fabricating commit hashes."""
    ready_for_approved_commit = (
        bool(validation_passed)
        and bool(commit_gate_allowed)
        and (approval_reference is not None)
    )
    committed = authoritative_commit_reference is not None

    result: dict[str, Any] = {
        "change_id": change_id,
        "validation_passed": validation_passed,
        "validation_reference": validation_reference,
        "commit_gate_allowed": commit_gate_allowed,
        "approval_reference": approval_reference,
        "ready_for_approved_commit": ready_for_approved_commit,
        "committed": committed,
    }
    if authoritative_commit_reference is not None:
        result["authoritative_commit_reference"] = authoritative_commit_reference

    return result


__all__ = [
    "CANONICAL_PROJECT_OPERATION_IDS",
    "build_prepare_commit_readiness_result",
    "build_project_operation_definitions",
    "create_project_overview_result",
    "generate_project_progress_summary_result",
    "plan_project_milestones_result",
    "review_project_dependencies_result",
    "review_project_resources_result",
    "review_project_risks_result",
    "review_project_status_result",
]
