from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.contracts import WorkflowNode


def _definition(workflow_id: str, domain_id: str, name: str, steps: tuple[str, ...]) -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(workflow_id, domain_id, "1.0.0", name, nodes=tuple(WorkflowNode(step, "complete" if i == len(steps) - 1 else "load_resource", step, dependencies=(steps[i - 1],) if i else ()) for i, step in enumerate(steps)))


def initial_domain_workflows() -> tuple[DomainWorkflowDefinition, ...]:
    return (
        _definition("health.medical_follow_up", "domain:health", "Medical follow-up", ("load_medical_resources", "prepare_consultation_summary", "complete")),
        _definition("university.semester_planning", "domain:university", "Semester planning", ("load_subjects", "generate_scenarios", "complete")),
        _definition("relationships.timeline_analysis", "domain:relationships", "Timeline analysis", ("load_events", "generate_hypotheses", "complete")),
        _definition("project.architecture_review", "domain:project", "Architecture review", ("load_repository_resources", "generate_findings", "complete")),
    )
