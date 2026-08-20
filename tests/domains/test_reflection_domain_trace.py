"""Phase 10.24 — Reflection trace tests.

Trace stores references/identifiers and permission decisions, never private
chain-of-thought.  Reflection composes caller-supplied typed references into
the shared Phase 10.17 trace contracts without fabricating provenance
(spec §37, §46).
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone

from cmm.domains.reflection import (
    assemble_reflection_trace,
    build_reflection_trace_contribution,
    build_reflection_trace_reference,
    validate_reflection_trace,
)
from cmm.domains.reflection.definition import REFLECTION_DOMAIN_ID
from cmm.domains.trace_contracts import (
    DomainTraceContribution,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceRole,
    DomainTraceStatus,
    DomainTraceValidationCode,
)

NOW = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)

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
    return build_reflection_trace_reference(ref_id=ref_id, kind=kind)


def _caller_refs() -> tuple[DomainTraceReference, ...]:
    return tuple(_ref(ref_id, kind) for kind, ref_id in _CALLER_KINDS)


def test_reference_wrapper_uses_supplied_kind():
    ref = _ref("res:1", DomainTraceReferenceKind.RESOURCE_RESOLUTION)
    assert ref.ref_id == "res:1"
    assert ref.kind is DomainTraceReferenceKind.RESOURCE_RESOLUTION
    assert str(ref.domain_id) == "domain:reflection"


def test_contribution_adds_exactly_one_domain_result():
    contribution = build_reflection_trace_contribution(
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
    contribution = build_reflection_trace_contribution(
        domain_result_id="dr:1", references=refs
    )
    contribution_ids = {r.ref_id for r in contribution.references}
    expected_ids = {ref_id for _, ref_id in _CALLER_KINDS} | {"dr:1"}
    assert contribution_ids == expected_ids


def test_assemble_uses_real_global_ids():
    trace = assemble_reflection_trace(
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
    assert trace.domain_results[0].result_id == "domain-result:1"
    assert trace.domain_results[0].domain_id.slug == "reflection"


def test_trace_is_reference_only_no_chain_of_thought():
    ref = _ref("op:1", DomainTraceReferenceKind.OPERATION_RESULT)
    trace = assemble_reflection_trace(
        request_id="req2",
        resolution_context_id="resolution-context:1",
        resolution_result_id="resolution-result:1",
        composition_id="composition:1",
        domain_result_id="domain-result:1",
        references=(ref,),
        started_at=NOW,
        completed_at=NOW.replace(second=1),
    )
    serialized = json.dumps(trace.to_dict(), allow_nan=False)
    assert "chain" not in serialized.lower()
    assert "private" not in serialized.lower()
    assert trace.status is DomainTraceStatus.COMPLETED


def _trace_and_inventory():
    trace = assemble_reflection_trace(
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
        expected_primary_domain=REFLECTION_DOMAIN_ID,
        expected_supporting_domains=(),
        resolution_result_domains=DomainTraceDomainSelection(
            "resolution-result:1", REFLECTION_DOMAIN_ID
        ),
        composition_domains=DomainTraceDomainSelection(
            "composition:1", REFLECTION_DOMAIN_ID
        ),
    )
    return trace, inventory


def test_trace_valid_with_full_inventory():
    trace, inventory = _trace_and_inventory()
    result = validate_reflection_trace(trace=trace, inventory=inventory)
    assert result.valid is True


def test_trace_invalid_when_inventory_has_unknown_reference():
    trace, inventory = _trace_and_inventory()
    extra = _ref("ghost:1", DomainTraceReferenceKind.FINDING)
    bad_inventory = replace(inventory, references=(*inventory.references, extra))
    result = validate_reflection_trace(trace=trace, inventory=bad_inventory)
    assert result.valid is False
    assert DomainTraceValidationCode.MISSING_REFERENCE in result.codes