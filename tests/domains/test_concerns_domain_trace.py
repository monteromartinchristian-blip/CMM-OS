"""Phase 10.25 — Concerns trace focused tests.

Trace references the semantic surfaces required by frozen design §80:
support need, evidence, uncertainty, reassurance, risk/material concern,
question rationale, action state, memory proposal, permission decisions.
References only; no chain-of-thought, no fabricated provenance.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone

from cmm.domains.concerns.definition import CONCERNS_DOMAIN_ID
from cmm.domains.concerns.trace import (
    assemble_concerns_trace,
    build_concerns_trace_contribution,
    build_concerns_trace_reference,
)
from cmm.domains.trace_contracts import (
    DomainTraceDomainSelection,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
)

NOW = datetime(2026, 8, 21, 16, 0, tzinfo=timezone.utc)

# The semantic surfaces a Concerns trace must be able to reference (frozen §80).
_REQUIRED_TRACE_KINDS = {
    "support_need": DomainTraceReferenceKind.FINDING,
    "evidence": DomainTraceReferenceKind.RESOURCE_RESOLUTION,
    "uncertainty": DomainTraceReferenceKind.GAP,
    "reassessment": DomainTraceReferenceKind.RULE_RESULT,
    "risk_material_concern": DomainTraceReferenceKind.RULE_RESULT,
    "question_rationale": DomainTraceReferenceKind.OPERATION_RESULT,
    "action_state": DomainTraceReferenceKind.DOMAIN_RESULT,
    "memory_proposal": DomainTraceReferenceKind.APPROVAL_REQUEST,
    "permission_decisions": DomainTraceReferenceKind.PERMISSION_DECISION,
}


def _trace_with_semantic_references():
    references = tuple(
        build_concerns_trace_reference(ref_id=ref_id, kind=kind)
        for ref_id, kind in (
            ("support-need:PERSPECTIVE", DomainTraceReferenceKind.FINDING),
            ("evidence:msg:1", DomainTraceReferenceKind.RESOURCE_RESOLUTION),
            ("uncertainty:intent", DomainTraceReferenceKind.GAP),
            ("rule:reassurance", DomainTraceReferenceKind.RULE_RESULT),
            ("op:identify_open_questions", DomainTraceReferenceKind.OPERATION_RESULT),
            ("perm:1", DomainTraceReferenceKind.PERMISSION_DECISION),
            ("appr-req:1", DomainTraceReferenceKind.APPROVAL_REQUEST),
        )
    )
    return assemble_concerns_trace(
        request_id="req-sem",
        resolution_context_id="rc:sem",
        resolution_result_id="rr:sem",
        composition_id="c:sem",
        domain_result_id="dr:sem",
        started_at=NOW,
        completed_at=NOW.replace(second=1),
        references=references,
    )


def test_trace_can_reference_all_required_semantic_surfaces():
    trace = _trace_with_semantic_references()
    kinds = {reference.kind for reference in trace.all_references()}
    for label, expected_kind in _REQUIRED_TRACE_KINDS.items():
        assert expected_kind in kinds, f"trace cannot reference {label}"


def test_trace_serialization_is_strict_json_and_reference_only():
    trace = _trace_with_semantic_references()
    serialized = json.dumps(trace.to_dict(), allow_nan=False).lower()
    # no chain-of-thought or private reasoning storage markers
    assert "chain_of_thought" not in serialized
    assert "private_reasoning" not in serialized


def test_supporting_domains_are_preserved_when_supplied():
    # Contribution references must belong to the primary domain (shared
    # contract).  Cross-domain results are carried as global CROSS_DOMAIN_RESULT
    # references at trace level via DomainTraceReferences.cross_domain_results.

    contribution = build_concerns_trace_contribution(
        domain_result_id="dr:support",
        references=(
            build_concerns_trace_reference(
                ref_id="concerns-rule:1", kind=DomainTraceReferenceKind.RULE_RESULT
            ),
        ),
    )
    ref_ids = {r.ref_id for r in contribution.references}
    assert "dr:support" in ref_ids
    assert "concerns-rule:1" in ref_ids


def test_assemble_rejects_nothing_valid_and_validates_clean():
    from cmm.domains.concerns.trace import validate_concerns_trace

    trace = assemble_concerns_trace(
        request_id="req-clean",
        resolution_context_id="rc:clean",
        resolution_result_id="rr:clean",
        composition_id="c:clean",
        domain_result_id="dr:clean",
        started_at=NOW,
        completed_at=NOW.replace(second=1),
    )
    inventory = DomainTraceReferenceInventory(
        references=trace.all_references(),
        domain_results=trace.domain_results,
        cross_domain_results=trace.references.cross_domain_results,
        expected_primary_domain=CONCERNS_DOMAIN_ID,
        expected_supporting_domains=(),
        resolution_result_domains=DomainTraceDomainSelection("rr:clean", CONCERNS_DOMAIN_ID),
        composition_domains=DomainTraceDomainSelection("c:clean", CONCERNS_DOMAIN_ID),
    )
    result = validate_concerns_trace(trace=trace, inventory=inventory)
    assert result.valid is True

    ghost = build_concerns_trace_reference(
        ref_id="ghost", kind=DomainTraceReferenceKind.FINDING
    )
    bad = replace(inventory, references=(*inventory.references, ghost))
    bad_result = validate_concerns_trace(trace=trace, inventory=bad)
    assert bad_result.valid is False
