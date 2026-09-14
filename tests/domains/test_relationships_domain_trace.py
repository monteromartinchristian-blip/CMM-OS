"""Tests for Phase 10.21 Relationships Domain trace composition
(reference-only)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from cmm.domains import relationships
from cmm.domains.relationships.definition import RELATIONSHIPS_DOMAIN_ID
from cmm.domains.trace_contracts import (
    DomainTrace,
    DomainTraceContractError,
    DomainTraceContribution,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceRole,
)

NOW = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)


def _ref(ref_id: str, kind: DomainTraceReferenceKind) -> DomainTraceReference:
    return relationships.build_relationships_trace_reference(ref_id=ref_id, kind=kind)


def test_reference_domain_scoped_only():
    with pytest.raises(DomainTraceContractError):
        relationships.build_relationships_trace_reference(
            ref_id="ctx:1", kind=DomainTraceReferenceKind.RESOLUTION_CONTEXT
        )


def test_contribution_adds_one_domain_result_and_keeps_callers():
    ref = _ref("op:1", DomainTraceReferenceKind.OPERATION_RESULT)
    contribution = relationships.build_relationships_trace_contribution(
        domain_result_id="dr:1", references=(ref,)
    )
    assert isinstance(contribution, DomainTraceContribution)
    assert contribution.role is DomainTraceRole.PRIMARY
    contribution_ids = {r.ref_id for r in contribution.references}
    assert contribution_ids == {"dr:1", "op:1"}
    kinds = [r.kind for r in contribution.references]
    assert kinds.count(DomainTraceReferenceKind.DOMAIN_RESULT) == 1


def test_assemble_uses_real_global_ids():
    trace = relationships.assemble_relationships_trace(
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
    assert str(trace.primary_domain) == "domain:relationships"
    assert trace.domain_results[0].domain_id.slug == "relationships"


def test_assemble_round_trip():
    trace = relationships.assemble_relationships_trace(
        request_id="req1",
        resolution_context_id="resolution-context:1",
        resolution_result_id="resolution-result:1",
        composition_id="composition:1",
        domain_result_id="domain-result:1",
        started_at=NOW,
        completed_at=NOW.replace(second=1),
        goal_id="goal:1",
    )
    restored = DomainTrace.from_dict(trace.to_dict())
    assert restored == trace


def _trace_and_inventory():
    trace = relationships.assemble_relationships_trace(
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
        expected_primary_domain=RELATIONSHIPS_DOMAIN_ID,
        expected_supporting_domains=(),
        resolution_result_domains=DomainTraceDomainSelection(
            "resolution-result:1", RELATIONSHIPS_DOMAIN_ID
        ),
        composition_domains=DomainTraceDomainSelection(
            "composition:1", RELATIONSHIPS_DOMAIN_ID
        ),
    )
    return trace, inventory


def test_trace_valid_with_full_inventory():
    trace, inventory = _trace_and_inventory()
    result = relationships.validate_relationships_trace(
        trace=trace, inventory=inventory
    )
    assert result.valid is True


def test_trace_invalid_when_inventory_has_unknown_reference():
    trace, inventory = _trace_and_inventory()
    extra = _ref("ghost:1", DomainTraceReferenceKind.FINDING)
    bad_inventory = replace(inventory, references=(*inventory.references, extra))
    result = relationships.validate_relationships_trace(
        trace=trace, inventory=bad_inventory
    )
    assert result.valid is False
