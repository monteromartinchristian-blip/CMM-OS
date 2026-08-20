"""Phase 10.24 — Reflection confirmed-persistence tests.

DP-024 requires confirmed persistence: a candidate pattern never becomes
persistent from repetition, model inference, or memory summaries.  Only a
valid shared confirmation authorizes a persistence proposal; malformed or
nonliteral authorization fails closed (spec §17, §28, §44.D).
"""

from __future__ import annotations

import json

from cmm.domains.memory_contracts import DomainMemoryApprovalDecisionSnapshot
from cmm.domains.reflection.rules import (
    authorizes_confirmation,
    classify_persistence,
    evaluate_persistence_basis,
)


def _pattern(pattern, *, sources=(), repetition=0, model_inferred=False,
             duplicate_summaries=(), single_conversation=False):
    return {
        "pattern": pattern,
        "sources": tuple(sources),
        "repetition_count": repetition,
        "model_inferred": model_inferred,
        "duplicate_summaries": tuple(duplicate_summaries),
        "single_conversation": single_conversation,
    }


def test_literal_true_authorizes_confirmation():
    for raw in ("true", "false", 1, 0, "0", "1", [], {}, (), None, 1.0, -1, float("nan")):
        assert authorizes_confirmation(raw) is False
    assert authorizes_confirmation(True) is True
    assert authorizes_confirmation(False) is False


def test_candidate_pattern_not_confirmed():
    record = classify_persistence(_pattern("avoids intimacy", sources=("msg:1",)))
    assert record["persistence_state"] == "candidate"
    assert record["confirmed"] is False
    assert record["authorization_accepted"] is False


def test_repeated_model_inference_not_confirmed():
    record = classify_persistence(
        _pattern("avoids intimacy", model_inferred=True, repetition=5)
    )
    assert record["confirmed"] is False
    assert record["persistence_state"] == "candidate"
    assert "model_inference" in record["excluded_reasons"]


def test_repeated_evidence_in_one_conversation_not_confirmed():
    record = classify_persistence(
        _pattern("avoids intimacy", sources=("conv:1", "conv:1", "conv:1"),
                 single_conversation=True, repetition=3)
    )
    assert record["confirmed"] is False
    assert "single_conversation" in record["excluded_reasons"]


def test_duplicate_memory_summaries_give_no_corroboration():
    basis = evaluate_persistence_basis(
        _pattern("avoids intimacy", duplicate_summaries=("m1", "m2", "m3"))
    )
    assert basis["independent_grounded_sources"] == 0
    assert basis["duplicate_summaries_ignored"] == 3
    record = classify_persistence(_pattern("avoids intimacy", duplicate_summaries=("m1", "m2")))
    assert record["confirmed"] is False


from cmm.domains.memory_contracts import (
    DomainMemoryApprovalRequestSnapshot,
    DomainMemoryCapability,
    DomainMemoryPermissionDecisionSnapshot,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemorySensitivityLevel,
    DomainMemoryTraceSnapshot,
    DomainMemoryViewSnapshot,
)
from cmm.domains.reflection.memory import (
    build_reflection_memory_binding,
    build_reflection_memory_proposal,
    build_reflection_memory_view,
    build_reflection_memory_view_request,
)


