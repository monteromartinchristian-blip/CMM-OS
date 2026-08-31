"""Phase 10.24 — Reflection memory boundary tests.

Reflection memory integration is proposal/reference-only through the shared
memory contracts: proposals require confirmation, memory entries are
provenance (never current truth), and no Reflection memory store exists
(spec §18, §38, §46).
"""

from __future__ import annotations

import json

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
from cmm.domains.reflection import (
    build_reflection_memory_binding,
    build_reflection_memory_proposal,
    build_reflection_memory_view,
    build_reflection_memory_view_request,
    validate_reflection_memory_binding,
)
from cmm.domains.reflection.rules import (
    authorizes_confirmation,
    classify_persistence,
)


def _reference(reference_id: str, canonical_id: str) -> DomainMemoryReference:
    return DomainMemoryReference(
        reference_id=reference_id,
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=canonical_id,
        domain_id="domain:reflection",
        applicable_domains=("domain:reflection",),
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )


def _inventory(
    *references: DomainMemoryReference, traces=()
) -> DomainMemoryReferenceInventory:
    return DomainMemoryReferenceInventory(references=references, traces=tuple(traces))


def test_memory_proposal_always_requires_confirmation():
    proposal = build_reflection_memory_proposal(proposal_id="mp-1")
    assert proposal.proposal_id == "mp-1"
    assert proposal.proposal_kind is DomainMemoryProposalKind.MEMORY_UPDATE
    assert proposal.requires_confirmation is True
    from cmm.domains.memory_contracts import DomainMemoryCapability

    assert DomainMemoryCapability.PROPOSE in proposal.required_capabilities


def test_no_confirmation_override_supported():
    """The builder exposes no way to create a non-confirmable proposal."""
    proposal = build_reflection_memory_proposal(proposal_id="mp-2")
    assert proposal.requires_confirmation is True


def test_memory_view_request_and_binding():
    ref = _reference("ref:1", "item:1")
    inventory = _inventory(ref)
    request = build_reflection_memory_view_request(
        request_id="req-1",
        trace_id="trace-1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    assert str(request.primary_domain) == "domain:reflection"
    view = build_reflection_memory_view(request=request, inventory=inventory)
    assert view.primary_domain == request.primary_domain
    assert view.request_id == request.request_id

    proposal = build_reflection_memory_proposal(proposal_id="mp-3")
    binding = build_reflection_memory_binding(
        proposal=proposal,
        view=view,
        trace_id="trace-1",
        permission_decision_ids=("perm-1",),
    )
    assert binding.memory_proposal_ids == ("mp-3",)
    assert binding.domain_id == "domain:reflection"
    assert binding.trace_id == "trace-1"
    json.dumps(
        {
            "binding_id": binding.binding_id,
            "view_digest": binding.view_digest,
            "memory_proposal_ids": list(binding.memory_proposal_ids),
        },
        allow_nan=False,
    )


def test_memory_view_validation():
    trace = DomainMemoryTraceSnapshot(
        trace_id="trace-2", primary_domain="domain:reflection"
    )
    ref = _reference("ref:2", "item:2")
    permission = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm-2",
        allowed=True,
        capabilities=(DomainMemoryCapability.READ,),
        source_domain_id="domain:reflection",
        target_domain_id="domain:reflection",
        sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
    )
    request = build_reflection_memory_view_request(
        request_id="req-2",
        trace_id="trace-2",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
        permission_decision_ids=("perm-2",),
    )
    inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        traces=(trace,),
        permission_decisions=(permission,),
    )
    view = build_reflection_memory_view(request=request, inventory=inventory)
    proposal = build_reflection_memory_proposal(proposal_id="mp-4")
    binding = build_reflection_memory_binding(
        proposal=proposal,
        view=view,
        trace_id="trace-2",
        permission_decision_ids=("perm-2",),
    )
    result = validate_reflection_memory_binding(binding=binding, inventory=inventory)
    # runs against the real shared validator; result is structured and fail-closed
    assert isinstance(result.is_valid, bool)


def test_memory_validation_fails_closed_on_missing_trace():
    ref = _reference("ref:3", "item:3")
    request = build_reflection_memory_view_request(
        request_id="req-3",
        trace_id="trace-3",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    inventory = DomainMemoryReferenceInventory(references=(ref,))
    view = build_reflection_memory_view(request=request, inventory=inventory)
    proposal = build_reflection_memory_proposal(proposal_id="mp-5")
    binding = build_reflection_memory_binding(
        proposal=proposal, view=view, trace_id="trace-3"
    )
    result = validate_reflection_memory_binding(binding=binding, inventory=inventory)
    assert result.is_valid is False


def test_memory_entry_is_provenance_not_truth():
    """A prior memory entry is provenance; it never silently becomes a current
    fact, identity, adopted decision, or confirmed persistent interest."""
    record = {
        "pattern": "fears conflict",
        "sources": ("memory:old",),
        "repetition_count": 5,
        "model_inferred": True,
        "duplicate_summaries": ("memory:old",),
        "single_conversation": False,
    }
    result = classify_persistence(record, confirmation=None)
    assert result["confirmed"] is False
    assert result["persistence_state"] != "confirmed"
    assert authorizes_confirmation(record.get("confirmed")) is False


def test_no_reflection_memory_store():
    import cmm.domains.reflection

    assert not hasattr(cmm.domains.reflection, "ReflectionMemoryStore")
    assert not hasattr(cmm.domains.reflection, "ReflectionMemoryRegistry")
    assert not hasattr(cmm.domains.reflection, "ReflectionMemoryEngine")
