"""Phase 10.30 — Project Domain Workflows.

Twelve declarative Project workflows built on shared ``DomainWorkflowDefinition``:
- 4 generic project workflows
- 8 software-project specialization workflows

Safety ordering: ``load -> profile -> reason`` is a strict dependency chain.
A terminal ``COMPLETE`` node always transitively depends on a ``VALIDATE`` node.
"""

from __future__ import annotations

from cmm.domains.project.catalog import (
    CANONICAL_PROJECT_WORKFLOW_IDS,
    PROJECT_DOMAIN_ID,
    PROJECT_DOMAIN_VERSION,
)
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowNodeType

PROJECT_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_PROJECT_WORKFLOW_IDS
GENERIC_PROJECT_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_PROJECT_WORKFLOW_IDS[:4]
SOFTWARE_PROJECT_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_PROJECT_WORKFLOW_IDS[4:]

PROJECT_WORKFLOW_NAMES_BY_ID: dict[str, str] = {
    # Generic (4)
    "project.project_setup": "Project Setup",
    "project.status_review": "Status Review",
    "project.milestone_dependency_review": "Milestone & Dependency Review",
    "project.periodic_project_review": "Periodic Project Review",
    # Software (8)
    "project.architecture_review": "Architecture Review",
    "project.feature_implementation": "Feature Implementation",
    "project.bug_resolution": "Bug Resolution",
    "project.technical_debt_review": "Technical Debt Review",
    "project.documentation_synchronisation": "Documentation Synchronisation",
    "project.refactor": "Refactor",
    "project.release_preparation": "Release Preparation",
    "project.self_development": "Self Development",
}


def _node(
    node_id: str,
    node_type: WorkflowNodeType,
    name: str,
    *,
    dependencies: tuple[str, ...] = (),
    operation_id: str | None = None,
    approval_gate: str | None = None,
    wait_condition: dict | None = None,
    metadata: dict | None = None,
) -> WorkflowNode:
    return WorkflowNode(
        node_id=node_id,
        node_type=node_type,
        name=name,
        dependencies=dependencies,
        operation_id=operation_id,
        operation_version="1.0.0" if operation_id else None,
        approval_gate=approval_gate,
        wait_condition=wait_condition,
        metadata=metadata or {},
    )


def _ordered_prefix() -> tuple[WorkflowNode, ...]:
    """Strict safety prefix: load -> profile -> reason."""
    return (
        _node("load", WorkflowNodeType.LOAD_RESOURCE, "LoadProjectSources"),
        _node(
            "profile",
            WorkflowNodeType.APPLY_PROFILE,
            "ApplyProjectProfile",
            dependencies=("load",),
        ),
        _node(
            "reason",
            WorkflowNodeType.REASON,
            "ApplyProjectRules",
            dependencies=("profile",),
        ),
    )


def _workflow(
    workflow_id: str,
    *,
    description: str,
    purpose: str,
    core_nodes: tuple[WorkflowNode, ...],
    approval_gates: tuple[str, ...] = (),
    extra_metadata: dict | None = None,
) -> DomainWorkflowDefinition:
    prefix = _ordered_prefix()
    last_core_id = core_nodes[-1].node_id if core_nodes else "reason"

    suffix = (
        _node("validate", WorkflowNodeType.VALIDATE, "ValidateProjectWorkflow", dependencies=(last_core_id,)),
        _node("complete", WorkflowNodeType.COMPLETE, "CompleteProjectWorkflow", dependencies=("validate",)),
    )

    all_nodes = (*prefix, *core_nodes, *suffix)
    meta = {"phase": "10.30"}
    if extra_metadata:
        meta.update(extra_metadata)

    return DomainWorkflowDefinition(
        workflow_id=workflow_id,
        domain_id=PROJECT_DOMAIN_ID,
        version=PROJECT_DOMAIN_VERSION,
        name=PROJECT_WORKFLOW_NAMES_BY_ID.get(workflow_id, workflow_id),
        description=description,
        nodes=all_nodes,
        required_permissions=("domain-permission:project:1.0.0",),
        approval_gates=approval_gates,
        purpose=purpose,
        metadata=meta,
    )