def _valid_persistence_chain(proposal_id: str = "prop-pers-1", *, approved: bool = True):
    ref = DomainMemoryReference(
        reference_id=f"ref:{proposal_id}",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=f"item:{proposal_id}",
        domain_id="domain:reflection",
        applicable_domains=("domain:reflection",),
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
    permission = DomainMemoryPermissionDecisionSnapshot(
        decision_id=f"perm:{proposal_id}",
        allowed=True,
        capabilities=(DomainMemoryCapability.PROPOSE,),
        source_domain_id="domain:reflection",
        target_domain_id="domain:reflection",
        sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
    )
    view_request = build_reflection_memory_view_request(
        request_id=f"req:{proposal_id}",
        trace_id=f"trace:{proposal_id}",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
        permission_decision_ids=(f"perm:{proposal_id}",),
    )
    proposal = build_reflection_memory_proposal(
        proposal_id=proposal_id,
        affected_reference_ids=(f"ref:{proposal_id}",),
    )
    temp_inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id=f"trace:{proposal_id}", primary_domain="domain:reflection"
            ),
        ),
        permission_decisions=(permission,),
    )
    view = build_reflection_memory_view(request=view_request, inventory=temp_inventory)
    binding = build_reflection_memory_binding(
        proposal=proposal,
        view=view,
        trace_id=f"trace:{proposal_id}",
        permission_decision_ids=(f"perm:{proposal_id}",),
        approval_request_ids=(f"appr-req:{proposal_id}",),
        approval_decision_ids=(f"appr-dec:{proposal_id}",),
    )
    inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        proposals=(proposal,),
        permission_decisions=(permission,),
        approval_requests=(
            DomainMemoryApprovalRequestSnapshot(
                request_id=f"appr-req:{proposal_id}", proposal_id=proposal_id
            ),
        ),
        approval_decisions=(
            DomainMemoryApprovalDecisionSnapshot(
                decision_id=f"appr-dec:{proposal_id}",
                request_id=f"appr-req:{proposal_id}",
                approved=approved,
            ),
        ),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id=f"trace:{proposal_id}", primary_domain="domain:reflection"
            ),
        ),
        views=(
            DomainMemoryViewSnapshot(
                view_id=view.view_id,
                request_id=view.request_id,
                primary_domain=view.primary_domain,
                trace_id=view.trace_id,
                view_digest=view.content_digest,
            ),
        ),
    )
    return binding, inventory


def test_valid_confirmation_authorizes_proposal():
    binding, inventory = _valid_persistence_chain(proposal_id="prop-pers-1", approved=True)
    record = classify_persistence(
        {**_pattern("avoids intimacy", sources=("msg:1", "msg:2")), "proposal_id": "prop-pers-1"},
        confirmation_binding=binding,
        confirmation_inventory=inventory,
    )
    assert record["authorization_accepted"] is True
    assert record["eligible_for_confirmation"] is True
    assert record["confirmed"] is True
    assert record["persistence_state"] == "confirmed"


def test_raw_true_is_not_a_complete_confirmation():
    record = classify_persistence(
        _pattern("avoids intimacy", sources=("msg:1", "msg:2")),
        confirmation=True,
    )
    assert record["confirmed"] is False
    assert record["authorization_accepted"] is False


def test_model_or_memory_summary_provenance_not_grounded():
    binding, inventory = _valid_persistence_chain(proposal_id="prop-pers-2", approved=True)
    for sources in (("model:1",), ("memory:summary:1",), ("memory:1",), ("summary:1",)):
        record = classify_persistence(
            {**_pattern("avoids intimacy", sources=sources), "proposal_id": "prop-pers-2"},
            confirmation_binding=binding,
            confirmation_inventory=inventory,
        )
        assert record["confirmed"] is False
        assert record["persistence_state"] != "confirmed"


def test_rejection_means_not_persisted():
    record = classify_persistence(
        _pattern("avoids intimacy", sources=("msg:1",)),
        confirmation=False,
    )
    assert record["confirmed"] is False
    assert record["persistence_state"] == "rejected"


def test_missing_confirmation_not_persisted():
    record = classify_persistence(_pattern("avoids intimacy"))
    assert record["confirmed"] is False
    assert record["persistence_state"] == "candidate"
    assert record["authorization_accepted"] is False


def test_nonliteral_authorization_fails_closed():
    for raw in ("true", "false", 1, 0, "yes", "1", [], {}):
        record = classify_persistence(_pattern("p"), confirmation=raw)
        assert record["confirmed"] is False
        assert record["authorization_accepted"] is False
        assert record["authorization_malformed"] is True


def test_absent_authorization_is_not_malformed_but_not_accepted():
    record = classify_persistence(_pattern("p"), confirmation=None)
    assert record["confirmed"] is False
    assert record["authorization_accepted"] is False
    assert record["authorization_malformed"] is False


def test_json_safe_persistence_result():
    record = classify_persistence(_pattern("p", sources=("s1",)), confirmation=True)
    json.dumps(record, allow_nan=False)


def test_persistence_never_from_repetition_alone():
    record = classify_persistence(
        _pattern("p", sources=("s1", "s2", "s3"), repetition=10),
        confirmation=None,
    )
    assert record["confirmed"] is False
    assert record["persistence_state"] == "candidate"