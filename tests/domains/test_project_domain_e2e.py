"""Phase 10.30 — Project Domain Generic End-to-End Acceptance Tests.

Tests the full lifecycle of generic (non-software) personal and professional projects:
- project setup, status review, milestone planning, and periodic review
- strictly generic context: software rules stay inactive
- all operations produce proposals (is_proposal=True)
- memory proposals require confirmation
- traces are assembled deterministically with reference-only links
- presentation layer marks proposals and preserves uncertainty
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive.reasoning_rule_contracts import (
    ReasoningRuleContext,
    ReasoningRuleResultStatus,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.project.bootstrap import build_standard_project_domain_bootstrap
from cmm.domains.project.catalog import PROJECT_DOMAIN_ID
from cmm.domains.project.memory import (
    build_project_memory_binding,
    build_project_memory_proposal,
    build_project_memory_view_request,
    validate_project_memory_proposal_content,
)
from cmm.domains.project.operations import (
    create_project_overview_result,
    generate_project_progress_summary_result,
    plan_project_milestones_result,
    review_project_dependencies_result,
    review_project_resources_result,
    review_project_status_result,
)
from cmm.domains.project.presentation import present_project_result
from cmm.domains.project.profile import (
    SOFTWARE_PROJECT_RULE_IDS,
    project_software_capability_active,
)
from cmm.domains.project.rules import build_project_rules
from cmm.domains.project.trace import (
    assemble_project_trace,
    build_project_trace_reference,
)
from cmm.domains.trace_contracts import DomainTraceReferenceKind, DomainTraceStatus


def test_generic_project_full_lifecycle_e2e() -> None:
    # 1. Bootstrap standard system
    bootstrap = build_standard_project_domain_bootstrap()
    assert bootstrap.domain_registry.get(PROJECT_DOMAIN_ID) is not None

    # 2. Verify software capability is INACTIVE for generic project context
    software_active = project_software_capability_active(
        workflow_id="project.project_setup",
        operation_id="project.create_project_overview",
        resource_ids=(
            "project.resource.project_brief",
            "project.resource.project_plan",
        ),
        capabilities=(),
        repository_backed=False,
    )
    assert software_active is False

    # 3. Rules in generic context: software rules produce inactive/no-op trace entries
    rules = build_project_rules()
    generic_context = ReasoningRuleContext(
        reasoning_id="reasoning:generic:e2e:1",
        timestamp=datetime.now(timezone.utc),
        metadata={"workflow_id": "project.project_setup"},
    )
    for rule in rules:
        if rule.definition.id in SOFTWARE_PROJECT_RULE_IDS:
            res = rule.evaluate(generic_context)
            assert res.status == ReasoningRuleResultStatus.APPLIED
            assert any(
                t.code == "SOFTWARE_CAPABILITY_INACTIVE" for t in res.trace_entries
            )

    # 4. Phase 1: Project Setup
    overview_result = create_project_overview_result(
        project_id="proj:relocation:2026",
        title="Family Relocation to Munich",
        objective="Execute relocation timeline and logistics",
        scope={
            "objective": "Execute relocation timeline and logistics",
            "deliverables": ["housing", "school_registration", "moving_truck"],
            "exclusions": ["buying_property"],
        },
        proposed_items=[
            {"id": "item_1", "deliverable": "housing", "description": "find apartment"},
        ],
    )
    assert overview_result["is_proposal"] is True
    assert overview_result["scope_evaluation"]["valid"] is True

    # 5. Phase 2: Milestone & Dependency Planning
    milestones = [
        {
            "id": "m1",
            "title": "Secure Lease",
            "status": "completed",
            "evidence": ["lease_contract_signed"],
            "target_date": "2026-07-01T00:00:00Z",
        },
        {
            "id": "m2",
            "title": "School Enrollment",
            "status": "active",
            "depends_on": "m1",
            "target_date": "2026-08-01T00:00:00Z",
        },
        {
            "id": "m3",
            "title": "Moving Day",
            "status": "planned",
            "depends_on": "m2",
            "target_date": "2026-08-15T00:00:00Z",
        },
    ]
    deps = [
        {"source": "m1", "target": "m2"},
        {"source": "m2", "target": "m3"},
    ]
    plan_res = plan_project_milestones_result(
        project_id="proj:relocation:2026",
        proposed_milestones=milestones,
    )
    assert plan_res["is_proposal"] is True
    assert plan_res["milestones_evaluation"]["valid"] is True
    assert plan_res["temporal_evaluation"]["valid"] is True

    dep_res = review_project_dependencies_result(dependencies=deps)
    assert dep_res["valid"] is True
    assert len(dep_res["cycles"]) == 0

    # 6. Phase 3: Status Review
    status_res = review_project_status_result(
        project_id="proj:relocation:2026",
        status="active",
        milestones=milestones,
        current_status="planned",
    )
    assert status_res["status"] == "active"
    assert status_res["transition_evaluation"]["allowed"] is True

    # 7. Phase 4: Resource & Progress Review
    resources = [
        {"kind": "budget_eur", "available": 10000, "unit": "EUR"},
        {"kind": "time_weeks", "available": 12, "unit": "weeks"},
    ]
    reqs = [
        {"resource": "budget_eur", "required": 6500},
        {"resource": "time_weeks", "required": 8},
    ]
    res_review = review_project_resources_result(resources=resources, requirements=reqs)
    assert res_review["feasible"] is True

    prog_summary = generate_project_progress_summary_result(
        project_id="proj:relocation:2026",
        progress_claims=[
            {"id": "c1", "claim": "Lease secured", "deliverable": "housing"}
        ],
        evidence=[{"deliverable": "housing", "status": "verified"}],
    )
    assert prog_summary["supported"] is True
    assert prog_summary["is_proposal"] is True

    # 8. Memory Proposal & Binding (Proposal-Only)
    proposal_content = {
        "kind": "milestone_record",
        "status": "decision",
        "is_confirmed": True,
        "summary": "Lease secured for Munich apartment",
    }
    val_prop = validate_project_memory_proposal_content(proposal_content)
    assert val_prop["is_valid"] is True

    mem_proposal = build_project_memory_proposal(
        proposal_id="prop:relocation:m1",
        affected_reference_ids=("ref:project:proj:relocation:2026",),
    )
    assert mem_proposal.requires_confirmation is True

    # Memory view request
    mem_view_req = build_project_memory_view_request(request_id="req:mem:1")
    assert mem_view_req.primary_domain == "domain:project"

    # Fake resolved view for binding test
    from dataclasses import dataclass

    @dataclass
    class _ResolvedView:
        view_id: str = f"view:project:1:{'0' * 12}"
        primary_domain: str = "domain:project"
        content_digest: str = "0" * 64

    binding = build_project_memory_binding(
        proposal=mem_proposal,
        view=_ResolvedView(),  # type: ignore[arg-type]
        trace_id="trace:generic:e2e:1",
    )
    assert binding.trace_id == "trace:generic:e2e:1"
    assert binding.memory_proposal_ids == ("prop:relocation:m1",)

    # 9. Trace Assembly
    now = datetime.now(timezone.utc)
    trace_ref = build_project_trace_reference(
        ref_id="rule:project.scope_consistency:1.0.0",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )
    trace = assemble_project_trace(
        request_id="req:trace:1",
        resolution_context_id="ctx:generic:1",
        resolution_result_id="res_res:generic:1",
        composition_id="comp:generic:1",
        domain_result_id="res:project:relocation:1",
        references=(trace_ref,),
        started_at=now,
        completed_at=now,
    )
    assert trace.primary_domain == DomainId.from_str(PROJECT_DOMAIN_ID)
    assert trace.status == DomainTraceStatus.COMPLETED

    # 10. Presentation
    presented = present_project_result(prog_summary)
    assert presented["domain_display_name"] == "Project"
    assert presented["proposals_distinguished"] is True
    assert presented["uncertainty_preserved"] is True
    assert presented["is_proposal"] is True