def build_project_workflow_definitions() -> tuple[DomainWorkflowDefinition, ...]:
    """Build all 12 Project Domain workflow definitions deterministically in canonical order."""
    wfs: list[DomainWorkflowDefinition] = []

    # 1. project.project_setup (Generic)
    wfs.append(
        _workflow(
            "project.project_setup",
            description="Initialize project overview, scope, and objectives",
            purpose="project_initialization",
            core_nodes=(
                _node(
                    "overview",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "CreateProjectOverview",
                    dependencies=("reason",),
                    operation_id="project.create_project_overview",
                ),
            ),
        )
    )

    # 2. project.status_review (Generic)
    wfs.append(
        _workflow(
            "project.status_review",
            description="Review project status, milestones, and blockers",
            purpose="status_tracking",
            core_nodes=(
                _node(
                    "review_status",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "ReviewProjectStatus",
                    dependencies=("reason",),
                    operation_id="project.review_status",
                ),
            ),
        )
    )

    # 3. project.milestone_dependency_review (Generic)
    wfs.append(
        _workflow(
            "project.milestone_dependency_review",
            description="Review milestones, dependencies, cycle detection, and resource constraints",
            purpose="milestone_dependency_review",
            core_nodes=(
                _node(
                    "plan_milestones",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "PlanMilestones",
                    dependencies=("reason",),
                    operation_id="project.plan_milestones",
                ),
                _node(
                    "review_dependencies",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "ReviewDependencies",
                    dependencies=("plan_milestones",),
                    operation_id="project.review_dependencies",
                ),
            ),
        )
    )

    # 4. project.periodic_project_review (Generic)
    wfs.append(
        _workflow(
            "project.periodic_project_review",
            description="Periodic review comparing current and prior state, risks, and progress summary",
            purpose="periodic_review",
            core_nodes=(
                _node(
                    "review_risks",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "ReviewRisks",
                    dependencies=("reason",),
                    operation_id="project.review_risks",
                ),
                _node(
                    "progress_summary",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "GenerateProgressSummary",
                    dependencies=("review_risks",),
                    operation_id="project.generate_progress_summary",
                ),
            ),
        )
    )

    # 5. project.architecture_review (Software)
    wfs.append(
        _workflow(
            "project.architecture_review",
            description="Analyse codebase architecture and contractual structural boundaries",
            purpose="architecture_review",
            core_nodes=(
                _node(
                    "analyse_arch",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "AnalyseArchitecture",
                    dependencies=("reason",),
                    operation_id="project.analyse_architecture",
                ),
            ),
        )
    )

    # 6. project.feature_implementation (Software)
    wfs.append(
        _workflow(
            "project.feature_implementation",
            description="Plan feature implementation and apply supervised code modifications under approval gate",
            purpose="feature_implementation",
            core_nodes=(
                _node(
                    "create_plan",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "CreateImplementationPlan",
                    dependencies=("reason",),
                    operation_id="project.create_implementation_plan",
                ),
                _node(
                    "modify_code",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "ModifyCode",
                    dependencies=("create_plan",),
                    operation_id="project.modify_code",
                    approval_gate="approval.file.modify",
                ),
            ),
            approval_gates=("approval.file.modify",),
        )
    )

    # 7. project.bug_resolution (Software)
    wfs.append(
        _workflow(
            "project.bug_resolution",
            description="Diagnose bug, plan fix, apply approved modification, and run validation",
            purpose="bug_resolution",
            core_nodes=(
                _node(
                    "create_plan",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "CreateImplementationPlan",
                    dependencies=("reason",),
                    operation_id="project.create_implementation_plan",
                ),
                _node(
                    "modify_code",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "ModifyCode",
                    dependencies=("create_plan",),
                    operation_id="project.modify_code",
                    approval_gate="approval.file.modify",
                ),
                _node(
                    "run_validation",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "RunValidation",
                    dependencies=("modify_code",),
                    operation_id="project.run_validation",
                ),
            ),
            approval_gates=("approval.file.modify",),
        )
    )

    # 8. project.technical_debt_review (Software)
    wfs.append(
        _workflow(
            "project.technical_debt_review",
            description="Detect technical debt, dead code, and duplication",
            purpose="technical_debt_review",
            core_nodes=(
                _node(
                    "detect_debt",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "DetectTechnicalDebt",
                    dependencies=("reason",),
                    operation_id="project.detect_technical_debt",
                ),
                _node(
                    "detect_dead_code",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "DetectDeadCode",
                    dependencies=("detect_debt",),
                    operation_id="project.detect_dead_code",
                ),
            ),
        )
    )

    # 9. project.documentation_synchronisation (Software)
    wfs.append(
        _workflow(
            "project.documentation_synchronisation",
            description="Compare code and documentation, and generate synchronization proposals",
            purpose="documentation_synchronisation",
            core_nodes=(
                _node(
                    "compare_doc",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "CompareCodeDoc",
                    dependencies=("reason",),
                    operation_id="project.compare_code_documentation",
                ),
                _node(
                    "update_doc",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "UpdateDocumentation",
                    dependencies=("compare_doc",),
                    operation_id="project.update_documentation",
                ),
            ),
        )
    )

    # 10. project.refactor (Software)
    wfs.append(
        _workflow(
            "project.refactor",
            description="Structure-preserving refactoring under validation and approval gates",
            purpose="refactor",
            core_nodes=(
                _node(
                    "create_plan",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "CreateImplementationPlan",
                    dependencies=("reason",),
                    operation_id="project.create_implementation_plan",
                ),
                _node(
                    "modify_code",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "ModifyCode",
                    dependencies=("create_plan",),
                    operation_id="project.modify_code",
                    approval_gate="approval.file.modify",
                ),
                _node(
                    "run_validation",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "RunValidation",
                    dependencies=("modify_code",),
                    operation_id="project.run_validation",
                ),
            ),
            approval_gates=("approval.file.modify",),
        )
    )

    # 11. project.release_preparation (Software)
    wfs.append(
        _workflow(
            "project.release_preparation",
            description="Prepare release notes and evaluate release readiness",
            purpose="release_preparation",
            core_nodes=(
                _node(
                    "release_notes",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "GenerateReleaseNotes",
                    dependencies=("reason",),
                    operation_id="project.generate_release_notes",
                ),
            ),
        )
    )

    # 12. project.self_development (Software)
    wfs.append(
        _workflow(
            "project.self_development",
            description="Autonomous self-development lifecycle: architecture -> validation -> commit readiness",
            purpose="self_development",
            core_nodes=(
                _node(
                    "arch_analysis",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "AnalyseArchitecture",
                    dependencies=("reason",),
                    operation_id="project.analyse_architecture",
                ),
                _node(
                    "run_validation",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "RunValidation",
                    dependencies=("arch_analysis",),
                    operation_id="project.run_validation",
                ),
                _node(
                    "prepare_commit",
                    WorkflowNodeType.EXECUTE_OPERATION,
                    "PrepareCommit",
                    dependencies=("run_validation",),
                    operation_id="project.prepare_commit",
                ),
            ),
        )
    )

    return tuple(wfs)


__all__ = [
    "GENERIC_PROJECT_WORKFLOW_IDS",
    "PROJECT_WORKFLOW_IDS",
    "PROJECT_WORKFLOW_NAMES_BY_ID",
    "SOFTWARE_PROJECT_WORKFLOW_IDS",
    "build_project_workflow_definitions",
]
