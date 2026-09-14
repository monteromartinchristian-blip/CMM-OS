"""Phase 10.30 — Project Domain Trace Integration Tests."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.identifiers import DomainId
from cmm.domains.project.catalog import PROJECT_DOMAIN_ID
from cmm.domains.project.trace import (
    assemble_project_trace,
    build_project_trace_contribution,
    build_project_trace_reference,
    build_supporting_trace_contribution,
)
from cmm.domains.trace_contracts import (
    DomainTrace,
    DomainTraceContribution,
    DomainTraceReference,
    DomainTraceReferenceKind,
    DomainTraceRole,
    DomainTraceStatus,
)


def test_build_project_trace_reference() -> None:
    ref = build_project_trace_reference(
        ref_id="rule:project.scope_consistency:1.0.0",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )
    assert isinstance(ref, DomainTraceReference)
    assert ref.domain_id == DomainId.from_str(PROJECT_DOMAIN_ID)
    assert ref.ref_id == "rule:project.scope_consistency:1.0.0"
    assert ref.kind == DomainTraceReferenceKind.RULE_RESULT


def test_build_project_trace_contribution_primary() -> None:
    ref = build_project_trace_reference(
        ref_id="op:project.review_status:1.0.0",
        kind=DomainTraceReferenceKind.OPERATION_RESULT,
    )
    contrib = build_project_trace_contribution(
        domain_result_id="res:project:1",
        references=(ref,),
    )
    assert isinstance(contrib, DomainTraceContribution)
    assert contrib.domain_id == DomainId.from_str(PROJECT_DOMAIN_ID)
    assert contrib.role == DomainTraceRole.PRIMARY
    assert len(contrib.references) == 2


def test_build_supporting_trace_contribution() -> None:
    ref = build_project_trace_reference(
        ref_id="rule:life_plan:1",
        kind=DomainTraceReferenceKind.RULE_RESULT,
        domain_id="domain:life-plan",
    )
    contrib = build_supporting_trace_contribution(
        domain_result_id="res:life_plan:1",
        domain_id="domain:life-plan",
        references=(ref,),
    )
    assert isinstance(contrib, DomainTraceContribution)
    assert contrib.role == DomainTraceRole.SUPPORTING
    assert contrib.domain_id == DomainId.from_str("domain:life-plan")


def test_assemble_project_trace_reference_only() -> None:
    now = datetime.now(timezone.utc)
    ref = build_project_trace_reference(
        ref_id="rule:project.scope_consistency:1.0.0",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )
    trace = assemble_project_trace(
        request_id="req:1",
        resolution_context_id="ctx:1",
        resolution_result_id="res_res:1",
        composition_id="comp:1",
        domain_result_id="res:project:1",
        references=(ref,),
        started_at=now,
        completed_at=now,
    )
    assert isinstance(trace, DomainTrace)
    assert trace.primary_domain == DomainId.from_str(PROJECT_DOMAIN_ID)
    assert trace.status == DomainTraceStatus.COMPLETED
    assert trace.references.resolution_context_id == "ctx:1"


def test_assemble_and_validate_project_trace_independent_inventory() -> None:
    from cmm.domains.project.trace import validate_project_trace
    from cmm.domains.trace_assembler import calculate_domain_trace_identity
    from cmm.domains.trace_contracts import (
        DomainResultTraceReference,
        DomainTraceAssemblyRequest,
        DomainTraceDomainSelection,
        DomainTraceReferenceInventory,
        DomainTraceReferences,
    )

    now = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    req_id = "req-proj-001"
    ctx_id = "ctx-proj-001"
    res_id = "res-proj-001"
    comp_id = "comp-proj-001"
    result_id_str = "dres-proj-001"

    ref1 = build_project_trace_reference(
        ref_id="prof-proj-001", kind=DomainTraceReferenceKind.PROFILE
    )
    ref2 = build_project_trace_reference(
        ref_id="rule:project.scope_consistency:1.0.0",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )

    trace_refs = DomainTraceReferences(
        resolution_context_id=ctx_id,
        resolution_result_id=res_id,
        composition_id=comp_id,
        cross_domain_results=(),
        presentation_result_ids=(),
    )
    assembly_request = DomainTraceAssemblyRequest(
        request_id=req_id,
        goal_id=None,
        primary_domain=PROJECT_DOMAIN_ID,
        supporting_domains=(),
        contributions=(
            build_project_trace_contribution(
                domain_result_id=result_id_str,
                references=(ref1, ref2),
            ),
        ),
        references=trace_refs,
        domain_results=(
            DomainResultTraceReference(
                result_id_str,
                PROJECT_DOMAIN_ID,
            ),
        ),
        status=DomainTraceStatus.COMPLETED,
        started_at=now,
        completed_at=now,
        metadata={},
    )
    predicted_identity = calculate_domain_trace_identity(assembly_request)

    # 1. Build independent DomainTraceReferenceInventory BEFORE trace assembly
    inventory = DomainTraceReferenceInventory(
        references=(
            DomainTraceReference(
                result_id_str,
                DomainTraceReferenceKind.DOMAIN_RESULT,
                PROJECT_DOMAIN_ID,
            ),
            ref1,
            ref2,
            DomainTraceReference(
                ctx_id, DomainTraceReferenceKind.RESOLUTION_CONTEXT, None
            ),
            DomainTraceReference(
                res_id, DomainTraceReferenceKind.RESOLUTION_RESULT, None
            ),
            DomainTraceReference(comp_id, DomainTraceReferenceKind.COMPOSITION, None),
        ),
        domain_results=(
            DomainResultTraceReference(
                result_id=result_id_str,
                domain_id=PROJECT_DOMAIN_ID,
                trace_id=predicted_identity.trace_id,
            ),
        ),
        cross_domain_results=(),
        expected_primary_domain=PROJECT_DOMAIN_ID,
        resolution_result_domains=DomainTraceDomainSelection(
            res_id, PROJECT_DOMAIN_ID, ()
        ),
        composition_domains=DomainTraceDomainSelection(comp_id, PROJECT_DOMAIN_ID, ()),
    )

    # 2. Assemble trace
    trace = assemble_project_trace(
        request_id=req_id,
        resolution_context_id=ctx_id,
        resolution_result_id=res_id,
        composition_id=comp_id,
        domain_result_id=result_id_str,
        started_at=now,
        completed_at=now,
        references=(ref1, ref2),
    )
    assert trace.id == predicted_identity.trace_id
    assert trace.digest == predicted_identity.digest

    # 3. Validate trace against prebuilt independent inventory
    val = validate_project_trace(trace=trace, inventory=inventory)
    assert val.valid is True

    # 4. Tamper cases
    # Extra reference in trace not in inventory
    tampered_extra = assemble_project_trace(
        request_id=req_id,
        resolution_context_id=ctx_id,
        resolution_result_id=res_id,
        composition_id=comp_id,
        domain_result_id=result_id_str,
        started_at=now,
        completed_at=now,
        references=(
            ref1,
            ref2,
            build_project_trace_reference(
                ref_id="forged-ref-extra", kind=DomainTraceReferenceKind.RULE_RESULT
            ),
        ),
    )
    assert (
        validate_project_trace(trace=tampered_extra, inventory=inventory).valid is False
    )

    # Substituted forged reference in inventory
    bad_inventory = DomainTraceReferenceInventory(
        references=(
            DomainTraceReference(
                result_id_str,
                DomainTraceReferenceKind.DOMAIN_RESULT,
                PROJECT_DOMAIN_ID,
            ),
            ref1,
            build_project_trace_reference(
                ref_id="forged-ref-sub", kind=DomainTraceReferenceKind.RULE_RESULT
            ),
            DomainTraceReference(
                ctx_id, DomainTraceReferenceKind.RESOLUTION_CONTEXT, None
            ),
            DomainTraceReference(
                res_id, DomainTraceReferenceKind.RESOLUTION_RESULT, None
            ),
            DomainTraceReference(comp_id, DomainTraceReferenceKind.COMPOSITION, None),
        ),
        domain_results=(
            DomainResultTraceReference(
                result_id=result_id_str,
                domain_id=PROJECT_DOMAIN_ID,
                trace_id=predicted_identity.trace_id,
            ),
        ),
        cross_domain_results=(),
        expected_primary_domain=PROJECT_DOMAIN_ID,
        resolution_result_domains=DomainTraceDomainSelection(
            res_id, PROJECT_DOMAIN_ID, ()
        ),
        composition_domains=DomainTraceDomainSelection(comp_id, PROJECT_DOMAIN_ID, ()),
    )
    assert validate_project_trace(trace=trace, inventory=bad_inventory).valid is False
