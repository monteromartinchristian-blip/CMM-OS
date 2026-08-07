"""Tests for General Domain trace composition (real Phase 10.17 references)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from cmm.domains.general import (
    assemble_general_trace,
    build_general_trace_contribution,
    build_general_trace_reference,
    validate_general_trace,
)
from cmm.domains.general.definition import GENERAL_DOMAIN_ID
from cmm.domains.trace_contracts import (
    DomainTrace,
    DomainTraceContractError,
    DomainTraceContribution,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceRole,
    DomainTraceValidationCode,
)

NOW = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)

# Caller-supplied reference kinds that must appear exactly as provided.
_CALLER_KINDS = (
    (DomainTraceReferenceKind.RESOURCE_RESOLUTION, "res:1"),
    (DomainTraceReferenceKind.PROFILE, "profile:1"),
    (DomainTraceReferenceKind.RULE_RESULT, "rule:1"),
    (DomainTraceReferenceKind.PERMISSION_DECISION, "perm:1"),
    (DomainTraceReferenceKind.APPROVAL_REQUEST, "approval-req:1"),
    (DomainTraceReferenceKind.APPROVAL_DECISION, "approval-dec:1"),
    (DomainTraceReferenceKind.OPERATION_RESULT, "op:1"),
    (DomainTraceReferenceKind.WORKFLOW_RESULT, "wf:1"),
)


def _ref(ref_id: str, kind: DomainTraceReferenceKind) -> DomainTraceReference:
    return build_general_trace_reference(ref_id=ref_id, kind=kind)


def _caller_refs() -> tuple[DomainTraceReference, ...]:
    return tuple(_ref(ref_id, kind) for kind, ref_id in _CALLER_KINDS)


def test_reference_wrapper_uses_supplied_kind():
    ref = _ref("res:1", DomainTraceReferenceKind.RESOURCE_RESOLUTION)
    assert ref.ref_id == "res:1"
    assert ref.kind is DomainTraceReferenceKind.RESOURCE_RESOLUTION
    assert str(ref.domain_id) == "domain:general"


def test_reference_wrapper_domain_scoped_only():
    with pytest.raises(DomainTraceContractError):
        build_general_trace_reference(
            ref_id="ctx:1", kind=DomainTraceReferenceKind.RESOLUTION_CONTEXT
        )


def test_contribution_adds_exactly_one_domain_result():
    contribution = build_general_trace_contribution(
        domain_result_id="dr:1",
        references=(_ref("op:1", DomainTraceReferenceKind.OPERATION_RESULT),),
    )
    assert isinstance(contribution, DomainTraceContribution)
    assert contribution.role is DomainTraceRole.PRIMARY
    kinds = [r.kind for r in contribution.references]
    assert kinds.count(DomainTraceReferenceKind.DOMAIN_RESULT) == 1
    assert DomainTraceReferenceKind.OPERATION_RESULT in kinds


def test_contribution_preserves_caller_references_exactly():
    refs = _caller_refs()
    contribution = build_general_trace_contribution(
        domain_result_id="dr:1", references=refs
    )
    contribution_ids = {r.ref_id for r in contribution.references}
    expected_ids = {ref_id for _, ref_id in _CALLER_KINDS} | {"dr:1"}
    assert contribution_ids == expected_ids


def test_assemble_uses_real_global_ids():
    trace = assemble_general_trace(
        request_id="req1",
        resolution_context_id="resolution-context:1",
        resolution_result_id="resolution-result:1",
        composition_id="composition:1",
        domain_result_id="domain-result:1",
        started_at=NOW,
        completed_at=NOW.replace(second=1),
    )
    assert trace.references.resolution_context_id == "resolution-context:1"
    assert trace.references.resolution_result_id == "resolution-result:1"
    assert trace.references.composition_id == "composition:1"
    # No fabricated IDs derived from any trace_id.
    assert trace.domain_results[0].result_id == "domain-result:1"
    assert trace.domain_results[0].domain_id.slug == "general"


def test_assemble_keeps_caller_references_in_contribution():
    ref = _ref("op:1", DomainTraceReferenceKind.OPERATION_RESULT)
    trace = assemble_general_trace(
        request_id="req1",
        resolution_context_id="resolution-context:1",
        resolution_result_id="resolution-result:1",
        composition_id="composition:1",
        domain_result_id="domain-result:1",
        references=(ref,),
        started_at=NOW,
        completed_at=NOW.replace(second=1),
    )
    op_refs = [
        r
        for r in trace.contributions[0].references
        if r.kind is DomainTraceReferenceKind.OPERATION_RESULT
    ]
    assert [r.ref_id for r in op_refs] == ["op:1"]
def test_assemble_round_trip():
    trace = assemble_general_trace(
        request_id="req1",
        resolution_context_id="resolution-context:1",
        resolution_result_id="resolution-result:1",
        composition_id="composition:1",
        domain_result_id="domain-result:1",
        started_at=NOW,
        completed_at=NOW.replace(second=1),
        goal_id="goal:1",
    )
    assert isinstance(trace, DomainTrace)
    restored = DomainTrace.from_dict(trace.to_dict())
    assert restored == trace


def _trace_and_inventory():
    trace = assemble_general_trace(
        request_id="req1",
        resolution_context_id="resolution-context:1",
        resolution_result_id="resolution-result:1",
        composition_id="composition:1",
        domain_result_id="domain-result:1",
        started_at=NOW,
        completed_at=NOW.replace(second=1),
    )
    inventory = DomainTraceReferenceInventory(
        references=trace.all_references(),
        domain_results=trace.domain_results,
        cross_domain_results=trace.references.cross_domain_results,
        expected_primary_domain=GENERAL_DOMAIN_ID,
        expected_supporting_domains=(),
        resolution_result_domains=DomainTraceDomainSelection(
            "resolution-result:1", GENERAL_DOMAIN_ID
        ),
        composition_domains=DomainTraceDomainSelection(
            "composition:1", GENERAL_DOMAIN_ID
        ),
    )
    return trace, inventory


def test_trace_valid_with_full_inventory():
    trace, inventory = _trace_and_inventory()
    result = validate_general_trace(trace=trace, inventory=inventory)
    assert result.valid is True


def test_trace_invalid_when_inventory_has_unknown_reference():
    trace, inventory = _trace_and_inventory()
    extra = _ref("ghost:1", DomainTraceReferenceKind.FINDING)
    bad_inventory = replace(inventory, references=(*inventory.references, extra))
    result = validate_general_trace(trace=trace, inventory=bad_inventory)
    assert result.valid is False
    assert DomainTraceValidationCode.MISSING_REFERENCE in result.codes


def test_trace_invalid_when_inventory_reference_kind_wrong():
    trace, inventory = _trace_and_inventory()
    wrong = tuple(
        replace(item, kind=DomainTraceReferenceKind.FINDING)
        if item.ref_id == "domain-result:1"
        else item
        for item in inventory.references
    )
    bad_inventory = replace(inventory, references=wrong)
    result = validate_general_trace(trace=trace, inventory=bad_inventory)
    assert result.valid is False
    assert DomainTraceValidationCode.KIND_MISMATCH in result.codes
