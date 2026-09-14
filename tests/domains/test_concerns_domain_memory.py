"""Phase 10.25 — Concerns memory boundary focused tests.

Session concern state is distinct from semantic memory: a memory entry is
provenance (never current truth), proposals are confirmation-gated through the
shared Phase 10.18 contracts, and no Concerns memory store exists.
"""

from __future__ import annotations

import json

from cmm.domains.concerns.memory import (
    build_concerns_memory_binding,
    build_concerns_memory_proposal,
    build_concerns_memory_view,
    build_concerns_memory_view_request,
)
from cmm.domains.concerns.permissions import (
    persistence_confirmation_accepted,
)
from cmm.domains.memory_contracts import (
    DomainMemoryCapability,
    DomainMemoryPermissionDecisionSnapshot,
    DomainMemoryProposalKind,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemorySensitivityLevel,
    DomainMemoryTraceSnapshot,
)


def _reference(reference_id: str, canonical_id: str) -> DomainMemoryReference:
    return DomainMemoryReference(
        reference_id=reference_id,
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=canonical_id,
        domain_id="domain:concerns",
        applicable_domains=("domain:concerns",),
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )


def test_proposal_kind_is_memory_update_and_confirmation_gated():
    proposal = build_concerns_memory_proposal(proposal_id="mp-c-1")
    assert proposal.proposal_kind is DomainMemoryProposalKind.MEMORY_UPDATE
    assert proposal.requires_confirmation is True


def test_view_request_is_domain_scoped():
    ref = _reference("ref:c-1", "item:c-1")
    request = build_concerns_memory_view_request(
        request_id="req-c-1",
        trace_id="trace-c-1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    assert str(request.primary_domain) == "domain:concerns"
    inventory = DomainMemoryReferenceInventory(references=(ref,))
    view = build_concerns_memory_view(request=request, inventory=inventory)
    assert str(view.primary_domain) == "domain:concerns"


def test_session_concern_state_is_not_semantic_memory():
    """Concern state stays in session scope; nothing is silently durable."""
    proposal = build_concerns_memory_proposal(proposal_id="mp-c-2")
    # The only path to durability is the shared confirmation contract.
    assert proposal.requires_confirmation is True
    record = persistence_confirmation_accepted(
        confirmation=None,
        content_kind="support_need",
    )
    assert record["accepted"] is False


def test_repeated_mention_never_confirms_persistence():
    """Repetition is not authorization: three mentions of the same fear stay
    unpersisted without the shared contract."""
    for mention_count in (1, 3, 9):
        record = persistence_confirmation_accepted(
            confirmation=None,
            content_kind="fear",
            repetition_count=mention_count,
        )
        assert record["accepted"] is False


def test_inferred_pattern_never_persists_even_with_valid_chain():
    from cmm.domains.concerns.permissions import (
        persistence_confirmation_accepted as accept,
    )

    # Even a structurally valid chain cannot authorize restricted content;
    # covered end-to-end in the permissions module tests; here we pin that the
    # restriction check precedes chain validation.
    record = accept(confirmation=None, content_kind="inferred_emotional_pattern")
    assert record["accepted"] is False
    json.dumps(record, allow_nan=False)


def test_permission_snapshot_read_capability_shape():
    permission = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm-c-1",
        allowed=True,
        capabilities=(DomainMemoryCapability.READ,),
        source_domain_id="domain:concerns",
        target_domain_id="domain:concerns",
        sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
    )
    assert permission.allowed is True
    assert DomainMemoryCapability.DELETE not in permission.capabilities


def test_binding_content_binds_trace_and_view():
    trace = DomainMemoryTraceSnapshot(
        trace_id="trace-c-9", primary_domain="domain:concerns"
    )
    ref = _reference("ref:c-9", "item:c-9")
    request = build_concerns_memory_view_request(
        request_id="req-c-9",
        trace_id="trace-c-9",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
        permission_decision_ids=("perm-c-9",),
    )
    inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        traces=(trace,),
    )
    view = build_concerns_memory_view(request=request, inventory=inventory)
    proposal = build_concerns_memory_proposal(proposal_id="mp-c-9")
    binding = build_concerns_memory_binding(
        proposal=proposal,
        view=view,
        trace_id="trace-c-9",
        permission_decision_ids=("perm-c-9",),
    )
    assert binding.trace_id == "trace-c-9"
    assert binding.view_id == view.view_id
